#!/usr/bin/env python3
"""Average share of identically matched dynamic groups across snapshot counts.

For a pair of snapshot counts (S_i, S_j) with n_i and n_j compared groups and the
linear-sum-assignment matching pi*, a matched pair is identical if its mean Jaccard is
>= IDENTICAL. Two percentages per pair:

- p_matched = identical pairs / min(n_i, n_j)   (share of the matched pairs)
- p_all     = identical pairs / max(n_i, n_j)   (share of all groups of the larger set;
                                                 groups without a partner count as 0)

and their mean, minimum and maximum over the pairs of an approach. Two thresholds:

- theta*: equal-count thresholds per snapshot count (``group_matching_pairs.csv`` and
  ``group_matching_summary.csv`` of ``sensitivity_plots.py``, all groups present at a
  common time point);
- theta_hat: one threshold for all snapshot counts (``fixed_window_sensitivity.py``,
  groups present at >= 2 common time points).

Outputs (``outputs/sensitivity_analysis/fixed_window``): ``matching_percentage_pairs.csv``
and ``matching_percentage_summary.csv``; ``figures/matching_percentage.png`` (one panel per
threshold, mean over the pairs as bars, minimum to maximum as a line).
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
from sensitivity_plots import crosstab, dynamic_groups, time_pairs

IDENTICAL = 0.99
THETA_HAT = {"cumulative": 0.35, "overlap": 0.40}
MEASURES = {"p_matched": ("identical / min(n_i, n_j)", "#2a78d6"),
            "p_all": ("identical / max(n_i, n_j)", "#e8853d")}


def at_theta_star(base: Path) -> pd.DataFrame:
    pairs = pd.read_csv(base / "group_matching_pairs.csv")
    summary = pd.read_csv(base / "group_matching_summary.csv")
    identical = (pairs.assign(identical=pairs["mean_jaccard"] >= IDENTICAL)
                 .groupby(["approach", "s_i", "s_j"])["identical"].sum().rename("identical_pairs"))
    frame = summary.merge(identical.reset_index(), on=["approach", "s_i", "s_j"])
    return frame.assign(threshold="theta*", theta=frame["theta_i"].astype(str) + " / " + frame["theta_j"].astype(str))[
        ["approach", "threshold", "theta", "s_i", "s_j", "compared_i", "compared_j", "identical_pairs"]]


def at_theta_hat(runs: Path) -> pd.DataFrame:
    rows = []
    for approach, theta in THETA_HAT.items():
        paths = sorted((runs / approach).glob(f"n*/graph_matching/{approach}/communities.csv"),
                       key=lambda path: int(path.parts[-4][1:]))
        groups = [dynamic_groups(path, approach, theta) for path in paths]
        for a, (times_i, chron_i) in enumerate(groups):
            for times_j, chron_j in groups[a + 1:]:
                table, r_ids, c_ids = crosstab(chron_i, chron_j, time_pairs(times_i, times_j, approach),
                                               MIN_COMMON_POINTS)
                r, c = linear_sum_assignment(table, maximize=True)
                rows.append({"approach": approach, "threshold": "theta_hat", "theta": str(theta),
                             "s_i": len(times_i), "s_j": len(times_j),
                             "compared_i": len(r_ids), "compared_j": len(c_ids),
                             "identical_pairs": int((table[r, c] >= IDENTICAL).sum())})
    return pd.DataFrame(rows)


def plot(summary: pd.DataFrame, out: Path) -> None:
    approaches = list(THETA_HAT)
    titles = {"theta*": "θ* (equal number of groups)", "theta_hat": "θ̂ (one threshold for all S)"}
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    width = 0.36
    x = np.arange(len(approaches))
    for ax, threshold in zip(axes, titles):
        for offset, (measure, (label, color)) in zip((-width / 2 - 0.01, width / 2 + 0.01), MEASURES.items()):
            rows = summary.loc[[(a, threshold) for a in approaches]]
            mean = rows[f"{measure}_mean"].to_numpy() * 100
            low = rows[f"{measure}_min"].to_numpy() * 100
            high = rows[f"{measure}_max"].to_numpy() * 100
            ax.bar(x + offset, mean, width, color=color, label=label)
            ax.vlines(x + offset, low, high, color="#3f3f46", linewidth=1.2)
            for xi, m, h in zip(x + offset, mean, high):
                ax.annotate(f"{m:.0f}", (xi, h), xytext=(0, 3), textcoords="offset points",
                            ha="center", fontsize=8, color="#3f3f46")
        ax.set_xticks(x)
        ax.set_xticklabels(approaches)
        ax.set_ylim(0, 105)
        ax.set_title(titles[threshold], fontsize=11)
        ax.grid(axis="y", color="#e5e7eb")
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("identical matched groups (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=8, loc="lower center", ncol=2, frameon=False)
    fig.suptitle("Share of identically matched groups, mean over the 10 pairs of snapshot counts "
                 "(line: min–max)", fontsize=11)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(out, dpi=170)
    plt.close(fig)


def main() -> None:
    base = find_project_root() / "code" / "graph-matching" / "outputs" / "sensitivity_analysis"
    frame = pd.concat([at_theta_star(base), at_theta_hat(base / "runs")], ignore_index=True)
    small = frame[["compared_i", "compared_j"]].min(axis=1)
    large = frame[["compared_i", "compared_j"]].max(axis=1)
    frame["p_matched"] = (frame["identical_pairs"] / small).round(3)
    frame["p_all"] = (frame["identical_pairs"] / large).round(3)
    out = base / "fixed_window"
    frame.to_csv(out / "matching_percentage_pairs.csv", index=False)
    summary = frame.groupby(["approach", "threshold"], sort=False).agg(
        pairs=("p_all", "size"),
        p_matched_mean=("p_matched", "mean"), p_matched_min=("p_matched", "min"),
        p_matched_max=("p_matched", "max"),
        p_all_mean=("p_all", "mean"), p_all_min=("p_all", "min"), p_all_max=("p_all", "max")).round(3)
    summary.to_csv(out / "matching_percentage_summary.csv")
    plot(summary, base / "figures" / "matching_percentage.png")
    print(frame.to_string(index=False))
    print(summary.to_string())


if __name__ == "__main__":
    main()
