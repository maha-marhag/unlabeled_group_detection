#!/usr/bin/env python3
"""Draw branching transition graphs around selected final communities."""

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
LANES = [1, -1, 2, -2, 3, -3, 4, -4, 5, -5]


def split_ids(value: object) -> list[str]:
    """Split semicolon-separated IDs while keeping empty cells harmless."""
    if value is None:
        return []
    text = str(value)
    if not text:
        return []
    return [item for item in text.split(";") if item]


def observation_snapshot(observation_id: str) -> int:
    """Extract the XX snapshot component from PREFIX-CXXYY."""
    match = re.search(r"-C(\d{2})(\d{2})$", observation_id)
    if not match:
        raise ValueError(f"Unexpected observation ID format: {observation_id}")
    return int(match.group(1))


def selected_groups(final_communities: pd.DataFrame, count: int) -> pd.DataFrame:
    """Pick long-lived final groups to make branching histories visible."""
    return (
        final_communities.sort_values(
            ["lifespan_snapshots", "final_size", "identity_group"],
            ascending=[False, False, True],
        )
        .head(count)
        .sort_values("identity_group")
    )


def relevant_events(events: pd.DataFrame, chain_observations: set[str]) -> pd.DataFrame:
    """Return events that directly touch a selected final group's chain."""
    mask = []
    for event in events.itertuples(index=False):
        participants = set(split_ids(event.source_observation_ids)) | set(
            split_ids(event.target_observation_ids)
        )
        mask.append(bool(participants & chain_observations))
    return events.loc[mask].copy()


def edge_rows(events: pd.DataFrame) -> list[dict]:
    """Expand event rows into directed observation-to-observation edges."""
    rows = []
    for event in events.itertuples(index=False):
        sources = split_ids(event.source_observation_ids)
        targets = split_ids(event.target_observation_ids)
        if not sources:
            for target in targets:
                rows.append(
                    {
                        "source": None,
                        "target": target,
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "from_snapshot": event.from_snapshot,
                        "to_snapshot": event.to_snapshot,
                    }
                )
            continue
        if not targets:
            for source in sources:
                rows.append(
                    {
                        "source": source,
                        "target": None,
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "from_snapshot": event.from_snapshot,
                        "to_snapshot": event.to_snapshot,
                    }
                )
            continue
        for source in sources:
            for target in targets:
                rows.append(
                    {
                        "source": source,
                        "target": target,
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "from_snapshot": event.from_snapshot,
                        "to_snapshot": event.to_snapshot,
                    }
                )
    return rows


def layout_nodes(
    observations: set[str],
    chain_observations: set[str],
    observation_to_group: dict[str, str],
    selected_group: str,
) -> dict[str, tuple[float, float]]:
    """Place selected-chain nodes in the center and branch nodes in lanes."""
    related_groups = sorted(
        {
            observation_to_group.get(observation, observation)
            for observation in observations
            if observation not in chain_observations
        }
    )
    lane_by_group = {
        group: LANES[index % len(LANES)]
        for index, group in enumerate(related_groups)
    }

    positions = {}
    seen_at_position: dict[tuple[int, float], int] = {}
    for observation in sorted(observations, key=lambda item: (observation_snapshot(item), item)):
        snapshot = observation_snapshot(observation)
        group = observation_to_group.get(observation, observation)
        y = 0.0 if observation in chain_observations or group == selected_group else float(lane_by_group[group])
        collision_key = (snapshot, y)
        offset = seen_at_position.get(collision_key, 0)
        seen_at_position[collision_key] = offset + 1
        if offset:
            y += 0.18 * offset
        positions[observation] = (float(snapshot), y)
    return positions


def add_ego_graph(
    fig: go.Figure,
    row: int,
    col: int,
    approach: str,
    group_row: pd.Series,
    events: pd.DataFrame,
    observation_to_group: dict[str, str],
) -> None:
    """Add one selected final group's branching transition graph."""
    chain = [item for item in str(group_row["observation_ids"]).split("=") if item]
    chain_observations = set(chain)
    selected_group = str(group_row["identity_group"])
    group_events = relevant_events(events, chain_observations)
    edges = edge_rows(group_events)

    observations = set(chain_observations)
    for edge in edges:
        if edge["source"]:
            observations.add(edge["source"])
        if edge["target"]:
            observations.add(edge["target"])

    positions = layout_nodes(
        observations,
        chain_observations,
        observation_to_group,
        selected_group,
    )

    for event_type, color in EVENT_COLORS.items():
        typed_edges = [edge for edge in edges if edge["event_type"] == event_type and edge["source"] and edge["target"]]
        if not typed_edges:
            continue
        xs = []
        ys = []
        customdata = []
        for edge in typed_edges:
            x0, y0 = positions[edge["source"]]
            x1, y1 = positions[edge["target"]]
            xs.extend([x0, x1, None])
            ys.extend([y0, y1, None])
            customdata.extend(
                [
                    [edge["event_id"], edge["event_type"], edge["source"], edge["target"]],
                    [edge["event_id"], edge["event_type"], edge["source"], edge["target"]],
                    [None, None, None, None],
                ]
            )

        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line={"color": color, "width": 2},
                customdata=customdata,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "type=%{customdata[1]}<br>"
                    "%{customdata[2]} -> %{customdata[3]}"
                    "<extra></extra>"
                ),
                name=event_type,
                legendgroup=f"event-{event_type}",
                showlegend=(row == 1 and col == 1),
            ),
            row=row,
            col=col,
        )

    event_midpoints = []
    for edge in edges:
        if not edge["source"] or not edge["target"]:
            continue
        x0, y0 = positions[edge["source"]]
        x1, y1 = positions[edge["target"]]
        event_midpoints.append(
            {
                "x": (x0 + x1) / 2,
                "y": (y0 + y1) / 2,
                "label": edge["event_type"][0].upper(),
                "event": f"{edge['event_id']}:{edge['event_type']}",
                "color": EVENT_COLORS[edge["event_type"]],
            }
        )

    if event_midpoints:
        fig.add_trace(
            go.Scatter(
                x=[item["x"] for item in event_midpoints],
                y=[item["y"] for item in event_midpoints],
                mode="markers+text",
                marker={
                    "symbol": "diamond",
                    "size": 8,
                    "color": [item["color"] for item in event_midpoints],
                    "line": {"width": 1, "color": "white"},
                },
                text=[item["label"] for item in event_midpoints],
                textposition="middle center",
                textfont={"size": 8, "color": "white"},
                customdata=[item["event"] for item in event_midpoints],
                hovertemplate="%{customdata}<extra></extra>",
                name="event",
                showlegend=False,
            ),
            row=row,
            col=col,
        )

    node_rows = []
    for observation, (x, y) in positions.items():
        group = observation_to_group.get(observation, "")
        node_rows.append(
            {
                "observation": observation,
                "x": x,
                "y": y,
                "group": group,
                "is_chain": observation in chain_observations,
            }
        )

    for is_chain, color, size in [(False, "#94a3b8", 9), (True, "#111827", 13)]:
        typed = [item for item in node_rows if item["is_chain"] == is_chain]
        if not typed:
            continue
        fig.add_trace(
            go.Scatter(
                x=[item["x"] for item in typed],
                y=[item["y"] for item in typed],
                mode="markers",
                marker={
                    "size": size,
                    "color": color,
                    "line": {"width": 1.5, "color": "white"},
                },
                customdata=[
                    [item["observation"], item["group"], "selected" if is_chain else "related"]
                    for item in typed
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "identity_group=%{customdata[1]}<br>"
                    "%{customdata[2]} observation"
                    "<extra></extra>"
                ),
                name="selected chain" if is_chain else "related observations",
                legendgroup="selected" if is_chain else "related",
                showlegend=(row == 1 and col == 1),
            ),
            row=row,
            col=col,
        )

    title = f"{approach} {selected_group}, n={group_row['final_size']}"
    fig.add_annotation(
        text=title,
        x=0.5,
        y=1.08,
        xref=f"x{(row - 1) * 3 + col} domain" if not (row == 1 and col == 1) else "x domain",
        yref=f"y{(row - 1) * 3 + col} domain" if not (row == 1 and col == 1) else "y domain",
        showarrow=False,
        font={"size": 12},
    )


def build_figure(input_dir: Path, groups_per_approach: int) -> go.Figure:
    """Build a grid of branching transition graphs."""
    fig = make_subplots(
        rows=len(APPROACHES),
        cols=groups_per_approach,
        horizontal_spacing=0.035,
        vertical_spacing=0.11,
    )

    for row, approach in enumerate(APPROACHES, start=1):
        final_communities = pd.read_csv(
            input_dir / approach / "final_communities.csv",
            keep_default_na=False,
        )
        events = pd.read_csv(
            input_dir / approach / "community_events.csv",
            keep_default_na=False,
        )
        identified = pd.read_csv(
            input_dir / approach / "identified_communities.csv",
            keep_default_na=False,
        )
        observation_to_group = dict(
            zip(identified["observation_id"], identified["identity_group"])
        )
        picked = selected_groups(final_communities, groups_per_approach)

        for col, (_, group_row) in enumerate(picked.iterrows(), start=1):
            add_ego_graph(
                fig,
                row,
                col,
                approach,
                group_row,
                events,
                observation_to_group,
            )
            fig.update_xaxes(
                title_text="Snapshot" if row == len(APPROACHES) else "",
                dtick=1,
                showgrid=True,
                row=row,
                col=col,
            )
            fig.update_yaxes(
                title_text=approach.title() if col == 1 else "",
                zeroline=True,
                showticklabels=False,
                showgrid=False,
                row=row,
                col=col,
            )

    fig.update_layout(
        title={"text": "Branching Transition Graphs For Final Communities", "x": 0.5},
        template="plotly_white",
        height=980,
        width=1600,
        margin={"l": 60, "r": 35, "t": 90, "b": 45},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
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
        / "branching_transition_graphs.html"
    )
    parser = argparse.ArgumentParser(
        description="Visualize split/merge transition graphs around final communities."
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
