#!/usr/bin/env python3
"""Compare cumulative, interval, and overlap dynamic-group approaches."""

from __future__ import annotations

import argparse
import math
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "idp_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from graph_matching import find_project_root


APPROACHES = ["cumulative", "interval", "overlap"]
APPROACH_COLORS = {"cumulative": "#2563eb", "interval": "#ea580c", "overlap": "#059669"}
STAGE_TYPES = [
    "Erosion", "Turnover-Shrinkage", "Steady-Stability",
    "Fluid-Stability", "Organic-Growth", "Dynamic-Growth",
]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=False)


def split_ids(value: object) -> list[str]:
    return [item for item in str(value).split(";") if item]


def safe_mean(values) -> float:
    clean = [float(value) for value in values if value != "" and not pd.isna(value)]
    return float(np.mean(clean)) if clean else 0.0


def safe_median(values) -> float:
    clean = [float(value) for value in values if value != "" and not pd.isna(value)]
    return float(np.median(clean)) if clean else 0.0


def accepted_overlaps(overlaps: pd.DataFrame, threshold: float) -> pd.DataFrame:
    source = pd.to_numeric(overlaps["source_overlap_pct"])
    target = pd.to_numeric(overlaps["target_overlap_pct"])
    return overlaps.loc[(source >= threshold) | (target >= threshold)].copy()


def load_data(outputs: Path, approach: str) -> dict[str, pd.DataFrame]:
    stage_id = outputs / "stage_identification" / approach
    stage_analysis = outputs / "stage_analysis" / approach
    graph_matching = outputs / "graph_matching" / approach
    return {
        "snapshots": read_csv(graph_matching / "snapshot_stats.csv"),
        "identified": read_csv(stage_id / "identified_communities.csv"),
        "groups": read_csv(stage_id / "identity_groups.csv"),
        "transitions": read_csv(stage_id / "identity_transitions.csv"),
        "events": read_csv(stage_id / "community_events.csv"),
        "finals": read_csv(stage_id / "final_communities.csv"),
        "overlaps": read_csv(stage_id / "community_overlap_history.csv"),
        "classic": read_csv(stage_analysis / "classic_stage_segments.csv"),
        "event_based": read_csv(stage_analysis / "event_based_stage_segments.csv"),
    }


def mean_group_size_cv(identified: pd.DataFrame) -> float:
    values = []
    for _, rows in identified.groupby("identity_group"):
        sizes = pd.to_numeric(rows["size"]).to_numpy(dtype=float)
        if len(sizes) >= 2 and np.mean(sizes):
            values.append(float(np.std(sizes) / np.mean(sizes)))
    return safe_mean(values)


def dimension_a_row(approach: str, data: dict[str, pd.DataFrame], threshold: float) -> dict:
    snapshots, identified = data["snapshots"], data["identified"]
    groups, transitions = data["groups"], data["transitions"]
    events, finals = data["events"], data["finals"]
    accepted = accepted_overlaps(data["overlaps"], threshold)
    counts = Counter(events["event_type"])
    snapshot_count = len(snapshots)
    transition_count = snapshot_count - 1
    inherited = transitions.loc[transitions["decision"] == "inherited"]
    attachments = [len(split_ids(value)) for value in finals["events"]]
    return {
        "approach": approach,
        "snapshot_count": snapshot_count,
        "snapshot_transition_count": transition_count,
        "observation_group_count": len(identified),
        "all_identity_chain_count": len(groups),
        "final_group_count": len(finals),
        "dead_identity_chain_count": int((groups["status"] == "dead").sum()),
        "mean_observation_group_size": safe_mean(identified["size"]),
        "median_observation_group_size": safe_median(identified["size"]),
        "mean_final_group_size": safe_mean(finals["final_size"]),
        "mean_identity_lifespan_snapshots": safe_mean(groups["lifespan_snapshots"]),
        "mean_identity_lifespan_share": safe_mean(pd.to_numeric(groups["lifespan_snapshots"]) / snapshot_count),
        "mean_within_chain_size_cv": mean_group_size_cv(identified),
        "birth_event_count": counts["birth"],
        "continuation_event_count": counts["continuation"],
        "split_event_count": counts["split"],
        "merge_event_count": counts["merge"],
        "death_event_count": counts["death"],
        "split_events_per_transition": counts["split"] / transition_count,
        "merge_events_per_transition": counts["merge"] / transition_count,
        "split_events_per_100_observations": 100 * counts["split"] / len(identified),
        "merge_events_per_100_observations": 100 * counts["merge"] / len(identified),
        "accepted_relation_count": len(accepted),
        "mean_accepted_jaccard": safe_mean(accepted["jaccard"]),
        "median_accepted_jaccard": safe_median(accepted["jaccard"]),
        "mean_inherited_jaccard": safe_mean(inherited["jaccard"]),
        "final_group_event_involvement_count": sum(attachments),
        "mean_event_involvements_per_final_group": safe_mean(attachments),
    }


def build_lineage_graph(identified: pd.DataFrame, overlaps: pd.DataFrame, threshold: float) -> nx.DiGraph:
    graph = nx.DiGraph()
    for _, row in identified.iterrows():
        graph.add_node(row["observation_id"], snapshot=int(row["snapshot_index"]),
                       local_id=int(row["local_id"]), identity_group=row["identity_group"],
                       size=int(row["size"]))
    for _, row in accepted_overlaps(overlaps, threshold).iterrows():
        source, target = row["source_observation_id"], row["target_observation_id"]
        if source in graph and target in graph:
            graph.add_edge(source, target, overlap_size=int(row["overlap_size"]),
                           jaccard=float(row["jaccard"]),
                           prospective_stability=float(row["source_overlap_pct"]),
                           retrospective_stability=float(row["target_overlap_pct"]))
    return graph


def graph_depths(graph: nx.DiGraph) -> dict[str, int]:
    depths = {}
    for node in nx.topological_sort(graph):
        parents = list(graph.predecessors(node))
        depths[node] = 0 if not parents else max(depths[parent] + 1 for parent in parents)
    return depths


def lineage_coordinates(graph: nx.DiGraph) -> tuple[dict, dict]:
    components = sorted(
        (set(nodes) for nodes in nx.weakly_connected_components(graph)),
        key=lambda nodes: min((graph.nodes[n]["snapshot"], graph.nodes[n]["local_id"], n) for n in nodes),
    )
    positions, component_ids = {}, {}
    y_cursor = 0.0
    for component_index, nodes in enumerate(components, start=1):
        by_snapshot = defaultdict(list)
        for node in nodes:
            by_snapshot[graph.nodes[node]["snapshot"]].append(node)
            component_ids[node] = component_index
        for snapshot in by_snapshot:
            by_snapshot[snapshot].sort(key=lambda n: (graph.nodes[n]["local_id"], n))

        # Repeated forward/backward barycentric passes reduce crossings while
        # retaining a deterministic time-layer layout.
        ordered_snapshots = sorted(by_snapshot)
        for _ in range(6):
            for snapshot in ordered_snapshots[1:]:
                previous_positions = {
                    node: index for index, node in enumerate(by_snapshot[snapshot - 1])
                }
                current_positions = {node: index for index, node in enumerate(by_snapshot[snapshot])}
                by_snapshot[snapshot].sort(
                    key=lambda node: (
                        safe_mean(previous_positions[parent] for parent in graph.predecessors(node))
                        if list(graph.predecessors(node)) else current_positions[node],
                        graph.nodes[node]["local_id"],
                        node,
                    )
                )
            for snapshot in reversed(ordered_snapshots[:-1]):
                next_positions = {
                    node: index for index, node in enumerate(by_snapshot[snapshot + 1])
                }
                current_positions = {node: index for index, node in enumerate(by_snapshot[snapshot])}
                by_snapshot[snapshot].sort(
                    key=lambda node: (
                        safe_mean(next_positions[child] for child in graph.successors(node))
                        if list(graph.successors(node)) else current_positions[node],
                        graph.nodes[node]["local_id"],
                        node,
                    )
                )
        height = max(1.0, float(max(len(layer) for layer in by_snapshot.values())))
        center = y_cursor + height / 2
        for snapshot, layer in by_snapshot.items():
            ordered = layer
            offset = (len(ordered) - 1) / 2
            for index, node in enumerate(ordered):
                positions[node] = (float(snapshot), center + index - offset)
        y_cursor += height + 1.4
    return positions, component_ids


def dimension_b_row(approach: str, graph: nx.DiGraph) -> dict:
    depths = graph_depths(graph)
    components = [graph.subgraph(nodes).copy() for nodes in nx.weakly_connected_components(graph)]
    snapshots = sorted({data["snapshot"] for _, data in graph.nodes(data=True)})
    widths = [sum(data["snapshot"] == t for _, data in graph.nodes(data=True)) for t in snapshots]
    split_nodes = [node for node in graph if graph.out_degree(node) > 1]
    merge_nodes = [node for node in graph if graph.in_degree(node) > 1]
    sizes = [component.number_of_nodes() for component in components]
    return {
        "approach": approach,
        "observation_nodes": graph.number_of_nodes(),
        "accepted_edges": graph.number_of_edges(),
        "start_snapshot_nodes": sum(data["snapshot"] == min(snapshots) for _, data in graph.nodes(data=True)),
        "end_snapshot_nodes": sum(data["snapshot"] == max(snapshots) for _, data in graph.nodes(data=True)),
        "root_nodes": sum(graph.in_degree(node) == 0 for node in graph),
        "terminal_nodes": sum(graph.out_degree(node) == 0 for node in graph),
        "split_nodes": len(split_nodes),
        "merge_nodes": len(merge_nodes),
        "split_branch_excess": sum(graph.out_degree(node) - 1 for node in split_nodes),
        "merge_branch_excess": sum(graph.in_degree(node) - 1 for node in merge_nodes),
        "weakly_connected_components": len(components),
        "largest_component_nodes": max(sizes, default=0),
        "largest_component_share": max(sizes, default=0) / graph.number_of_nodes(),
        "mean_component_nodes": safe_mean(sizes),
        "max_depth_edges": max(depths.values(), default=0),
        "mean_node_depth": safe_mean(depths.values()),
        "mean_component_depth_edges": safe_mean(nx.dag_longest_path_length(c) for c in components),
        "max_snapshot_breadth": max(widths, default=0),
        "mean_snapshot_breadth": safe_mean(widths),
        "mean_observation_size": safe_mean(data["size"] for _, data in graph.nodes(data=True)),
    }


def network_rows(approach: str, graph: nx.DiGraph, positions: dict, component_ids: dict) -> tuple[list, list]:
    nodes, edges = [], []
    for node in sorted(graph, key=lambda n: (graph.nodes[n]["snapshot"], graph.nodes[n]["local_id"])):
        data = graph.nodes[node]
        terminal = graph.out_degree(node) == 0
        final_label = data["identity_group"] if terminal and str(data["identity_group"]).startswith("c") else ""
        label = str(data["local_id"]) + (f"→{final_label or 'dead'}" if terminal else "")
        x, y = positions[node]
        nodes.append({"approach": approach, "observation_id": node, "snapshot_index": data["snapshot"],
                      "local_id": data["local_id"], "identity_group": data["identity_group"],
                      "size": data["size"], "in_degree": graph.in_degree(node),
                      "out_degree": graph.out_degree(node), "component_id": component_ids[node],
                      "x": x, "y": y, "display_label": label})
    for source, target, data in graph.edges(data=True):
        structure = ("split_merge" if graph.out_degree(source) > 1 and graph.in_degree(target) > 1
                     else "split" if graph.out_degree(source) > 1
                     else "merge" if graph.in_degree(target) > 1 else "one_to_one")
        edges.append({"approach": approach, "source_observation_id": source,
                      "target_observation_id": target, "event_structure": structure, **data})
    return nodes, edges


def plot_lineage(approach: str, graph: nx.DiGraph, positions: dict, output_dir: Path) -> None:
    height = max(8.0, min(40.0, 0.12 * graph.number_of_nodes()))
    width = max(16.0, 0.9 * len({data["snapshot"] for _, data in graph.nodes(data=True)}))
    fig, ax = plt.subplots(figsize=(width, height))
    for source, target in graph.edges():
        x0, y0 = positions[source]; x1, y1 = positions[target]
        color = "#dc2626" if graph.out_degree(source) > 1 or graph.in_degree(target) > 1 else "#94a3b8"
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops={"arrowstyle": "->", "color": color, "lw": 0.8, "alpha": 0.75}, zorder=1)
    ax.scatter([positions[n][0] for n in graph], [positions[n][1] for n in graph],
               s=[18 + math.sqrt(graph.nodes[n]["size"]) * 5 for n in graph],
               c=["#dc2626" if graph.out_degree(n) > 1 else "#7c3aed" if graph.in_degree(n) > 1
                  else APPROACH_COLORS[approach] for n in graph],
               edgecolors="white", linewidths=0.5, zorder=2)
    for node in graph:
        data = graph.nodes[node]; terminal = graph.out_degree(node) == 0
        final = data["identity_group"] if str(data["identity_group"]).startswith("c") else "dead"
        label = str(data["local_id"]) + (f"→{final}" if terminal else "")
        x, y = positions[node]
        ax.text(x, y + 0.15, label, fontsize=4.8, ha="center", va="bottom", zorder=3)
    ax.set_title(f"{approach.title()} complete dynamic-group lineage network")
    ax.set_xlabel("Snapshot index (x coordinate)")
    ax.set_ylabel("Component/layer position (y coordinate)")
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.7); ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(output_dir / f"network_{approach}.png", dpi=220)
    fig.savefig(output_dir / f"network_{approach}.pdf")
    plt.close(fig)


def stage_distribution_rows(approach: str, method: str, stages: pd.DataFrame) -> list[dict]:
    total_count = len(stages)
    durations = pd.to_numeric(stages["t_end"]) - pd.to_numeric(stages["t_start"])
    total_duration = float(durations.sum())
    groups = sorted(stages["identity_group"].unique())
    group_shares = defaultdict(list)
    for group in groups:
        frame = stages.loc[stages["identity_group"] == group]
        group_durations = pd.to_numeric(frame["t_end"]) - pd.to_numeric(frame["t_start"])
        denominator = float(group_durations.sum())
        for stage_type in STAGE_TYPES:
            numerator = float(group_durations.loc[frame["stage_type"] == stage_type].sum())
            group_shares[stage_type].append(numerator / denominator if denominator else 0.0)
    rows = []
    for stage_type in STAGE_TYPES:
        selected = stages.loc[stages["stage_type"] == stage_type]
        selected_duration = pd.to_numeric(selected["t_end"]) - pd.to_numeric(selected["t_start"])
        count_share = len(selected) / total_count if total_count else 0.0
        duration_share = float(selected_duration.sum()) / total_duration if total_duration else 0.0
        rows.append({"approach": approach, "method": method, "stage_type": stage_type,
                     "stage_count": len(selected), "stage_count_share": count_share,
                     "transition_duration": int(selected_duration.sum()),
                     "transition_duration_share": duration_share,
                     "count_duration_index": (count_share + duration_share) / 2,
                     "mean_stage_length_snapshots": safe_mean(selected["length"]),
                     "mean_group_transition_share": safe_mean(group_shares[stage_type]),
                     "groups_with_stage": int(selected["identity_group"].nunique()),
                     "group_prevalence": selected["identity_group"].nunique() / len(groups) if groups else 0.0})
    return rows


def stage_maps(stages: pd.DataFrame) -> dict[str, list[dict]]:
    return {group: rows.sort_values(["t_start", "t_end"]).to_dict("records")
            for group, rows in stages.groupby("identity_group")}


def stage_for_transition(stages: list[dict], start: int) -> str:
    for stage in stages:
        if int(stage["t_start"]) <= start and int(stage["t_end"]) >= start + 1:
            return str(stage["stage_type"])
    return ""


def is_boundary(stages: list[dict], snapshot: int) -> bool:
    return (any(int(row["t_end"]) == snapshot for row in stages)
            and any(int(row["t_start"]) == snapshot for row in stages))


def stage_method_summary(approach: str, method: str, stages: pd.DataFrame) -> dict:
    durations = pd.to_numeric(stages["t_end"]) - pd.to_numeric(stages["t_start"])
    groups = stages["identity_group"].nunique()
    return {"approach": approach, "method": method, "analyzed_group_count": groups,
            "stage_count": len(stages), "mean_stages_per_group": len(stages) / groups,
            "mean_stage_length_snapshots": safe_mean(stages["length"]),
            "median_stage_length_snapshots": safe_median(stages["length"]),
            "total_transition_duration": int(durations.sum())}


def compare_stage_methods(approach: str, classic: pd.DataFrame, event_based: pd.DataFrame) -> dict:
    classic_map, event_map = stage_maps(classic), stage_maps(event_based)
    agreements, classic_boundaries, event_boundaries = [], set(), set()
    groups = sorted(set(classic_map) & set(event_map))
    for group in groups:
        all_rows = classic_map[group] + event_map[group]
        for snapshot in range(min(int(r["t_start"]) for r in all_rows), max(int(r["t_end"]) for r in all_rows)):
            left = stage_for_transition(classic_map[group], snapshot)
            right = stage_for_transition(event_map[group], snapshot)
            if left and right:
                agreements.append(left == right)
        classic_boundaries.update((group, t) for t in {int(r["t_start"]) for r in classic_map[group]}
                                  if is_boundary(classic_map[group], t))
        event_boundaries.update((group, t) for t in {int(r["t_start"]) for r in event_map[group]}
                                if is_boundary(event_map[group], t))
    intersection = classic_boundaries & event_boundaries
    union = classic_boundaries | event_boundaries
    return {"approach": approach, "groups_compared": len(groups),
            "transition_labels_compared": len(agreements),
            "same_stage_type_transition_count": sum(agreements),
            "stage_type_agreement_rate": safe_mean(agreements),
            "classic_internal_boundary_count": len(classic_boundaries),
            "event_internal_boundary_count": len(event_boundaries),
            "shared_boundary_count": len(intersection),
            "boundary_jaccard": len(intersection) / len(union) if union else 1.0,
            "event_boundary_precision_vs_classic": len(intersection) / len(event_boundaries) if event_boundaries else 0.0,
            "event_boundary_recall_vs_classic": len(intersection) / len(classic_boundaries) if classic_boundaries else 0.0}


def event_stage_associations(approach: str, data: dict[str, pd.DataFrame]) -> list[dict]:
    observation_group = dict(zip(data["identified"]["observation_id"], data["identified"]["identity_group"]))
    methods = {"classic": stage_maps(data["classic"]), "event_based": stage_maps(data["event_based"])}
    rows = []
    for _, event in data["events"].iterrows():
        if event["event_type"] not in {"split", "merge"}:
            continue
        snapshot = int(event["to_snapshot"])
        participants = set(split_ids(event["source_observation_ids"])) | set(split_ids(event["target_observation_ids"]))
        groups = sorted({observation_group[item] for item in participants
                         if item in observation_group and str(observation_group[item]).startswith("c")})
        for group in groups:
            for method, mapping in methods.items():
                stages = mapping.get(group, [])
                if not stages:
                    continue
                pre_type = stage_for_transition(stages, snapshot - 1)
                post_type = stage_for_transition(stages, snapshot)
                boundary_context = (
                    "internal" if pre_type and post_type
                    else "group_start" if post_type
                    else "group_end" if pre_type
                    else "outside_analyzed_lifespan"
                )
                rows.append({"approach": approach, "method": method, "event_id": event["event_id"],
                             "event_type": event["event_type"], "identity_group": group,
                             "event_snapshot": snapshot, "is_stage_boundary": is_boundary(stages, snapshot),
                             "pre_event_stage_type": pre_type, "post_event_stage_type": post_type,
                             "stage_type_changed": bool(pre_type and post_type and pre_type != post_type),
                             "post_stage_available": bool(post_type), "boundary_context": boundary_context})
    return rows


def cramers_v(frame: pd.DataFrame) -> float:
    table = pd.crosstab(frame["event_type"], frame["post_event_stage_type"])
    if table.empty or min(table.shape) < 2:
        return 0.0
    observed = table.to_numpy(dtype=float); total = observed.sum()
    expected = observed.sum(axis=1, keepdims=True) @ observed.sum(axis=0, keepdims=True) / total
    chi_square = float(np.sum(np.divide((observed - expected) ** 2, expected,
                                        out=np.zeros_like(expected), where=expected > 0)))
    denominator = total * min(table.shape[0] - 1, table.shape[1] - 1)
    return math.sqrt(chi_square / denominator) if denominator else 0.0


def summarize_event_associations(associations: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (approach, method), method_frame in associations.groupby(["approach", "method"]):
        available_all = method_frame.loc[method_frame["post_stage_available"] == True]  # noqa: E712
        association = cramers_v(available_all)
        for event_type, frame in method_frame.groupby("event_type"):
            available = frame.loc[frame["post_stage_available"] == True]  # noqa: E712
            internal = frame.loc[frame["boundary_context"] == "internal"]
            for stage_type in STAGE_TYPES:
                count = int((available["post_event_stage_type"] == stage_type).sum())
                rows.append({"approach": approach, "method": method, "event_type": event_type,
                             "post_stage_type": stage_type, "event_group_involvement_count": len(frame),
                             "stage_boundary_count": int(frame["is_stage_boundary"].sum()),
                             "stage_boundary_rate": safe_mean(frame["is_stage_boundary"]),
                             "internal_event_group_involvement_count": len(internal),
                             "internal_stage_boundary_count": int(internal["is_stage_boundary"].sum()),
                             "internal_stage_boundary_rate": safe_mean(internal["is_stage_boundary"]),
                             "group_start_event_count": int((frame["boundary_context"] == "group_start").sum()),
                             "group_end_event_count": int((frame["boundary_context"] == "group_end").sum()),
                             "post_stage_available_count": len(available), "post_stage_count": count,
                             "post_stage_likelihood": count / len(available) if len(available) else 0.0,
                             "stage_type_change_rate": safe_mean(internal["stage_type_changed"]),
                             "event_type_post_stage_cramers_v": association})
    return pd.DataFrame(rows)


def grouped_plot(summary: pd.DataFrame, specs: list[tuple[str, str]], output: Path) -> None:
    fig, axes = plt.subplots(1, len(specs), figsize=(5.3 * len(specs), 4.6))
    axes = np.atleast_1d(axes)
    labels = [value.title() for value in summary["approach"]]
    colors = [APPROACH_COLORS[value] for value in summary["approach"]]
    for ax, (metric, title) in zip(axes, specs):
        ax.bar(labels, summary[metric], color=colors)
        ax.set_title(title, fontsize=10); ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", color="#e5e7eb"); ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(output, dpi=200); plt.close(fig)


def plot_group_size_and_jaccard(data_by_approach: dict[str, dict], threshold: float, output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8))
    jaccard_values = []
    for approach in APPROACHES:
        data = data_by_approach[approach]
        identified = data["identified"].copy()
        snapshot_days = data["snapshots"][["snapshot_index", "end_day"]].copy()
        frame = identified.groupby("snapshot_index")["size"].agg(
            mean="mean", median="median",
            q25=lambda values: values.quantile(.25),
            q75=lambda values: values.quantile(.75),
        ).reset_index().merge(snapshot_days, on="snapshot_index")
        axes[0].plot(frame["end_day"], frame["mean"], marker="o", markersize=3,
                     label=f"{approach.title()} mean", color=APPROACH_COLORS[approach])
        axes[0].fill_between(frame["end_day"], frame["q25"], frame["q75"],
                             color=APPROACH_COLORS[approach], alpha=.12)
        jaccard_values.append(accepted_overlaps(data["overlaps"], threshold)["jaccard"].astype(float))
    axes[0].set_title("Observation-group size over time")
    axes[0].set_xlabel("Window end day")
    axes[0].set_ylabel("Members (line=mean, band=IQR)")
    axes[0].legend(fontsize=8)
    axes[0].grid(color="#e5e7eb"); axes[0].set_axisbelow(True)
    axes[1].boxplot(jaccard_values, tick_labels=[value.title() for value in APPROACHES],
                    patch_artist=True,
                    boxprops={"facecolor": "#cbd5e1"}, medianprops={"color": "#dc2626"})
    axes[1].set_title("Accepted-relation Jaccard distributions")
    axes[1].set_ylabel("Jaccard")
    axes[1].set_ylim(0, 1)
    axes[1].grid(axis="y", color="#e5e7eb"); axes[1].set_axisbelow(True)
    fig.tight_layout(); fig.savefig(output, dpi=200); plt.close(fig)


def plot_stage_distribution(distribution: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(15, 11), sharey=True)
    for row, approach in enumerate(APPROACHES):
        for col, method in enumerate(["classic", "event_based"]):
            ax = axes[row, col]
            frame = distribution.loc[(distribution["approach"] == approach)
                                     & (distribution["method"] == method)].set_index("stage_type").reindex(STAGE_TYPES)
            x = np.arange(len(STAGE_TYPES))
            ax.bar(x - .18, frame["stage_count_share"], .36, label="Stage count share", color="#64748b")
            ax.bar(x + .18, frame["transition_duration_share"], .36, label="Duration share",
                   color=APPROACH_COLORS[approach])
            ax.set_title(f"{approach.title()} — {method.replace('_', ' ').title()}")
            ax.set_xticks(x, [value.replace("-", "\n") for value in STAGE_TYPES], fontsize=7)
            ax.set_ylim(0, .75); ax.grid(axis="y", color="#e5e7eb"); ax.set_axisbelow(True)
    axes[0, 0].legend(fontsize=8); axes[0, 1].legend(fontsize=8)
    fig.supylabel("Share"); fig.tight_layout(); fig.savefig(output, dpi=200); plt.close(fig)


def plot_event_stage_likelihoods(summary: pd.DataFrame, output: Path) -> None:
    row_keys = [(approach, method, event_type) for approach in APPROACHES
                for method in ["classic", "event_based"] for event_type in ["split", "merge"]]
    matrix = np.zeros((len(row_keys), len(STAGE_TYPES)))
    for row_index, key in enumerate(row_keys):
        approach, method, event_type = key
        frame = summary.loc[(summary["approach"] == approach)
                            & (summary["method"] == method)
                            & (summary["event_type"] == event_type)].set_index("post_stage_type")
        for col_index, stage_type in enumerate(STAGE_TYPES):
            if stage_type in frame.index:
                matrix[row_index, col_index] = frame.loc[stage_type, "post_stage_likelihood"]
    fig, ax = plt.subplots(figsize=(12, 7.5))
    image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=max(.5, float(matrix.max())))
    ax.set_xticks(range(len(STAGE_TYPES)), [value.replace("-", "\n") for value in STAGE_TYPES], fontsize=8)
    ax.set_yticks(range(len(row_keys)),
                  [f"{a.title()} / {m.replace('_', ' ')} / {e}" for a, m, e in row_keys], fontsize=8)
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            ax.text(col, row, f"{matrix[row, col]:.0%}", ha="center", va="center", fontsize=7,
                    color="white" if matrix[row, col] > .3 else "#111827")
    ax.set_title("Stage type following split/merge involvement")
    fig.colorbar(image, ax=ax, label="Conditional likelihood")
    fig.tight_layout(); fig.savefig(output, dpi=200); plt.close(fig)


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    selected = frame[columns].copy()
    for column in selected:
        if pd.api.types.is_float_dtype(selected[column]):
            selected[column] = selected[column].map(lambda value: f"{value:.3f}")
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    lines += ["| " + " | ".join(str(value) for value in row) + " |"
              for row in selected.itertuples(index=False, name=None)]
    return "\n".join(lines)


def write_report(output_dir: Path, a: pd.DataFrame, b: pd.DataFrame, stage_summary: pd.DataFrame,
                 method_comparison: pd.DataFrame, event_summary: pd.DataFrame) -> None:
    erosion = event_summary.loc[event_summary["post_stage_type"] == "Erosion"]
    text = f"""# Comparison of cumulative, interval, and overlap approaches

## Scope and comparability

All outputs use the same 526-day dataset. Cumulative and interval use 11 snapshots with 50-day steps. Overlap uses 20 snapshots with 50-day windows and a 25-day stride. Raw totals therefore reflect both approach behavior and observation frequency. Normalized rates and proportions are the primary comparison measures.

Accepted lineage relations satisfy prospective stability >= 0.4 or retrospective stability >= 0.4. Every detected community at a snapshot is an observation node. Identity chains include final and intermediate/dead chains.

## Dimension A: dynamic-group and event information

{markdown_table(a, ["approach", "snapshot_count", "observation_group_count", "all_identity_chain_count", "final_group_count", "mean_observation_group_size", "split_event_count", "merge_event_count", "split_events_per_transition", "merge_events_per_transition", "mean_accepted_jaccard", "mean_inherited_jaccard"])}

![Dimension A comparison](dimension_a_comparison.png)

![Group size and Jaccard details](dimension_a_size_jaccard.png)

The full table is `dimension_a_summary.csv`. Final-group event involvement counts can count an event once for each participating final group, matching the earlier project table.

## Dimension B: complete lineage-network structure

{markdown_table(b, ["approach", "observation_nodes", "accepted_edges", "weakly_connected_components", "split_nodes", "merge_nodes", "start_snapshot_nodes", "end_snapshot_nodes", "max_depth_edges", "mean_component_depth_edges", "max_snapshot_breadth", "mean_observation_size"])}

![Dimension B comparison](dimension_b_comparison.png)

Each approach has a complete PNG/PDF network. Node x is snapshot index and node y is a deterministic component/layer coordinate. Nodes show local internal IDs; terminal nodes append their final label or `dead`. Red edges touch a structural split or merge. Exact coordinates and attributes are in `network_nodes.csv` and `network_edges.csv`.

## Dimension C: classic versus event-based stages

{markdown_table(stage_summary, ["approach", "method", "analyzed_group_count", "stage_count", "mean_stages_per_group", "mean_stage_length_snapshots", "total_transition_duration"])}

{markdown_table(method_comparison, ["approach", "groups_compared", "stage_type_agreement_rate", "classic_internal_boundary_count", "event_internal_boundary_count", "shared_boundary_count", "boundary_jaccard"])}

![Stage distributions](dimension_c_stage_distribution.png)

![Event-to-stage likelihoods](dimension_c_event_stage_likelihoods.png)

Stage count share and transition-duration share are separate. `count_duration_index` is their equal-weight descriptive average. Duration uses `t_end - t_start`, so shared boundary snapshots are not double-counted.

### Split/merge relationships with stages

{markdown_table(erosion, ["approach", "method", "event_type", "event_group_involvement_count", "internal_event_group_involvement_count", "internal_stage_boundary_rate", "post_stage_available_count", "post_stage_likelihood", "stage_type_change_rate", "event_type_post_stage_cramers_v"])}

`post_stage_likelihood` is the proportion of event/group involvements whose first valid transition after the event has the listed stage type. Final-snapshot cases have no post-event transition and are excluded from that denominator. `internal_stage_boundary_rate` considers only events with valid stages on both sides. Event-based segmentation uses every such internal split/merge as a boundary. The classic rate shows how often those same events coincide with independently detected size-based boundaries. Cramer's V measures association, not causation.

## Findings and recommendation

- **Cumulative gives the strongest apparent continuity but has the most historical inertia.** Its mean accepted Jaccard is {a.loc[a['approach'] == 'cumulative', 'mean_accepted_jaccard'].iloc[0]:.3f}, versus {a.loc[a['approach'] == 'interval', 'mean_accepted_jaccard'].iloc[0]:.3f} for interval and {a.loc[a['approach'] == 'overlap', 'mean_accepted_jaccard'].iloc[0]:.3f} for overlap. It also has the largest mean observation group size and the fewest split/merge events per transition. Because every snapshot retains all previous edges, this stability partly reflects construction rather than only social persistence.
- **Interval is the most fragmented and volatile.** It produces {a.loc[a['approach'] == 'interval', 'all_identity_chain_count'].iloc[0]:.0f} identity chains, has the lowest accepted and inherited Jaccard, and has the highest split and merge rates per transition. It responds to change but loses continuity at hard 50-day boundaries.
- **Overlap is the middle ground.** Its similarity and normalized split/merge rates fall between cumulative and interval. It retains the local 50-day horizon while reducing boundary discontinuity and provides 20 observation points. Its large component and 19-edge maximum depth show that it preserves long lineages without cumulative memory.
- Event-based stages are fewer and longer than classic stages for all approaches. Classic/event label agreement is {method_comparison.loc[method_comparison['approach'] == 'cumulative', 'stage_type_agreement_rate'].iloc[0]:.1%} for cumulative, {method_comparison.loc[method_comparison['approach'] == 'interval', 'stage_type_agreement_rate'].iloc[0]:.1%} for interval, and {method_comparison.loc[method_comparison['approach'] == 'overlap', 'stage_type_agreement_rate'].iloc[0]:.1%} for overlap. The lower overlap agreement means event boundaries capture different structure from size-only turning points; it is not a classifier mismatch.
- Split and merge events do not deterministically imply erosion. The erosion likelihoods are conditional descriptive rates and vary by approach/method. Event type alone has weak-to-moderate association with the following stage in the current sample, so events should remain boundary evidence rather than direct stage labels.

**Recommendation: continue with the overlap approach.** It offers the best balance of temporal continuity, sensitivity to change, and temporal resolution. Keep cumulative as a high-continuity reference and interval as a volatility reference. Before treating the choice as final, run the planned overlap sensitivity analysis at 20 and 50 snapshots and check whether normalized event rates, component structure, and stage distributions remain stable.

## Output guide

- `dimension_a_summary.csv`: group, event, size, lifespan, and similarity measures.
- `dimension_b_network_summary.csv`: lineage-network structure.
- `network_nodes.csv`: all node attributes and x/y coordinates.
- `network_edges.csv`: accepted lineage relations and structural edge types.
- `dimension_c_stage_method_summary.csv`: stage totals and lengths.
- `dimension_c_stage_type_distribution.csv`: count, duration, prevalence, and combined shares.
- `dimension_c_classic_event_comparison.csv`: boundary and label agreement.
- `dimension_c_event_stage_associations.csv`: event/group/method details.
- `dimension_c_event_stage_summary.csv`: event-to-stage likelihoods and Cramer's V.

## Interpretation rule

Use normalized rates and structural proportions when choosing an approach. Use raw totals to understand workload and graph scale. Do not rank the approaches solely by group or event totals because overlap currently has a finer temporal stride.
"""
    (output_dir / "README.md").write_text(text)


def run(outputs: Path, output_dir: Path, threshold: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    a_rows, b_rows, nodes, edges = [], [], [], []
    stage_rows, distributions, comparisons, associations = [], [], [], []
    data_by_approach = {}
    for approach in APPROACHES:
        data = load_data(outputs, approach)
        data_by_approach[approach] = data
        a_rows.append(dimension_a_row(approach, data, threshold))
        graph = build_lineage_graph(data["identified"], data["overlaps"], threshold)
        positions, component_ids = lineage_coordinates(graph)
        b_rows.append(dimension_b_row(approach, graph))
        node_data, edge_data = network_rows(approach, graph, positions, component_ids)
        nodes.extend(node_data); edges.extend(edge_data)
        plot_lineage(approach, graph, positions, output_dir)
        for method, stages in [("classic", data["classic"]), ("event_based", data["event_based"])]:
            stage_rows.append(stage_method_summary(approach, method, stages))
            distributions.extend(stage_distribution_rows(approach, method, stages))
        comparisons.append(compare_stage_methods(approach, data["classic"], data["event_based"]))
        associations.extend(event_stage_associations(approach, data))

    a, b = pd.DataFrame(a_rows), pd.DataFrame(b_rows)
    stage_summary, distribution = pd.DataFrame(stage_rows), pd.DataFrame(distributions)
    method_comparison, association_rows = pd.DataFrame(comparisons), pd.DataFrame(associations)
    association_summary = summarize_event_associations(association_rows)
    outputs_to_write = {
        "dimension_a_summary.csv": a, "dimension_b_network_summary.csv": b,
        "network_nodes.csv": pd.DataFrame(nodes), "network_edges.csv": pd.DataFrame(edges),
        "dimension_c_stage_method_summary.csv": stage_summary,
        "dimension_c_stage_type_distribution.csv": distribution,
        "dimension_c_classic_event_comparison.csv": method_comparison,
        "dimension_c_event_stage_associations.csv": association_rows,
        "dimension_c_event_stage_summary.csv": association_summary,
    }
    for name, frame in outputs_to_write.items():
        frame.to_csv(output_dir / name, index=False)
    grouped_plot(a, [("all_identity_chain_count", "All identity chains"),
                     ("split_events_per_transition", "Splits per transition"),
                     ("mean_accepted_jaccard", "Mean accepted Jaccard")],
                 output_dir / "dimension_a_comparison.png")
    plot_group_size_and_jaccard(data_by_approach, threshold,
                                output_dir / "dimension_a_size_jaccard.png")
    grouped_plot(b, [("weakly_connected_components", "Weak components"),
                     ("split_nodes", "Split nodes"), ("merge_nodes", "Merge nodes"),
                     ("max_depth_edges", "Maximum depth"),
                     ("max_snapshot_breadth", "Maximum breadth")],
                 output_dir / "dimension_b_comparison.png")
    plot_stage_distribution(distribution, output_dir / "dimension_c_stage_distribution.png")
    plot_event_stage_likelihoods(association_summary,
                                 output_dir / "dimension_c_event_stage_likelihoods.png")
    write_report(output_dir, a, b, stage_summary, method_comparison, association_summary)


def parse_args() -> argparse.Namespace:
    root = find_project_root()
    parser = argparse.ArgumentParser(description="Compare all three temporal-group approaches.")
    parser.add_argument("--outputs", type=Path, default=root / "code" / "graph-matching" / "outputs")
    parser.add_argument("--output", type=Path,
                        default=root / "code" / "graph-matching" / "outputs" / "approach_comparison")
    parser.add_argument("--stability-threshold", type=float, default=0.4)
    return parser.parse_args()


def main() -> None:
    args = parse_args(); run(args.outputs, args.output, args.stability_threshold); print(args.output)


if __name__ == "__main__":
    main()
