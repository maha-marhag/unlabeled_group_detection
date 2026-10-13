#!/usr/bin/env python3
"""Configuration sensitivity of dynamic-group identification.

For every approach (cumulative, interval, overlap) and every requested snapshot
count, the Louvain pipeline is run once and cached. The identity-matching step
is then repeated over a grid of thresholds for three matching criteria:

- ``stability``: the current rule (prospective or retrospective stability
  >= threshold; the production value is 0.4);
- ``jaccard``: absolute Jaccard similarity >= threshold;
- ``jaccard_adaptive``: Jaccard >= threshold * J_ref, where J_ref is the median
  best-match Jaccard of the run. J_ref rescales with the snapshot count, so
  the same relative threshold means "the same fraction of a typical match"
  at every resolution.

Outputs (``outputs/sensitivity_analysis``):

- ``runs/{approach}/n{count}/graph_matching``: cached communities.
- ``number_of_groups.csv``: number of groups per (approach, count, criterion, threshold).
- ``figures/number_of_groups_vs_{criterion}.png``: threshold sweeps at fixed snapshot counts.
- ``figures/number_of_groups_vs_snapshots_{criterion}.png``: snapshot-count sweeps at fixed thresholds.
"""

from __future__ import annotations

import argparse
import os
import statistics
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "idp_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import graph_matching
from graph_matching import find_project_root
from identity_events import (
    assign_ids,
    build_identity_groups,
    identity_relations,
    load_snapshots,
)

APPROACHES = ["cumulative", "interval", "overlap"]
SNAPSHOT_COUNTS = [10, 20, 30, 40, 50]
THRESHOLDS = [round(0.1 + 0.05 * i, 2) for i in range(17)]  # 0.10 ... 0.90
CRITERIA = ["stability", "jaccard", "jaccard_adaptive"]
CURRENT_CRITERION = ("stability", 0.4)
BASELINE_OVERLAP_COUNT = 20
BASELINE_SNAPSHOT_DAYS = 50

COUNT_COLORS = {10: "#2a78d6", 20: "#eb6834", 30: "#1baf7a", 40: "#eda100", 50: "#4a3aa7"}
CRITERION_STYLE = {
    "stability": ("#2a78d6", "current: stability"),
    "jaccard": ("#eb6834", "Jaccard (absolute)"),
    "jaccard_adaptive": ("#1baf7a", "Jaccard (adaptive, x J_ref)"),
}
APPROACH_COLORS = {"cumulative": "#2a78d6", "interval": "#eb6834", "overlap": "#1baf7a"}
METRICS = {"number_of_groups": "number of groups"}


# --------------------------------------------------------------------------- #
# Pipeline runs
# --------------------------------------------------------------------------- #
def ensure_run(edges, approach: str, count: int, run_dir: Path, force: bool) -> Path:
    communities = run_dir / approach / "communities.csv"
    if communities.exists() and not force:
        return communities
    num_snapshots = None if (approach == "overlap" and count == BASELINE_OVERLAP_COUNT) else count
    windows = graph_matching.make_windows(
        approach, 526, BASELINE_SNAPSHOT_DAYS, num_snapshots, 0.5
    )
    if len(windows) != count:
        raise ValueError(f"{approach}: expected {count} windows, got {len(windows)}")
    graph_matching.run_approach(
        edges=edges,
        approach=approach,
        output_dir=run_dir,
        cutoff_days=526,
        snapshot_days=BASELINE_SNAPSHOT_DAYS,
        num_snapshots=num_snapshots,
        overlap_fraction=0.5,
        seed=42,
        resolution=1.0,
        min_community_size=3,
        match_threshold=0.5,
    )
    return communities


def reference_jaccard(snapshots) -> float:
    """Median over communities of the best Jaccard to any next-snapshot community."""
    best = []
    for previous, current in zip(snapshots, snapshots[1:]):
        relations = identity_relations(previous, current)
        by_prev = {}
        for relation in relations:
            key = relation.previous.local_id
            by_prev[key] = max(by_prev.get(key, 0.0), relation.jaccard)
        best.extend(by_prev.get(prev.local_id, 0.0) for prev in previous)
    return statistics.median(best) if best else 0.0


def evaluate(snapshots, approach: str, criterion: str, threshold: float, j_ref: float) -> dict:
    """Number of dynamic groups produced by one matching configuration."""
    if criterion == "stability":
        ids, transitions = assign_ids(snapshots, approach, stability_threshold=threshold)
    else:
        effective = threshold * j_ref if criterion == "jaccard_adaptive" else threshold
        ids, transitions = assign_ids(
            snapshots, approach, jaccard_threshold=effective, criterion="jaccard"
        )
    groups, _ = build_identity_groups(snapshots, ids, transitions)
    return {
        "approach": approach,
        "snapshot_count": len(snapshots),
        "criterion": criterion,
        "threshold": threshold,
        "number_of_groups": len(groups),
    }


def build_grid(data_path: Path, output: Path, approaches, counts, force: bool) -> pd.DataFrame:
    edges = graph_matching.load_edges(data_path, cutoff_days=526)
    rows = []
    for approach in approaches:
        for count in counts:
            run_dir = output / "runs" / approach / f"n{count}"
            communities = ensure_run(edges, approach, count, run_dir / "graph_matching", force)
            _, snapshots = load_snapshots(communities)
            j_ref = reference_jaccard(snapshots)
            for criterion in CRITERIA:
                for threshold in THRESHOLDS:
                    rows.append(evaluate(snapshots, approach, criterion, threshold, j_ref))
            print(f"{approach} n={count}: J_ref={j_ref:.3f}", flush=True)
    grid = pd.DataFrame(rows)
    grid.to_csv(output / "number_of_groups.csv", index=False)
    return grid


# --------------------------------------------------------------------------- #
# Threshold sweep at fixed snapshot count
# --------------------------------------------------------------------------- #
def current_value(grid: pd.DataFrame, approach: str, count: int, metric: str) -> float:
    criterion, threshold = CURRENT_CRITERION
    row = grid[
        (grid["approach"] == approach)
        & (grid["snapshot_count"] == count)
        & (grid["criterion"] == criterion)
        & (grid["threshold"] == threshold)
    ]
    return float(row[metric].iloc[0])


def plot_threshold_sweep(grid: pd.DataFrame, criterion: str, metric: str, out: Path) -> None:
    """One panel per fixed snapshot count: metric vs threshold, one line per approach.

    Dashed horizontal lines show the value of the current configuration
    (stability 0.4) for each approach.
    """
    counts = sorted(grid["snapshot_count"].unique())
    fig, axes = plt.subplots(1, len(counts), figsize=(3.6 * len(counts), 4), sharey=True)
    for ax, count in zip(axes, counts):
        for approach, color in APPROACH_COLORS.items():
            sub = grid[
                (grid["approach"] == approach)
                & (grid["snapshot_count"] == count)
                & (grid["criterion"] == criterion)
            ].sort_values("threshold")
            if sub.empty:
                continue
            ax.plot(sub["threshold"], sub[metric], color=color, linewidth=2, marker="o",
                    markersize=3, label=approach)
            ax.axhline(current_value(grid, approach, count, metric), color=color,
                       linestyle="dashed", linewidth=1, alpha=0.7)
        ax.set_title(f"{count} snapshots", fontsize=10)
        ax.set_xlabel("Jaccard threshold")
        ax.grid(color="#e5e7eb")
        ax.set_axisbelow(True)
    axes[0].set_ylabel(METRICS[metric])
    handles, labels = axes[0].get_legend_handles_labels()
    handles.append(plt.Line2D([], [], color="#52514e", linestyle="dashed", linewidth=1))
    labels.append("current configuration (stability 0.4)")
    axes[0].legend(handles, labels, fontsize=7)
    label = CRITERION_STYLE[criterion][1]
    fig.suptitle(f"{METRICS[metric].capitalize()} vs {label} threshold, fixed number of snapshots", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=170)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Snapshot-count sweep at fixed threshold
# --------------------------------------------------------------------------- #
def plot_snapshot_sweep(grid: pd.DataFrame, criterion: str, metric: str, thresholds, out: Path) -> None:
    """One panel per fixed threshold: metric vs number of snapshots, one line per approach.

    Dashed lines show the current configuration (stability 0.4) per approach.
    """
    fig, axes = plt.subplots(1, len(thresholds), figsize=(3.6 * len(thresholds), 4), sharey=True)
    counts = sorted(grid["snapshot_count"].unique())
    for ax, threshold in zip(axes, thresholds):
        for approach, color in APPROACH_COLORS.items():
            sub = grid[
                (grid["approach"] == approach)
                & (grid["criterion"] == criterion)
                & (grid["threshold"] == threshold)
            ].sort_values("snapshot_count")
            if sub.empty:
                continue
            ax.plot(sub["snapshot_count"], sub[metric], color=color, linewidth=2, marker="o",
                    markersize=4, label=approach)
            current = [current_value(grid, approach, count, metric) for count in counts]
            ax.plot(counts, current, color=color, linestyle="dashed", linewidth=1, alpha=0.7)
        ax.set_title(f"threshold {threshold:.2f}", fontsize=10)
        ax.set_xlabel("number of snapshots")
        ax.set_xticks(counts)
        ax.grid(color="#e5e7eb")
        ax.set_axisbelow(True)
    axes[0].set_ylabel(METRICS[metric])
    handles, labels = axes[0].get_legend_handles_labels()
    handles.append(plt.Line2D([], [], color="#52514e", linestyle="dashed", linewidth=1))
    labels.append("current configuration (stability 0.4)")
    axes[0].legend(handles, labels, fontsize=7)
    label = CRITERION_STYLE[criterion][1]
    fig.suptitle(f"{METRICS[metric].capitalize()} vs number of snapshots, fixed {label} threshold", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=170)
    plt.close(fig)


def make_figures(grid: pd.DataFrame, fig_dir: Path, sweeps: set[str]) -> None:
    fig_dir.mkdir(parents=True, exist_ok=True)
    fixed_thresholds = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    if "threshold" in sweeps:
        for criterion in ("jaccard", "jaccard_adaptive", "stability"):
            for metric in METRICS:
                plot_threshold_sweep(grid, criterion, metric, fig_dir / f"{metric}_vs_{criterion}.png")
    if "snapshots" in sweeps:
        for criterion in ("jaccard", "jaccard_adaptive", "stability"):
            for metric in METRICS:
                plot_snapshot_sweep(grid, criterion, metric, fixed_thresholds,
                                    fig_dir / f"{metric}_vs_snapshots_{criterion}.png")


def parse_args() -> argparse.Namespace:
    root = find_project_root()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=root / "dataset" / "email-Eu-core-temporal.txt")
    parser.add_argument(
        "--output", type=Path,
        default=root / "code" / "graph-matching" / "outputs" / "sensitivity_analysis",
    )
    parser.add_argument("--approach", choices=[*APPROACHES, "all"], default="all")
    parser.add_argument("--snapshot-counts", type=int, nargs="+", default=SNAPSHOT_COUNTS)
    parser.add_argument("--force", action="store_true", help="Recompute cached Louvain runs.")
    parser.add_argument("--figures-only", action="store_true", help="Reuse number_of_groups.csv.")
    parser.add_argument("--sweeps", default="threshold,snapshots",
                        help="Figure sets to draw: threshold, snapshots, or both (comma-separated).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    approaches = APPROACHES if args.approach == "all" else [args.approach]
    args.output.mkdir(parents=True, exist_ok=True)
    if args.figures_only:
        grid = pd.read_csv(args.output / "number_of_groups.csv")
    else:
        grid = build_grid(args.data, args.output, approaches, args.snapshot_counts, args.force)
    make_figures(grid, args.output / "figures", set(args.sweeps.split(",")))


if __name__ == "__main__":
    main()
