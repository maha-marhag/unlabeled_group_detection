#!/usr/bin/env python3
"""Summary of the robustness to the number of snapshots: window width depending on S vs fixed.

Reads the results of the snapshot-count windows from ``main`` and of the fixed 50-day
windows from this branch (``outputs/sensitivity_analysis``) and reports, per approach:

- the share of matched groups that are identical (mean Jaccard >= 0.99) and with mean
  Jaccard >= 0.5, pooled over all pairs of snapshot counts at theta*;
- the best score of the joint threshold search (mean, min, max over the pairs).

Outputs: ``window_width_summary.csv`` and ``figures/window_width_summary.png``
(paired bars: % identical matched groups and mean best score).
"""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "idp_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from graph_matching import find_project_root

APPROACHES = ["cumulative", "interval", "overlap"]
SETUPS = {"variable": ("main", "W depends on S", "#9ca3af"),
          "fixed": (None, "W = 50 days", "#2a78d6")}


def read(base: Path, name: str, ref: str | None) -> pd.DataFrame:
    if ref is None:
        return pd.read_csv(base / name)
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=base, capture_output=True,
                          text=True, check=True).stdout.strip()
    path = (base / name).resolve().relative_to(root)
    text = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=base, capture_output=True,
                          text=True, check=True).stdout
    return pd.read_csv(io.StringIO(text))


def summarise(base: Path) -> pd.DataFrame:
    rows = []
    for setup, (ref, label, _) in SETUPS.items():
        pairs = read(base, "group_matching_pairs.csv", ref)
        joint = read(base, "joint_threshold_search_best.csv", ref)
        for approach in APPROACHES:
            values = pairs.loc[pairs["approach"] == approach, "mean_jaccard"]
            scores = joint.loc[joint["approach"] == approach, "score"]
            if values.empty:
                continue
            rows.append({"approach": approach, "setup": label,
                         "identical_share": round((values >= 0.99).mean(), 3),
                         "share_at_least_0_5": round((values >= 0.5).mean(), 3),
                         "mean_best_score": round(scores.mean(), 3),
                         "min_best_score": round(scores.min(), 3),
                         "max_best_score": round(scores.max(), 3)})
    return pd.DataFrame(rows)


def plot(summary: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    width = 0.38
    x = np.arange(len(APPROACHES))
    for ax, column, title, scale in ((axes[0], "identical_share", "Identical matched groups (%)", 100),
                                     (axes[1], "mean_best_score", "Best score (mean over pairs)", 1)):
        for offset, (_, label, color) in zip((-width / 2, width / 2), SETUPS.values()):
            sub = summary[summary["setup"] == label].set_index("approach")
            heights = [sub[column].get(a, np.nan) * scale for a in APPROACHES]
            bars = ax.bar(x + offset, np.nan_to_num(heights), width, color=color, label=label)
            for bar, height in zip(bars, heights):
                text = "n/a" if np.isnan(height) else (f"{height:.0f}" if scale == 100 else f"{height:.2f}")
                ax.annotate(text, (bar.get_x() + bar.get_width() / 2, 0 if np.isnan(height) else height),
                            xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8,
                            color="#52514e")
        ax.set_xticks(x)
        ax.set_xticklabels(APPROACHES)
        ax.set_ylim(0, 100 if scale == 100 else 1)
        ax.set_title(title, fontsize=11)
        ax.grid(axis="y", color="#e5e7eb")
        ax.set_axisbelow(True)
    axes[0].legend(fontsize=8, loc="upper right")
    fig.suptitle("Robustness to the number of snapshots: window width depending on S vs fixed",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=170)
    plt.close(fig)


def main() -> None:
    base = find_project_root() / "code" / "graph-matching" / "outputs" / "sensitivity_analysis"
    summary = summarise(base)
    summary.to_csv(base / "window_width_summary.csv", index=False)
    plot(summary, base / "figures" / "window_width_summary.png")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
