#!/usr/bin/env python3
"""Create interactive node-link network visualizations for spot checks."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
from plotly.io import to_html

from graph_matching import build_graph, edges_for_window, load_edges, make_windows


PALETTE = [
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#9333ea",
    "#ea580c",
    "#0891b2",
    "#be123c",
    "#4f46e5",
    "#65a30d",
    "#c026d3",
    "#0f766e",
    "#b45309",
    "#7c3aed",
    "#0284c7",
    "#475569",
    "#db2777",
    "#059669",
    "#ca8a04",
    "#1d4ed8",
    "#991b1b",
]


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "dataset" / "email-Eu-core-temporal.txt").exists():
            return candidate

    return Path(__file__).resolve().parent


STATUS_STYLE = {
    "stable": {"color": "#2563eb", "symbol": "circle", "label": "Stable members"},
    "new": {"color": "#16a34a", "symbol": "diamond", "label": "New members"},
    "departed": {"color": "#dc2626", "symbol": "x", "label": "Departed members"},
}


def color_for_id(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return PALETTE[int(digest[:8], 16) % len(PALETTE)]


def load_communities(path: Path) -> pd.DataFrame:
    communities = pd.read_csv(path)
    communities["nodes"] = communities["nodes_json"].apply(json.loads)
    return communities


def edge_trace(graph: nx.Graph, pos: dict[int, tuple[float, float]]) -> go.Scatter:
    x_values = []
    y_values = []
    hover_values = []
    for source, target, attrs in graph.edges(data=True):
        x_values.extend([pos[source][0], pos[target][0], None])
        y_values.extend([pos[source][1], pos[target][1], None])
        hover_values.extend([f"{source} - {target}<br>weight={attrs.get('weight', 1)}", "", None])

    return go.Scatter(
        x=x_values,
        y=y_values,
        mode="lines",
        line={"width": 0.55, "color": "rgba(80, 91, 112, 0.24)"},
        hoverinfo="text",
        text=hover_values,
        name="Email edges",
        showlegend=False,
    )


def select_focus_community(communities: pd.DataFrame, focus_community: str | None) -> str:
    if focus_community:
        return focus_community

    first_snapshot = communities["snapshot_index"].min()
    first_communities = communities.loc[communities["snapshot_index"] == first_snapshot]
    if first_communities.empty:
        raise ValueError("No communities available to visualize.")

    largest = first_communities.sort_values(["size", "local_id"], ascending=[False, True]).iloc[0]
    return str(largest["persistent_id"])


def focus_group_at_snapshot(communities: pd.DataFrame, snapshot_index: int, focus_community: str) -> dict | None:
    rows = communities.loc[
        (communities["snapshot_index"] == snapshot_index)
        & (communities["persistent_id"].astype(str) == str(focus_community))
    ]
    if rows.empty:
        return None

    row = rows.sort_values(["size", "local_id"], ascending=[False, True]).iloc[0]
    return {
        "local_id": int(row["local_id"]),
        "persistent_id": str(row["persistent_id"]),
        "size": int(row["size"]),
        "nodes": [int(node) for node in row["nodes"]],
    }


def member_trace(
    graph: nx.Graph,
    pos: dict[int, tuple[float, float]],
    group: dict,
    nodes: set[int],
    status: str,
) -> go.Scatter:
    visible_nodes = sorted(node for node in nodes if node in graph and node in pos)
    degrees = dict(graph.degree(weight="weight"))
    style = STATUS_STYLE[status]
    return go.Scatter(
        x=[pos[node][0] for node in visible_nodes],
        y=[pos[node][1] for node in visible_nodes],
        mode="markers",
        marker={
            "size": [10 + min(24, degrees.get(node, 0) * 0.7) for node in visible_nodes],
            "color": style["color"],
            "symbol": style["symbol"],
            "line": {"width": 0.8, "color": "#111827"},
            "opacity": 0.92,
        },
        text=[
            "User {node}<br>{status}<br>{pid}<br>community={cid}<br>community size={size}<br>weighted degree={degree}".format(
                node=node,
                status=style["label"],
                pid=group["persistent_id"],
                cid=group["local_id"],
                size=group["size"],
                degree=round(degrees.get(node, 0), 2),
            )
            for node in visible_nodes
        ],
        hoverinfo="text",
        name=f"{style['label']} ({len(visible_nodes)})",
        legendgroup=status,
        showlegend=True,
    )


def make_network_frame(
    graph: nx.Graph,
    communities: pd.DataFrame,
    snapshot_index: int,
    focus_community: str,
    max_nodes: int,
    seed: int,
) -> tuple[list[go.Scatter], str]:
    group = focus_group_at_snapshot(communities, snapshot_index, focus_community)
    previous_group = focus_group_at_snapshot(communities, snapshot_index - 1, focus_community)
    if group is None:
        empty = go.Scatter(
            x=[],
            y=[],
            mode="markers",
            name=f"{focus_community} absent",
            showlegend=True,
            hoverinfo="skip",
        )
        return [empty], f"{focus_community} is not present in this snapshot"

    current_nodes = set(group["nodes"])
    previous_nodes = set(previous_group["nodes"]) if previous_group else set()
    stable_nodes = current_nodes & previous_nodes if previous_group else set(current_nodes)
    new_nodes = current_nodes - previous_nodes if previous_group else set()
    departed_nodes = previous_nodes - current_nodes
    visible_node_pool = current_nodes | departed_nodes

    graph = graph.copy()
    graph.add_nodes_from(visible_node_pool)
    focus_graph = graph.subgraph(visible_node_pool).copy()

    if focus_graph.number_of_nodes() > max_nodes:
        ranked_nodes = sorted(focus_graph.degree(weight="weight"), key=lambda item: item[1], reverse=True)
        keep_nodes = {node for node, _ in ranked_nodes[:max_nodes]}
        focus_graph = focus_graph.subgraph(keep_nodes).copy()
        stable_nodes &= keep_nodes
        new_nodes &= keep_nodes
        departed_nodes &= keep_nodes

    if focus_graph.number_of_nodes() == 0:
        return [], f"{focus_community} has no visible nodes in this snapshot"

    pos = nx.spring_layout(focus_graph, seed=seed, weight="weight", k=0.45, iterations=110)
    traces: list[go.Scatter] = [edge_trace(focus_graph, pos)]
    traces.append(member_trace(focus_graph, pos, group, stable_nodes, "stable"))
    traces.append(member_trace(focus_graph, pos, group, new_nodes, "new"))
    if previous_group:
        departed_group = {**group, "local_id": previous_group["local_id"], "size": previous_group["size"]}
        traces.append(member_trace(focus_graph, pos, departed_group, departed_nodes, "departed"))

    note = (
        f"{focus_community}, local community C{group['local_id']}, "
        f"{len(stable_nodes)} stable, {len(new_nodes)} new, {len(departed_nodes)} departed, "
        f"{focus_graph.number_of_nodes()} displayed nodes, {focus_graph.number_of_edges()} visible weighted edges"
    )
    hidden_count = len(visible_node_pool) - focus_graph.number_of_nodes()
    if hidden_count > 0:
        note += f", {hidden_count} nodes hidden by max-nodes"
    return traces, note


def build_interactive_network_figure(
    approach: str,
    edges: pd.DataFrame,
    windows: list,
    communities: pd.DataFrame,
    focus_community: str,
    max_nodes: int,
    max_snapshots: int,
    seed: int,
) -> go.Figure:
    windows = windows[:max_snapshots]
    frames = []
    frame_notes: dict[int, str] = {}

    for window in windows:
        graph = build_graph(edges_for_window(edges, window))
        traces, note = make_network_frame(graph, communities, window.index, focus_community, max_nodes, seed)
        frame_notes[window.index] = note
        frames.append(go.Frame(data=traces, name=str(window.index)))

    if not frames:
        return go.Figure()

    first_window = windows[0]
    fig = go.Figure(data=frames[0].data, frames=frames)
    fig.update_layout(
        title=(
            f"{approach.title()} Focused Community Evolution: {focus_community}<br>"
            f"<sup>Use the slider to follow this one persistent community over time. "
            f"{frame_notes[first_window.index]}</sup>"
        ),
        showlegend=True,
        legend={"title": {"text": "Member status"}, "itemsizing": "constant", "font": {"size": 10}},
        hovermode="closest",
        margin={"l": 20, "r": 260, "t": 90, "b": 40},
        width=1280,
        height=850,
        plot_bgcolor="#ffffff",
        xaxis={"visible": False},
        yaxis={"visible": False},
        sliders=[
            {
                "active": 0,
                "currentvalue": {"prefix": "Snapshot: "},
                "pad": {"t": 35},
                "steps": [
                    {
                        "label": f"{window.index}: {window.label}",
                        "method": "animate",
                        "args": [
                            [str(window.index)],
                            {"mode": "immediate", "frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}},
                        ],
                    }
                    for window in windows
                ],
            }
        ],
    )
    return fig


def build_approach_figure(args: argparse.Namespace, approach: str) -> tuple[str, go.Figure]:
    project_root = find_project_root()
    data_path = args.data or project_root / "dataset" / "email-Eu-core-temporal.txt"
    result_root = args.results / approach
    communities_path = result_root / "communities.csv"
    if not communities_path.exists():
        raise FileNotFoundError(f"Missing graph matching results for {approach}. Run graph_matching.py first.")

    communities = load_communities(communities_path)
    focus_community = select_focus_community(communities, args.focus_community)
    edges = load_edges(data_path, cutoff_days=args.cutoff_days)
    windows = make_windows(
        approach=approach,
        cutoff_days=args.cutoff_days,
        snapshot_days=args.snapshot_days,
        num_snapshots=args.num_snapshots,
        overlap_fraction=args.overlap_fraction,
    )
    fig = build_interactive_network_figure(
        approach=approach,
        edges=edges,
        windows=windows,
        communities=communities,
        focus_community=focus_community,
        max_nodes=args.max_nodes,
        max_snapshots=args.max_snapshots,
        seed=args.seed,
    )
    return focus_community, fig


def write_combined_html(figures: dict[str, tuple[str, go.Figure]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tabs = []
    panels = []
    for index, (approach, (focus_community, fig)) in enumerate(figures.items()):
        active = "active" if index == 0 else ""
        div = to_html(fig, include_plotlyjs=(index == 0), full_html=False)
        tabs.append(
            f"<button class=\"tab {active}\" data-tab=\"{approach}\" onclick=\"showTab('{approach}')\">"
            f"{approach.title()}<br><span>{escape(focus_community)}</span></button>"
        )
        panels.append(f'<section id="{approach}" class="panel {active}">{div}</section>')

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Focused Community Evolution</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f8fafc; color: #111827; }}
    header {{ padding: 18px 24px 8px; }}
    h1 {{ margin: 0 0 6px; font-size: 24px; }}
    p {{ margin: 0; color: #4b5563; }}
    .tabs {{ display: flex; gap: 8px; padding: 14px 24px; border-bottom: 1px solid #d1d5db; background: white; position: sticky; top: 0; z-index: 10; }}
    .tab {{ border: 1px solid #cbd5e1; background: #f8fafc; padding: 10px 14px; border-radius: 8px; cursor: pointer; font-weight: 650; }}
    .tab span {{ font-size: 11px; font-weight: 500; color: #64748b; }}
    .tab.active {{ background: #111827; color: white; border-color: #111827; }}
    .tab.active span {{ color: #cbd5e1; }}
    .panel {{ display: none; padding: 18px 24px 30px; }}
    .panel.active {{ display: block; }}
  </style>
</head>
<body>
  <header>
    <h1>Focused Community Evolution</h1>
    <p>Each tab follows one persistent community through time. Blue circles are stable members, green diamonds are new members, and red x-marks are members that departed since the previous snapshot.</p>
  </header>
  <nav class="tabs">{''.join(tabs)}</nav>
  {''.join(panels)}
  <script>
    function showTab(id) {{
      document.querySelectorAll('.tab').forEach((el) => el.classList.remove('active'));
      document.querySelectorAll('.panel').forEach((el) => el.classList.remove('active'));
      document.querySelector(`button[data-tab="${{id}}"]`).classList.add('active');
      document.getElementById(id).classList.add('active');
      window.dispatchEvent(new Event('resize'));
    }}
  </script>
</body>
</html>
"""
    output_path.write_text(html)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create interactive node-link network visualizations.")
    parser.add_argument("--data", type=Path, default=None)
    parser.add_argument("--results", type=Path, default=Path("graph-matching/outputs/graph_matching"))
    parser.add_argument("--combined-output", type=Path, default=Path("graph-matching/outputs/visualizations/focused_community_evolution.html"))
    parser.add_argument("--approach", choices=["interval", "cumulative", "overlap", "all"], default="all")
    parser.add_argument("--cutoff-days", type=int, default=500)
    parser.add_argument("--snapshot-days", type=int, default=50)
    parser.add_argument("--num-snapshots", type=int, default=10)
    parser.add_argument("--overlap-fraction", type=float, default=0.5)
    parser.add_argument("--max-snapshots", type=int, default=20)
    parser.add_argument("--max-nodes", type=int, default=220)
    parser.add_argument("--focus-community", default=None, help="Persistent community id to follow, e.g. INTERVAL-0001. Defaults to the largest community in snapshot 0.")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    approaches = ["cumulative", "interval", "overlap"] if args.approach == "all" else [args.approach]
    figures = {approach: build_approach_figure(args, approach) for approach in approaches}
    write_combined_html(figures, args.combined_output)


if __name__ == "__main__":
    main()
