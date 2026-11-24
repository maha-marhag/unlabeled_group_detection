#!/usr/bin/env python3
"""Visualize final labeled-community transitions for selected groups."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from graph_matching import find_project_root


APPROACHES = ["cumulative", "interval", "overlap"]
EVENT_COLORS = {
    "birth": "#16a34a",
    "continuation": "#2563eb",
    "split": "#f97316",
    "merge": "#9333ea",
    "death": "#dc2626",
}


def observation_snapshot(observation_id: str) -> int:
    """Extract the XX snapshot component from PREFIX-CXXYY."""
    match = re.search(r"-C(\d{2})(\d{2})$", observation_id)
    if not match:
        raise ValueError(f"Unexpected observation ID format: {observation_id}")
    return int(match.group(1))


def parse_event(event: str) -> dict:
    """Parse EVENT_ID:type@sX or EVENT_ID:type@sX->sY."""
    event_id, rest = event.split(":", 1)
    event_type, snapshot_ref = rest.split("@", 1)
    snapshots = [int(item) for item in re.findall(r"s(\d+)", snapshot_ref)]
    if len(snapshots) == 1:
        x = float(snapshots[0])
    else:
        x = sum(snapshots[:2]) / 2
    return {
        "event_id": event_id,
        "event_type": event_type,
        "snapshot_ref": snapshot_ref,
        "x": x,
    }


def selected_groups(final_communities: pd.DataFrame, count: int) -> pd.DataFrame:
    """Pick representative final groups with long, non-trivial histories."""
    return (
        final_communities.sort_values(
            ["lifespan_snapshots", "final_size", "identity_group"],
            ascending=[False, False, True],
        )
        .head(count)
        .sort_values("identity_group")
    )


def add_group_trace(
    fig: go.Figure,
    row: int,
    approach: str,
    group_row: pd.Series,
    y: float,
) -> None:
    """Add one final group's observation chain and event markers."""
    observations = str(group_row["observation_ids"]).split("=")
    snapshots = [observation_snapshot(item) for item in observations]
    label = f"{approach} {group_row['identity_group']}"

    fig.add_trace(
        go.Scatter(
            x=snapshots,
            y=[y] * len(snapshots),
            mode="lines+markers+text",
            line={"width": 2.5},
            marker={
                "size": 12,
                "line": {"width": 1, "color": "white"},
            },
            text=observations,
            textposition="top center",
            textfont={"size": 9},
            name=label,
            legendgroup=label,
            hovertemplate=(
                f"<b>{label}</b><br>"
                "snapshot=%{x}<br>"
                "observation=%{text}<br>"
                f"final_size={group_row['final_size']}<br>"
                f"lifespan_snapshots={group_row['lifespan_snapshots']}"
                "<extra></extra>"
            ),
        ),
        row=row,
        col=1,
    )

    events = [item for item in str(group_row["events"]).split(";") if item]
    event_points = [parse_event(item) for item in events]
    for event_type, color in EVENT_COLORS.items():
        typed = [item for item in event_points if item["event_type"] == event_type]
        if not typed:
            continue
        fig.add_trace(
            go.Scatter(
                x=[item["x"] for item in typed],
                y=[y - 0.18] * len(typed),
                mode="markers",
                marker={
                    "symbol": "diamond",
                    "size": 10,
                    "color": color,
                    "line": {"width": 1, "color": "white"},
                },
                name=event_type,
                legendgroup=f"event-{event_type}",
                showlegend=(row == 1 and y == 0),
                customdata=[
                    [item["event_id"], item["event_type"], item["snapshot_ref"]]
                    for item in typed
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "type=%{customdata[1]}<br>"
                    "snapshot=%{customdata[2]}<br>"
                    f"group={group_row['identity_group']}"
                    "<extra></extra>"
                ),
            ),
            row=row,
            col=1,
        )


def build_figure(input_dir: Path, groups_per_approach: int) -> go.Figure:
    """Build the multi-approach transition figure."""
    fig = make_subplots(
        rows=len(APPROACHES),
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.12,
        subplot_titles=[approach.title() for approach in APPROACHES],
    )

    for row, approach in enumerate(APPROACHES, start=1):
        final_path = input_dir / approach / "final_communities.csv"
        final_communities = pd.read_csv(final_path, keep_default_na=False)
        picked = selected_groups(final_communities, groups_per_approach)

        for index, (_, group_row) in enumerate(picked.iterrows()):
            add_group_trace(fig, row, approach, group_row, float(index))

        fig.update_yaxes(
            tickmode="array",
            tickvals=list(range(len(picked))),
            ticktext=[
                f"{item.identity_group}<br>n={item.final_size}"
                for item in picked.itertuples()
            ],
            range=[-0.7, len(picked) - 0.25],
            title_text="Final group",
            row=row,
            col=1,
        )
        fig.update_xaxes(
            dtick=1,
            title_text="Snapshot",
            row=row,
            col=1,
        )

    fig.update_layout(
        title={
            "text": "Final Community Transition Events",
            "x": 0.5,
        },
        height=920,
        width=1400,
        template="plotly_white",
        hovermode="closest",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
        margin={"l": 90, "r": 35, "t": 95, "b": 55},
    )
    return fig


def parse_args() -> argparse.Namespace:
    project_dir = find_project_root()
    default_input = (
        project_dir / "code" / "graph-matching" / "outputs" / "stage_identification"
    )
    default_output = (
        project_dir
        / "code"
        / "graph-matching"
        / "outputs"
        / "visualizations"
        / "final_community_transition_events.html"
    )
    parser = argparse.ArgumentParser(
        description="Visualize transition events for final labeled communities."
    )
    parser.add_argument("--input", type=Path, default=default_input)
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument("--groups-per-approach", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fig = build_figure(args.input, args.groups_per_approach)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(args.output, include_plotlyjs="cdn")
    print(args.output)


if __name__ == "__main__":
    main()
