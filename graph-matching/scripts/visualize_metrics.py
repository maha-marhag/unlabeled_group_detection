#!/usr/bin/env python3
"""Compute and visualize temporal network/community metrics."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from graph_matching import build_graph, edges_for_window, find_project_root, load_edges, make_windows


# Load detected communities and decode their node lists from JSON.
def load_communities(path: Path) -> pd.DataFrame:
    communities = pd.read_csv(path)
    communities["nodes"] = communities["nodes_json"].apply(json.loads)
    return communities


# Return the mean of a list, using 0.0 for empty inputs.
def safe_mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


# Return the median of a list, using 0.0 for empty inputs.
def safe_median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2)


# Convert a community-size distribution into an entropy-based effective count.
def entropy_effective_count(sizes: list[int]) -> float:
    total = sum(sizes)
    if total == 0:
        return 0.0
    entropy = 0.0
    for size in sizes:
        p = size / total
        if p > 0:
            entropy -= p * math.log(p)
    return float(math.exp(entropy))


# Compute graph-level metrics for one snapshot graph.
def graph_metrics(graph: nx.Graph, communities: list[set[int]]) -> dict:
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    weighted_edge_sum = sum(float(data.get("weight", 1)) for _, _, data in graph.edges(data=True))

    if node_count == 0:
        return {
            "nodes": 0,
            "weighted_edges": 0,
            "edge_weight_sum": 0.0,
            "density": 0.0,
            "transitivity": 0.0,
            "avg_clustering": 0.0,
            "connected_components": 0,
            "largest_component_nodes": 0,
            "largest_component_share": 0.0,
            "avg_degree": 0.0,
            "avg_weighted_degree": 0.0,
            "modularity": 0.0,
        }

    components = list(nx.connected_components(graph))
    largest_component_nodes = max((len(component) for component in components), default=0)
    degree_values = [degree for _, degree in graph.degree()]
    weighted_degree_values = [degree for _, degree in graph.degree(weight="weight")]

    modularity = 0.0
    nonempty_communities = [set(community) & set(graph.nodes()) for community in communities if community]
    covered_nodes = set().union(*nonempty_communities) if nonempty_communities else set()
    missing_nodes = set(graph.nodes()) - covered_nodes
    modularity_partition = [community for community in nonempty_communities if community]
    modularity_partition.extend({node} for node in missing_nodes)
    if modularity_partition and edge_count > 0:
        modularity = float(nx.algorithms.community.quality.modularity(graph, modularity_partition, weight="weight"))

    return {
        "nodes": node_count,
        "weighted_edges": edge_count,
        "edge_weight_sum": weighted_edge_sum,
        "density": float(nx.density(graph)),
        "transitivity": float(nx.transitivity(graph)),
        "avg_clustering": float(nx.average_clustering(graph)),
        "connected_components": len(components),
        "largest_component_nodes": largest_component_nodes,
        "largest_component_share": largest_component_nodes / node_count,
        "avg_degree": safe_mean([float(value) for value in degree_values]),
        "avg_weighted_degree": safe_mean([float(value) for value in weighted_degree_values]),
        "modularity": modularity,
    }


# Compute community-level size and internal-density metrics for one snapshot.
def community_metrics(graph: nx.Graph, communities: list[set[int]]) -> dict:
    sizes = [len(community) for community in communities]
    total_memberships = sum(sizes)
    community_densities = []
    for community in communities:
        if len(community) < 2:
            community_densities.append(0.0)
            continue
        subgraph = graph.subgraph(community)
        community_densities.append(float(nx.density(subgraph)))

    largest_size = max(sizes, default=0)
    return {
        "communities": len(communities),
        "total_community_memberships": total_memberships,
        "mean_community_size": safe_mean([float(size) for size in sizes]),
        "median_community_size": safe_median([float(size) for size in sizes]),
        "max_community_size": largest_size,
        "min_community_size": min(sizes, default=0),
        "largest_community_share": largest_size / total_memberships if total_memberships else 0.0,
        "effective_communities": entropy_effective_count(sizes),
        "mean_internal_density": safe_mean(community_densities),
        "median_internal_density": safe_median(community_densities),
    }


# Rebuild graphs for one approach and return network/community metric tables.
def compute_metrics_for_approach(args: argparse.Namespace, approach: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    project_root = find_project_root()
    data_path = args.data or project_root / "dataset" / "email-Eu-core-temporal.txt"
    result_root = args.results / approach

    communities_path = result_root / "communities.csv"
    if not communities_path.exists():
        raise FileNotFoundError(f"Missing graph matching outputs for {approach}. Run graph_matching.py first.")

    edges = load_edges(data_path, cutoff_days=args.cutoff_days)
    communities_df = load_communities(communities_path)
    windows = make_windows(
        approach=approach,
        cutoff_days=args.cutoff_days,
        snapshot_days=args.snapshot_days,
        num_snapshots=args.num_snapshots,
        overlap_fraction=args.overlap_fraction,
    )

    network_rows = []
    community_rows = []
    for window in windows:
        snapshot_communities = communities_df.loc[communities_df["snapshot_index"] == window.index]
        communities = [set(nodes) for nodes in snapshot_communities["nodes"]]
        window_edges = edges_for_window(edges, window)
        graph = build_graph(window_edges)

        base = {
            "approach": approach,
            "snapshot_index": window.index,
            "snapshot_label": window.label,
            "start_day": window.start_day,
            "end_day": window.end_day,
            "temporal_edges": len(window_edges),
        }
        network_rows.append({**base, **graph_metrics(graph, communities)})
        community_rows.append({**base, **community_metrics(graph, communities)})

    return pd.DataFrame(network_rows), pd.DataFrame(community_rows)


# Add one metric line to a Plotly subplot.
def add_line(fig: go.Figure, df: pd.DataFrame, metric: str, row: int, col: int, label: str | None = None) -> None:
    fig.add_trace(
        go.Scatter(
            x=df["snapshot_index"],
            y=df[metric],
            mode="lines+markers",
            name=label or metric,
            hovertemplate="snapshot=%{x}<br>%{y}<extra></extra>",
        ),
        row=row,
        col=col,
    )


# Build an optional Plotly dashboard figure from metric tables.
def build_dashboard(approach: str, network_df: pd.DataFrame, community_df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=3,
        cols=2,
        subplot_titles=[
            "Network Size",
            "Network Cohesion",
            "Connectivity",
            "Degree / Communication Volume",
            "Community Counts",
            "Community Size Distribution",
        ],
        specs=[
            [{"secondary_y": True}, {}],
            [{}, {"secondary_y": True}],
            [{}, {}],
        ],
        vertical_spacing=0.09,
        horizontal_spacing=0.09,
    )

    fig.add_trace(go.Scatter(x=network_df["snapshot_index"], y=network_df["nodes"], mode="lines+markers", name="nodes"), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=network_df["snapshot_index"], y=network_df["weighted_edges"], mode="lines+markers", name="unique edges"), row=1, col=1, secondary_y=True)
    add_line(fig, network_df, "density", 1, 2, "density")
    add_line(fig, network_df, "transitivity", 1, 2, "transitivity")
    add_line(fig, network_df, "avg_clustering", 1, 2, "avg clustering")
    add_line(fig, network_df, "connected_components", 2, 1, "components")
    add_line(fig, network_df, "largest_component_share", 2, 1, "largest component share")
    fig.add_trace(go.Scatter(x=network_df["snapshot_index"], y=network_df["avg_degree"], mode="lines+markers", name="avg degree"), row=2, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(x=network_df["snapshot_index"], y=network_df["edge_weight_sum"], mode="lines+markers", name="email volume"), row=2, col=2, secondary_y=True)
    add_line(fig, community_df, "communities", 3, 1, "communities")
    add_line(fig, community_df, "effective_communities", 3, 1, "effective communities")
    add_line(fig, community_df, "mean_community_size", 3, 2, "mean size")
    add_line(fig, community_df, "median_community_size", 3, 2, "median size")
    add_line(fig, community_df, "max_community_size", 3, 2, "max size")

    fig.update_layout(
        title=f"{approach.title()} Evolution Metrics Dashboard",
        height=1000,
        width=1450,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.12, "xanchor": "left", "x": 0},
        margin={"l": 60, "r": 60, "t": 90, "b": 140},
    )
    fig.update_xaxes(title_text="snapshot index")
    fig.update_yaxes(title_text="nodes", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="edges", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="email volume", row=2, col=2, secondary_y=True)
    return fig


# Compute metrics and package them with a dashboard figure for one approach.
def build_metric_dashboard_for_approach(args: argparse.Namespace, approach: str) -> tuple[pd.DataFrame, pd.DataFrame, go.Figure]:
    network_df, community_df = compute_metrics_for_approach(args, approach)
    fig = build_dashboard(approach, network_df, community_df)
    return network_df, community_df, fig


# Parse command-line options for metric calculation.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize temporal network and community metrics.")
    parser.add_argument("--data", type=Path, default=None)
    parser.add_argument("--results", type=Path, default=Path("graph-matching/outputs/graph_matching"))
    parser.add_argument("--approach", choices=["interval", "cumulative", "overlap", "all"], default="all")
    parser.add_argument("--cutoff-days", type=int, default=526)
    parser.add_argument("--snapshot-days", type=int, default=50)
    parser.add_argument("--num-snapshots", type=int, default=None)
    parser.add_argument("--overlap-fraction", type=float, default=0.5)
    return parser.parse_args()


# Print metric row counts for the selected approach or all approaches.
def main() -> None:
    args = parse_args()
    approaches = ["cumulative", "interval", "overlap"] if args.approach == "all" else [args.approach]
    for approach in approaches:
        network_df, community_df, _ = build_metric_dashboard_for_approach(args, approach)
        print(f"{approach}: {len(network_df)} network rows, {len(community_df)} community rows")


if __name__ == "__main__":
    main()
