#!/usr/bin/env python3
"""Robustness of the dynamic groups to the number of snapshots with one Jaccard threshold.

Uses the fixed-width runs of ``config_sensitivity.py``: windows of WINDOW_DAYS days
ending every WINDOW_DAYS / k days (k = 1..5), anchored at the cutoff. A cumulative
window ending at t covers [0, t], a sliding window covers [t - W, t]. For k = 1 the
sliding windows do not overlap, so this run is also the interval approach.

The same Jaccard threshold theta is used for both runs of a comparison; theta is swept
over SEARCH_THRESHOLDS. The dynamic groups present at MIN_COMMON_POINTS or more common
time points are compared as in ``sensitivity_plots.py`` (mean Jaccard cross table,
linear sum assignment, score = matched Jaccard sum / max(n_i, n_j), ARI).

Outputs (``outputs/sensitivity_analysis/fixed_window``):

- ``threshold_sweep.csv``: one row per approach, pair (k_i, k_j) and theta.
- ``best_per_pair.csv``: best eligible theta per approach and pair.
- ``theta_summary.csv``: per approach and theta, the mean over pairs (one theta for all k).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config_sensitivity import STRIDE_DIVISORS
from graph_matching import find_project_root
from sensitivity_plots import MIN_COMPARED_GROUPS, SEARCH_THRESHOLDS, agreement, dynamic_groups, time_pairs

APPROACHES = ["cumulative", "overlap"]


def sweep(runs: Path) -> pd.DataFrame:
    rows = []
    for approach in APPROACHES:
        # Runs ordered by number of snapshots, i.e. by stride divisor k.
        paths = sorted((runs / approach).glob(f"n*/graph_matching/{approach}/communities.csv"),
                       key=lambda path: int(path.parts[-4][1:]))
        if len(paths) != len(STRIDE_DIVISORS[approach]):
            raise ValueError(f"{approach}: expected {len(STRIDE_DIVISORS[approach])} runs, got {len(paths)}")
        runs_by_k = dict(zip(STRIDE_DIVISORS[approach], paths))
        groups = {(k, theta): dynamic_groups(path, approach, theta)
                  for k, path in runs_by_k.items() for theta in SEARCH_THRESHOLDS}
        ks = list(runs_by_k)
        for a, k_i in enumerate(ks):
            for k_j in ks[a + 1:]:
                for theta in SEARCH_THRESHOLDS:
                    times_i, chron_i = groups[k_i, theta]
                    times_j, chron_j = groups[k_j, theta]
                    pairs = time_pairs(times_i, times_j, approach)
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
    base = root / "code" / "graph-matching" / "outputs" / "sensitivity_analysis"
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=Path, default=base / "runs")
    parser.add_argument("--output", type=Path, default=base / "fixed_window")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    search = sweep(args.runs)
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
