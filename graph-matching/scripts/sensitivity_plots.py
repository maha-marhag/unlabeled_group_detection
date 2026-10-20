#!/usr/bin/env python3
"""Step-by-step sensitivity figures on the Jaccard threshold and the number of snapshots.

Reads ``outputs/sensitivity_analysis/number_of_groups.csv`` written by
``config_sensitivity.py`` and draws one figure per step.

Step 1 (``step1_groups_vs_jaccard_by_snapshots.png``):
    one subplot per approach; x = Jaccard threshold, y = number of groups,
    one line per snapshot count (10..50). A horizontal dashed line marks a
    number of groups, so the intersections with the five lines can be read off.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "idp_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from graph_matching import find_project_root

APPROACHES = ["cumulative", "interval", "overlap"]
COUNT_COLORS = {10: "#2a78d6", 20: "#eb6834", 30: "#1baf7a", 40: "#eda100", 50: "#4a3aa7"}
COUNT_MARKERS = {10: "o", 20: "s", 30: "^", 40: "D", 50: "v"}
# Round number of groups marked by the dashed line in step 1, chosen close to the
# value that intercepts the most snapshot-count lines.
GROUPS_LINE = {"cumulative": 70, "interval": 200, "overlap": 110}


def plot_step1(grid: pd.DataFrame, out: Path, groups_line: dict[str, int] | None) -> None:
    grid = grid[grid["criterion"] == "jaccard"]
    fig, axes = plt.subplots(1, len(APPROACHES), figsize=(5.2 * len(APPROACHES), 4.4))
    for ax, approach in zip(axes, APPROACHES):
        sub = grid[grid["approach"] == approach]
        for count in sorted(sub["snapshot_count"].unique()):
            line = sub[sub["snapshot_count"] == count].sort_values("threshold")
            ax.plot(line["threshold"], line["number_of_groups"], color=COUNT_COLORS[count],
                    marker=COUNT_MARKERS[count], markersize=4, linewidth=2,
                    label=f"{count} snapshots")
        value = (groups_line or {}).get(approach, GROUPS_LINE[approach])
        ranges = sub.groupby("snapshot_count")["number_of_groups"].agg(["min", "max"])
        hits = int(((ranges["min"] <= value) & (ranges["max"] >= value)).sum())
        ax.axhline(value, color="#52514e", linestyle="dashed", linewidth=1.2)
        ax.annotate(f"{value} groups ({hits}/5 lines)", xy=(0.9, value), xytext=(0, -5),
                    textcoords="offset points", ha="right", va="top", fontsize=8,
                    color="#52514e", bbox=dict(boxstyle="round,pad=0.2", fc="white",
                                               ec="none", alpha=0.85))
        ax.set_title(approach, fontsize=11)
        ax.set_xlabel("Jaccard threshold")
        ax.set_ylabel("number of groups")
        ax.grid(color="#e5e7eb")
        ax.set_axisbelow(True)
        ax.legend(fontsize=8, title="snapshots", title_fontsize=8)
    fig.suptitle("Number of groups vs Jaccard threshold, one line per number of snapshots", fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=170)
    plt.close(fig)


def parse_groups_line(values: list[str] | None) -> dict[str, int] | None:
    """``--groups-line cumulative=70 interval=200`` -> {"cumulative": 70, ...}."""
    if not values:
        return None
    result = {}
    for item in values:
        approach, number = item.split("=")
        result[approach] = int(number)
    return result


def parse_args() -> argparse.Namespace:
    root = find_project_root()
    base = root / "code" / "graph-matching" / "outputs" / "sensitivity_analysis"
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--grid", type=Path, default=base / "number_of_groups.csv")
    parser.add_argument("--figures", type=Path, default=base / "figures")
    parser.add_argument("--groups-line", nargs="*", metavar="APPROACH=N",
                        help="Number of groups for the dashed line, per approach. "
                             f"Default: {GROUPS_LINE}.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.figures.mkdir(parents=True, exist_ok=True)
    grid = pd.read_csv(args.grid)
    plot_step1(grid, args.figures / "step1_groups_vs_jaccard_by_snapshots.png",
               parse_groups_line(args.groups_line))


if __name__ == "__main__":
    main()
