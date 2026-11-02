#!/usr/bin/env python3
"""Robustness of the dynamic groups to the number of snapshots at a fixed window width.

The window width is fixed to W days and only the stride changes: Delta = W / k for
k = 1..5, window ends t = W + j * Delta (t <= cutoff). A cumulative window ending at t
covers [0, t], a sliding window covers [t - W, t]. For k = 1 the sliding windows do not
overlap, so this run is also the interval approach with W-day windows.

Since every window has the same width, the graph at a time point t is the same for
every k, and the common time points of two runs are exact (the multiples of W at
least). The same Jaccard threshold theta is used for both runs of a comparison; theta
is swept over SEARCH_THRESHOLDS. The dynamic groups present at MIN_COMMON_POINTS or
more common time points are compared as in ``sensitivity_plots.py`` (mean Jaccard
cross table, linear sum assignment, score = matched Jaccard sum / max(n_i, n_j), ARI).

Outputs (``outputs/sensitivity_analysis/fixed_window``):

- ``runs/{approach}/k{k}/communities.csv``: cached Louvain communities.
- ``threshold_sweep.csv``: one row per approach, pair (k_i, k_j) and theta.
- ``best_per_pair.csv``: best eligible theta per approach and pair.
- ``theta_summary.csv``: per approach and theta, the mean over pairs (one theta for all k).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

import graph_matching
from graph_matching import SECONDS_PER_DAY, build_graph, detect_communities, edges_for_window, find_project_root
from graph_matching import SnapshotWindow
from sensitivity_plots import MIN_COMPARED_GROUPS, SEARCH_THRESHOLDS, agreement, dynamic_groups

APPROACHES = ["cumulative", "overlap"]
WINDOW_DAYS = 50
STRIDE_DIVISORS = [1, 2, 3, 4, 5]
CUTOFF_DAYS = 526
SEED = 42
RESOLUTION = 1.0
MIN_COMMUNITY_SIZE = 3


def fixed_windows(approach: str, k: int) -> list[SnapshotWindow]:
    stride = WINDOW_DAYS / k
    ends = [WINDOW_DAYS + j * stride for j in range(int((CUTOFF_DAYS - WINDOW_DAYS) / stride + 1e-9) + 1)]
    windows = []
    for index, end in enumerate(ends):
        start = 0 if approach == "cumulative" else end - WINDOW_DAYS
        windows.append(SnapshotWindow(index, f"days_{start:.2f}_{end:.2f}",
                                      round(start * SECONDS_PER_DAY), round(end * SECONDS_PER_DAY)))
    return windows


def ensure_run(edges: pd.DataFrame, approach: str, k: int, run_dir: Path) -> Path:
    path = run_dir / approach / f"k{k}" / "communities.csv"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["approach", "snapshot_index", "snapshot_label", "window_start_ts",
                         "window_end_ts", "local_id", "nodes_json"])
        for window in fixed_windows(approach, k):
            graph = build_graph(edges_for_window(edges, window))
            communities = detect_communities(graph, seed=SEED, resolution=RESOLUTION, min_size=MIN_COMMUNITY_SIZE)
            for local_id, community in enumerate(communities):
                writer.writerow([approach, window.index, window.label, window.start_ts, window.end_ts,
                                 local_id, json.dumps(sorted(community))])
    print(f"{approach} k={k}: communities written", flush=True)
    return path


def sweep(edges: pd.DataFrame, out: Path) -> pd.DataFrame:
    rows = []
    for approach in APPROACHES:
        paths = {k: ensure_run(edges, approach, k, out / "runs") for k in STRIDE_DIVISORS}
        groups = {(k, theta): dynamic_groups(paths[k], approach, theta)
                  for k in STRIDE_DIVISORS for theta in SEARCH_THRESHOLDS}
        for a, k_i in enumerate(STRIDE_DIVISORS):
            for k_j in STRIDE_DIVISORS[a + 1:]:
                for theta in SEARCH_THRESHOLDS:
                    times_i, chron_i = groups[k_i, theta]
                    times_j, chron_j = groups[k_j, theta]
                    common = {round(t, 6) for t in times_j}
                    pairs = [(t, t) for t in times_i if round(t, 6) in common]
                    rows.append({"approach": approach, "k_i": k_i, "k_j": k_j,
                                 "s_i": len(times_i), "s_j": len(times_j), "theta": theta,
                                 "common_time_points": len(pairs),
                                 "groups_i": len(chron_i), "groups_j": len(chron_j),
                                 "single_snapshot_share_i": float(np.mean([len(c) == 1 for c in chron_i.values()])),
                                 "single_snapshot_share_j": float(np.mean([len(c) == 1 for c in chron_j.values()])),
                                 **agreement(chron_i, chron_j, pairs)})
                print(f"{approach} k={k_i} vs k={k_j} done", flush=True)
    return pd.DataFrame(rows).round(3)


def parse_args() -> argparse.Namespace:
    root = find_project_root()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=root / "dataset" / "email-Eu-core-temporal.txt")
    parser.add_argument("--output", type=Path, default=root / "code" / "graph-matching" / "outputs"
                        / "sensitivity_analysis" / "fixed_window")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    edges = graph_matching.load_edges(args.data, cutoff_days=CUTOFF_DAYS)
    search = sweep(edges, args.output)
    search.to_csv(args.output / "threshold_sweep.csv", index=False)
    eligible = search[(search["compared_i"] >= MIN_COMPARED_GROUPS) & (search["compared_j"] >= MIN_COMPARED_GROUPS)]
    best = eligible.loc[eligible.groupby(["approach", "k_i", "k_j"], sort=False)["score"].idxmax()]
    best.to_csv(args.output / "best_per_pair.csv", index=False)
    # One theta for all k: only thetas eligible for every pair of the approach.
    pairs_per_approach = search.groupby("approach")[["k_i", "k_j"]].apply(lambda f: len(f.drop_duplicates()))
    by_theta = eligible.groupby(["approach", "theta"]).agg(
        eligible_pairs=("score", "size"), mean_score=("score", "mean"), min_score=("score", "min"),
        mean_median_jaccard=("median_matched_jaccard", "mean"), mean_ari=("ari", "mean")).reset_index()
    by_theta["all_pairs_eligible"] = by_theta["eligible_pairs"] == by_theta["approach"].map(pairs_per_approach)
    by_theta.round(3).to_csv(args.output / "theta_summary.csv", index=False)
    print(best.to_string(index=False))
    print(by_theta[by_theta["all_pairs_eligible"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
