#!/usr/bin/env python3
"""Run and compare overlap analysis at 20 and 50 snapshots."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "idp_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import graph_matching
import identity_events
import stage_events
import stage_identification_analysis
import visualize_stage_identification
from compare_approaches import (
    STAGE_TYPES,
    build_lineage_graph,
    compare_stage_methods,
    dimension_a_row,
    dimension_b_row,
    lineage_coordinates,
    load_data,
    network_rows,
    plot_lineage,
    stage_distribution_rows,
    stage_method_summary,
)


CONFIGURATIONS = [20, 50]
# The 20-snapshot run must reproduce the overlap baseline used in
# outputs/approach_comparison: exact 50-day windows with a 25-day stride.
# Passing num_snapshots=None selects that default window construction instead
# of solving a fractional window width from the requested count.
BASELINE_SNAPSHOT_COUNT = 20
BASELINE_SNAPSHOT_DAYS = 50


def requested_snapshot_count(snapshot_count: int) -> int | None:
    """Return the num_snapshots argument that yields the requested configuration."""
    return None if snapshot_count == BASELINE_SNAPSHOT_COUNT else snapshot_count


def run_configuration(
    project_root: Path,
    data_path: Path,
    output_root: Path,
    snapshot_count: int,
    cutoff_days: int,
    overlap_fraction: float,
    stability_threshold: float,
) -> None:
    config_root = output_root / f"n{snapshot_count}"
    graph_dir = config_root / "graph_matching"
    identification_dir = config_root / "stage_identification"
    analysis_dir = config_root / "stage_analysis"

    num_snapshots = requested_snapshot_count(snapshot_count)
    windows = graph_matching.make_windows(
        "overlap", cutoff_days, BASELINE_SNAPSHOT_DAYS, num_snapshots, overlap_fraction
    )
    if len(windows) != snapshot_count:
        raise ValueError(
            f"Expected {snapshot_count} overlap windows, got {len(windows)}."
        )

    edges = graph_matching.load_edges(data_path, cutoff_days=cutoff_days)
    graph_matching.run_approach(
        edges=edges,
        approach="overlap",
        output_dir=graph_dir,
        cutoff_days=cutoff_days,
        snapshot_days=BASELINE_SNAPSHOT_DAYS,
        num_snapshots=num_snapshots,
        overlap_fraction=overlap_fraction,
        seed=42,
        resolution=1.0,
        min_community_size=3,
        match_threshold=0.5,
    )
    identity_events.run_approach(
        input_dir=graph_dir,
        output_dir=identification_dir,
        approach="overlap",
        jaccard_threshold=0.0,
        stability_threshold=stability_threshold,
    )
    stage_events.run_approach(
        input_dir=graph_dir,
        output_dir=identification_dir,
        approach="overlap",
        jaccard_threshold=0.0,
        stability_threshold=stability_threshold,
    )
    stage_events.combine_final_communities(identification_dir, ["overlap"])
    stage_identification_analysis.run_approach(
        project_root,
        identification_dir,
        analysis_dir,
        "overlap",
        100.0,
    )
    stage_identification_analysis.combine_outputs(analysis_dir, ["overlap"])
    visualize_stage_identification.run(
        analysis_dir,
        config_root / "stage_figures",
        identification_dir,
        ["overlap"],
    )


def configuration_metrics(
    output_root: Path,
    snapshot_count: int,
    threshold: float,
) -> tuple[dict, pd.DataFrame, pd.DataFrame, dict]:
    config_root = output_root / f"n{snapshot_count}"
    data = load_data(config_root, "overlap")
    a = dimension_a_row("overlap", data, threshold)
    graph = build_lineage_graph(data["identified"], data["overlaps"], threshold)
    b = dimension_b_row("overlap", graph)
    positions, component_ids = lineage_coordinates(graph)
    nodes, edges = network_rows("overlap", graph, positions, component_ids)
    pd.DataFrame(nodes).to_csv(config_root / "network_nodes.csv", index=False)
    pd.DataFrame(edges).to_csv(config_root / "network_edges.csv", index=False)
    plot_lineage("overlap", graph, positions, config_root)

    snapshots = data["snapshots"]
    widths = pd.to_numeric(snapshots["end_day"]) - pd.to_numeric(snapshots["start_day"])
    starts = pd.to_numeric(snapshots["start_day"])
    strides = starts.diff().dropna()
    classic_summary = stage_method_summary("overlap", "classic", data["classic"])
    event_summary = stage_method_summary("overlap", "event_based", data["event_based"])
    method_comparison = compare_stage_methods("overlap", data["classic"], data["event_based"])
    summary = {
        "configuration": f"overlap_{snapshot_count}",
        "snapshot_count": snapshot_count,
        "mean_window_width_days": float(widths.mean()),
        "mean_stride_days": float(strides.mean()),
        "mean_temporal_edges_per_snapshot": float(pd.to_numeric(snapshots["temporal_edges"]).mean()),
        **{key: value for key, value in a.items() if key != "approach"},
        **{f"network_{key}": value for key, value in b.items() if key != "approach"},
        "classic_stage_count": classic_summary["stage_count"],
        "classic_mean_stages_per_group": classic_summary["mean_stages_per_group"],
        "event_stage_count": event_summary["stage_count"],
        "event_mean_stages_per_group": event_summary["mean_stages_per_group"],
        "classic_event_stage_type_agreement": method_comparison["stage_type_agreement_rate"],
        "classic_event_boundary_jaccard": method_comparison["boundary_jaccard"],
    }
    distributions = []
    for method, stages in [("classic", data["classic"]), ("event_based", data["event_based"])]:
        for row in stage_distribution_rows(f"overlap_{snapshot_count}", method, stages):
            row["snapshot_count"] = snapshot_count
            distributions.append(row)
    return summary, pd.DataFrame(nodes), pd.DataFrame(distributions), data


def percent_change_table(summary: pd.DataFrame) -> pd.DataFrame:
    numeric = summary.select_dtypes(include="number").columns
    rows = []
    first, second = summary.iloc[0], summary.iloc[1]
    for metric in numeric:
        if metric == "snapshot_count":
            continue
        baseline = float(first[metric])
        value = float(second[metric])
        rows.append(
            {
                "metric": metric,
                "overlap_20": baseline,
                "overlap_50": value,
                "absolute_change": value - baseline,
                "percent_change": (value - baseline) / baseline if baseline else np.nan,
            }
        )
    return pd.DataFrame(rows)


def plot_summary(summary: pd.DataFrame, output: Path) -> None:
    specs = [
        ("observation_group_count", "Observation groups"),
        ("all_identity_chain_count", "Identity chains"),
        ("final_group_count", "Final groups"),
        ("split_events_per_transition", "Splits per transition"),
        ("merge_events_per_transition", "Merges per transition"),
        ("mean_accepted_jaccard", "Mean accepted Jaccard"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    labels = ["20 snapshots", "50 snapshots"]
    colors = ["#059669", "#0f766e"]
    for ax, (metric, title) in zip(axes.flatten(), specs):
        ax.bar(labels, summary[metric], color=colors)
        ax.set_title(title)
        ax.grid(axis="y", color="#e5e7eb")
        ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def plot_group_sizes(data_by_count: dict[int, dict], output: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for count, color in [(20, "#059669"), (50, "#0f766e")]:
        data = data_by_count[count]
        sizes = data["identified"].groupby("snapshot_index")["size"].mean().reset_index()
        times = data["snapshots"][["snapshot_index", "end_day"]]
        frame = sizes.merge(times, on="snapshot_index")
        ax.plot(frame["end_day"], frame["size"], marker="o", markersize=3,
                label=f"{count} snapshots", color=color)
    ax.set_title("Mean overlap-community size over time")
    ax.set_xlabel("Window end day")
    ax.set_ylabel("Mean community size")
    ax.legend()
    ax.grid(color="#e5e7eb")
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def plot_stage_distributions(distribution: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 8), sharey=True)
    for row, count in enumerate(CONFIGURATIONS):
        for col, method in enumerate(["classic", "event_based"]):
            ax = axes[row, col]
            frame = distribution.loc[(distribution["snapshot_count"] == count)
                                     & (distribution["method"] == method)].set_index("stage_type").reindex(STAGE_TYPES)
            x = np.arange(len(STAGE_TYPES))
            ax.bar(x - .18, frame["stage_count_share"], .36, label="Count share", color="#64748b")
            ax.bar(x + .18, frame["transition_duration_share"], .36, label="Duration share",
                   color="#059669" if count == 20 else "#0f766e")
            ax.set_title(f"{count} snapshots — {method.replace('_', ' ').title()}")
            ax.set_xticks(x, [value.replace("-", "\n") for value in STAGE_TYPES], fontsize=7)
            ax.grid(axis="y", color="#e5e7eb")
            ax.set_axisbelow(True)
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].legend(fontsize=8)
    fig.supylabel("Share")
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def event_stage_share(distribution: pd.DataFrame, snapshot_count: int, stage_type: str) -> float:
    rows = distribution.loc[
        (distribution["snapshot_count"] == snapshot_count)
        & (distribution["method"] == "event_based")
        & (distribution["stage_type"] == stage_type)
    ]
    return float(rows["stage_count_share"].iloc[0]) if len(rows) else 0.0


def write_report(output_root: Path, summary: pd.DataFrame, distribution: pd.DataFrame) -> None:
    s20 = summary.loc[summary["snapshot_count"] == 20].iloc[0]
    s50 = summary.loc[summary["snapshot_count"] == 50].iloc[0]
    turnover_20 = event_stage_share(distribution, 20, "Turnover-Shrinkage")
    turnover_50 = event_stage_share(distribution, 50, "Turnover-Shrinkage")
    organic_20 = event_stage_share(distribution, 20, "Organic-Growth")
    organic_50 = event_stage_share(distribution, 50, "Organic-Growth")
    steady_20 = event_stage_share(distribution, 20, "Steady-Stability")
    steady_50 = event_stage_share(distribution, 50, "Steady-Stability")
    boundary_delta = abs(
        float(s20["classic_event_boundary_jaccard"]) - float(s50["classic_event_boundary_jaccard"])
    )
    boundary_sentence = (
        "showing greater disagreement about exact change points at fine resolution"
        if boundary_delta >= 0.05
        else "so agreement about exact change points is largely unaffected by resolution"
    )
    text = f"""# Overlap snapshot sensitivity: 20 versus 50 snapshots

## Configuration

Both runs cover the same 526-day dataset and use 50% overlap, Louvain resolution 1.0, seed 42, minimum community size 3, and directional stability threshold 0.4. The 20-snapshot run uses exact 50-day windows with a 25-day stride and is identical to the overlap baseline in `outputs/approach_comparison`. The 50-snapshot run solves its window width from the requested count so that 50 half-overlapping windows cover the full period.

| Metric | 20 snapshots | 50 snapshots |
| --- | ---: | ---: |
| Mean window width (days) | {s20['mean_window_width_days']:.2f} | {s50['mean_window_width_days']:.2f} |
| Mean stride (days) | {s20['mean_stride_days']:.2f} | {s50['mean_stride_days']:.2f} |
| Observation groups | {s20['observation_group_count']:.0f} | {s50['observation_group_count']:.0f} |
| Identity chains | {s20['all_identity_chain_count']:.0f} | {s50['all_identity_chain_count']:.0f} |
| Final groups | {s20['final_group_count']:.0f} | {s50['final_group_count']:.0f} |
| Splits per transition | {s20['split_events_per_transition']:.3f} | {s50['split_events_per_transition']:.3f} |
| Merges per transition | {s20['merge_events_per_transition']:.3f} | {s50['merge_events_per_transition']:.3f} |
| Mean accepted Jaccard | {s20['mean_accepted_jaccard']:.3f} | {s50['mean_accepted_jaccard']:.3f} |
| Weakly connected components | {s20['network_weakly_connected_components']:.0f} | {s50['network_weakly_connected_components']:.0f} |
| Maximum lineage depth | {s20['network_max_depth_edges']:.0f} | {s50['network_max_depth_edges']:.0f} |
| Classic stages | {s20['classic_stage_count']:.0f} | {s50['classic_stage_count']:.0f} |
| Event-based stages | {s20['event_stage_count']:.0f} | {s50['event_stage_count']:.0f} |
| Classic/event label agreement | {s20['classic_event_stage_type_agreement']:.1%} | {s50['classic_event_stage_type_agreement']:.1%} |

![Resolution comparison](comparison/summary_comparison.png)

![Community size over time](comparison/group_size_over_time.png)

![Stage distributions](comparison/stage_distributions.png)

## Interpretation

The 50-snapshot run is not simply a larger copy of the 20-snapshot run. Its windows are shorter, so each snapshot contains less interaction evidence. Raw group, event, and stage counts naturally increase with observation frequency. Rates per transition, Jaccard similarity, final-group count, component structure, and stage shares are therefore the main sensitivity indicators.

### Stable findings

- Final groups remain nearly unchanged: {s20['final_group_count']:.0f} at 20 snapshots and {s50['final_group_count']:.0f} at 50.
- Splits per transition change from {s20['split_events_per_transition']:.3f} to {s50['split_events_per_transition']:.3f}; merges change from {s20['merge_events_per_transition']:.3f} to {s50['merge_events_per_transition']:.3f}.
- Mean accepted Jaccard changes only from {s20['mean_accepted_jaccard']:.3f} to {s50['mean_accepted_jaccard']:.3f}.
- Classic/event stage-label agreement remains close: {s20['classic_event_stage_type_agreement']:.1%} versus {s50['classic_event_stage_type_agreement']:.1%}.

These results indicate that the overlap approach's normalized event activity and final-group count are reasonably robust to the finer resolution.

### Resolution-sensitive findings

- Mean observation-group size falls from {s20['mean_observation_group_size']:.1f} to {s50['mean_observation_group_size']:.1f}, because a {s50['mean_window_width_days']:.2f}-day window contains less interaction evidence than a {s20['mean_window_width_days']:.2f}-day window.
- Identity chains increase from {s20['all_identity_chain_count']:.0f} to {s50['all_identity_chain_count']:.0f}, while dead chains increase from {s20['dead_identity_chain_count']:.0f} to {s50['dead_identity_chain_count']:.0f}. This is substantial additional fragmentation rather than only additional temporal detail.
- Event-based stage composition shifts. The turnover-shrinkage share of event-based stages moves from {turnover_20:.1%} to {turnover_50:.1%}, organic growth from {organic_20:.1%} to {organic_50:.1%}, and steady stability from {steady_20:.1%} to {steady_50:.1%}. Stage conclusions are therefore not resolution-invariant.
- Classic/event boundary Jaccard changes from {s20['classic_event_boundary_jaccard']:.3f} to {s50['classic_event_boundary_jaccard']:.3f}, {boundary_sentence}.

## Recommendation

Keep **20-snapshot overlap as the primary working configuration**. It retains the overlap approach's continuity benefits while providing substantially more interaction evidence per snapshot and fewer fragmented/dead chains. Keep the 50-snapshot run as a fine-grained sensitivity view for locating short-lived changes, but do not mix its raw counts or stage distribution directly with the 20-snapshot results.

The detailed values and percentage changes are in `comparison/resolution_summary.csv` and `comparison/resolution_changes.csv`. Full pipeline outputs are preserved under `n20/` and `n50/`. Each configuration also includes its complete lineage-network PNG/PDF and node/edge coordinate CSVs.
"""
    (output_root / "README.md").write_text(text)


def run(args: argparse.Namespace) -> None:
    project_root = find_project_root()
    for count in CONFIGURATIONS:
        run_configuration(project_root, args.data, args.output, count, args.cutoff_days,
                          args.overlap_fraction, args.stability_threshold)

    summaries, distributions, data_by_count = [], [], {}
    for count in CONFIGURATIONS:
        summary, _, distribution, data = configuration_metrics(args.output, count, args.stability_threshold)
        summaries.append(summary)
        distributions.append(distribution)
        data_by_count[count] = data
    summary = pd.DataFrame(summaries)
    distribution = pd.concat(distributions, ignore_index=True)
    comparison_dir = args.output / "comparison"
    comparison_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(comparison_dir / "resolution_summary.csv", index=False)
    percent_change_table(summary).to_csv(comparison_dir / "resolution_changes.csv", index=False)
    distribution.to_csv(comparison_dir / "stage_type_distribution.csv", index=False)
    plot_summary(summary, comparison_dir / "summary_comparison.png")
    plot_group_sizes(data_by_count, comparison_dir / "group_size_over_time.png")
    plot_stage_distributions(distribution, comparison_dir / "stage_distributions.png")
    write_report(args.output, summary, distribution)


def find_project_root() -> Path:
    return graph_matching.find_project_root()


def parse_args() -> argparse.Namespace:
    root = find_project_root()
    parser = argparse.ArgumentParser(description="Run overlap with 20 and 50 snapshots.")
    parser.add_argument("--data", type=Path, default=root / "dataset" / "email-Eu-core-temporal.txt")
    parser.add_argument("--output", type=Path,
                        default=root / "code" / "graph-matching" / "outputs" / "overlap_snapshot_sensitivity")
    parser.add_argument("--cutoff-days", type=int, default=526)
    parser.add_argument("--overlap-fraction", type=float, default=.5)
    parser.add_argument("--stability-threshold", type=float, default=.4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args)
    print(args.output)


if __name__ == "__main__":
    main()
