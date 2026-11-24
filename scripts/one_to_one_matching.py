#!/usr/bin/env python3
"""One-to-one correspondence of the dynamic groups across snapshot counts, by mean Jaccard.

For a pair of snapshot counts (S_i, S_j) the cross table M of mean Jaccard values J_bar of
the compared dynamic groups is built as in ``sensitivity_plots.crosstab`` (mean over the
common time points at which the two groups overlap).

- Linear sum assignment (Hungarian algorithm): one partner per group; a pair is identical
  if J_bar >= IDENTICAL.
- Maximum alignment: every group chooses its best partner(s) without a one-to-one
  constraint, b_i(k) = argmax_l M[k, l], b_j(l) = argmax_k M[k, l]. (k, l) is a mutual
  best match if l is the only best partner of k and k the only best partner of l (M > 0).
  Every group is classified as

  - one_to_one: part of a mutual best match;
  - split_merge: several best partners (tie) or a best partner that does not choose it
    back, i.e. the group corresponds to several groups of the other configuration;
  - no_partner: its row (column) of M is 0.

Shares per pair of snapshot counts for the configuration with fewer compared groups
(denominator min(n_i, n_j)) and with more (max(n_i, n_j)), averaged over the pairs;
theta* (all groups at a common time point) and theta_hat (groups at >= 2 common time points).

Outputs (``outputs/sensitivity_analysis/fixed_window``): ``one_to_one_pairs.csv``,
``one_to_one_summary.csv``; ``figures/one_to_one.png`` (classes of the maximum alignment) and
``figures/hungarian_vs_max_alignment.png`` (identical pairs of the assignment vs 1:1 groups
of the maximum alignment).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "idp_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from fixed_window_sensitivity import MIN_COMMON_POINTS
from graph_matching import find_project_root
from sensitivity_plots import GROUPS_LINE, crosstab, dynamic_groups, theta_star, time_pairs

IDENTICAL = 0.99
THETA_HAT = {"cumulative": 0.35, "overlap": 0.40}
APPROACHES = list(THETA_HAT)
CLASSES = {"one_to_one": ("1:1 (mutual best match)", "#2a78d6"),
           "split_merge": ("split / merge (several partners)", "#e8853d"),
           "no_partner": ("no partner", "#8b5cc4")}


def best_partners(table: np.ndarray) -> list[set[int]]:
    """Per row the set of columns reaching the row maximum (empty if the row is 0)."""
    return [set(np.flatnonzero(row == row.max())) if row.max() > 0 else set() for row in table]


def runs_of(runs: Path, approach: str) -> list[Path]:
    return sorted((runs / approach).glob(f"n*/graph_matching/{approach}/communities.csv"),
                  key=lambda path: int(path.parts[-4][1:]))


def classes(best: list[set[int]], mutual_members: set[int]) -> dict[str, int]:
    counts = dict.fromkeys(CLASSES, 0)
    for k, partners in enumerate(best):
        key = "no_partner" if not partners else "one_to_one" if k in mutual_members else "split_merge"
        counts[key] += 1
    return counts


def compare(table: np.ndarray) -> dict:
    rows_best, cols_best = best_partners(table), best_partners(table.T)
    mutual = {(k, next(iter(b))) for k, b in enumerate(rows_best)
              if len(b) == 1 and cols_best[next(iter(b))] == {k}}
    sides = {"i": classes(rows_best, {k for k, _ in mutual}),
             "j": classes(cols_best, {l for _, l in mutual})}
    n_i, n_j = table.shape
    small, large = ("i", "j") if n_i <= n_j else ("j", "i")
    r, c = linear_sum_assignment(table, maximize=True)
    result = {"compared_i": n_i, "compared_j": n_j, "mutual": len(mutual),
              "hungarian_pairs": len(r), "hungarian_identical": int((table[r, c] >= IDENTICAL).sum()),
              "hungarian_mutual": len(set(zip(r, c)) & mutual)}
    for side, label in ((small, "min"), (large, "max")):
        n = max(n_i, n_j) if label == "max" else min(n_i, n_j)
        for key, count in sides[side].items():
            result[f"{key}_{label}_count"] = count
            result[f"{key}_{label}"] = round(count / n, 3)
    result["hungarian_identical_min"] = round(result["hungarian_identical"] / min(n_i, n_j), 3)
    result["hungarian_identical_max"] = round(result["hungarian_identical"] / max(n_i, n_j), 3)
    return result


def sweep(base: Path) -> pd.DataFrame:
    grid = pd.read_csv(base / "number_of_groups.csv")
    grid = grid[grid["criterion"] == "jaccard"]
    rows = []
    for approach in APPROACHES:
        sub = grid[grid["approach"] == approach]
        paths = {int(path.parts[-4][1:]): path for path in runs_of(base / "runs", approach)}
        counts = sorted(paths)
        thetas = {"theta*": ({s: theta_star(sub[sub["snapshot_count"] == s], GROUPS_LINE[approach])
                              for s in counts}, 1),
                  "theta_hat": ({s: THETA_HAT[approach] for s in counts}, MIN_COMMON_POINTS)}
        for threshold, (theta, min_points) in thetas.items():
            groups = {s: dynamic_groups(paths[s], approach, theta[s]) for s in counts}
            for a, s_i in enumerate(counts):
                for s_j in counts[a + 1:]:
                    (times_i, chron_i), (times_j, chron_j) = groups[s_i], groups[s_j]
                    table, _, _ = crosstab(chron_i, chron_j, time_pairs(times_i, times_j, approach), min_points)
                    rows.append({"approach": approach, "threshold": threshold, "s_i": s_i, "s_j": s_j,
                                 **compare(table)})
            print(f"{approach} {threshold} done", flush=True)
    return pd.DataFrame(rows)


def plot(summary: pd.DataFrame, out: Path) -> None:
    titles = {"theta*": "θ* (equal number of groups)", "theta_hat": "θ̂ (one threshold for all S)"}
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    width = 0.26
    x = np.arange(len(APPROACHES))
    for ax, threshold in zip(axes, titles):
        for offset, (key, (label, color)) in zip((-width - 0.01, 0, width + 0.01), CLASSES.items()):
            rows = summary.loc[[(a, threshold) for a in APPROACHES]]
            mean, low, high = (rows[f"{key}_min_{s}"].to_numpy() * 100 for s in ("mean", "min", "max"))
            ax.bar(x + offset, mean, width, color=color, label=label)
            ax.vlines(x + offset, low, high, color="#3f3f46", linewidth=1.2)
            for xi, m, h in zip(x + offset, mean, high):
                ax.annotate(f"{m:.0f}", (xi, h), xytext=(0, 3), textcoords="offset points",
                            ha="center", fontsize=8, color="#3f3f46")
        ax.set_xticks(x)
        ax.set_xticklabels(APPROACHES)
        ax.set_ylim(0, 105)
        ax.set_title(titles[threshold], fontsize=11)
        ax.grid(axis="y", color="#e5e7eb")
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("groups of the smaller configuration (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=8, loc="lower center", ncol=3, frameon=False)
    fig.suptitle("Maximum alignment by mean Jaccard: mean over the 10 pairs of snapshot counts "
                 "(line: min–max)", fontsize=11)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(out, dpi=170)
    plt.close(fig)


def plot_comparison(summary: pd.DataFrame, out: Path) -> None:
    titles = {"theta*": "θ* (equal number of groups)", "theta_hat": "θ̂ (one threshold for all S)"}
    bars = {"hungarian_identical_min": ("Hungarian: identical pairs", "#2a78d6"),
            "one_to_one_min": ("maximum alignment: 1:1 groups", "#e8853d")}
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    width = 0.36
    x = np.arange(len(APPROACHES))
    for ax, threshold in zip(axes, titles):
        for offset, (column, (label, color)) in zip((-width / 2 - 0.01, width / 2 + 0.01), bars.items()):
            rows = summary.loc[[(a, threshold) for a in APPROACHES]]
            mean, low, high = (rows[f"{column}_{s}"].to_numpy() * 100 for s in ("mean", "min", "max"))
            ax.bar(x + offset, mean, width, color=color, label=label)
            ax.vlines(x + offset, low, high, color="#3f3f46", linewidth=1.2)
            for xi, m, h in zip(x + offset, mean, high):
                ax.annotate(f"{m:.0f}", (xi, h), xytext=(0, 3), textcoords="offset points",
                            ha="center", fontsize=8, color="#3f3f46")
        ax.set_xticks(x)
        ax.set_xticklabels(APPROACHES)
        ax.set_ylim(0, 105)
        ax.set_title(titles[threshold], fontsize=11)
        ax.grid(axis="y", color="#e5e7eb")
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("groups of the smaller configuration (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=8, loc="lower center", ncol=2, frameon=False)
    fig.suptitle("Hungarian assignment vs maximum alignment: mean over the 10 pairs of snapshot "
                 "counts (line: min–max)", fontsize=11)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(out, dpi=170)
    plt.close(fig)


def main() -> None:
    base = find_project_root() / "code" / "graph-matching" / "outputs" / "sensitivity_analysis"
    frame = sweep(base)
    frame.to_csv(base / "fixed_window" / "one_to_one_pairs.csv", index=False)
    shares = [c for c in frame.columns if c.endswith(("_min", "_max"))]
    stats = {}
    for column in shares:
        stats |= {f"{column}_mean": (column, "mean"), f"{column}_min": (column, "min"),
                  f"{column}_max": (column, "max")}
    for column in [c for c in frame.columns if c.endswith("_count")] + [
            "mutual", "hungarian_pairs", "hungarian_identical", "hungarian_mutual"]:
        stats[f"{column}_sum"] = (column, "sum")
    summary = frame.groupby(["approach", "threshold"], sort=False).agg(**stats).round(3)
    summary.to_csv(base / "fixed_window" / "one_to_one_summary.csv")
    plot(summary, base / "figures" / "one_to_one.png")
    plot_comparison(summary, base / "figures" / "hungarian_vs_max_alignment.png")
    print(summary.T.to_string())


if __name__ == "__main__":
    main()
