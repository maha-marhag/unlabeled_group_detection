#!/usr/bin/env python3
"""Sensitivity figures on the Jaccard threshold and the number of snapshots.

Reads ``outputs/sensitivity_analysis/number_of_groups.csv`` written by
``config_sensitivity.py`` and draws the figures below.

``groups_vs_jaccard_by_snapshots.png``:
    one subplot per approach; x = Jaccard threshold, y = number of groups,
    one line per snapshot count (10..50). A horizontal dashed line marks a
    number of groups, so the intersections with the five lines can be read off.

``lifespan_vs_size_at_theta_star.png``, ``groups_at_theta_star.csv``:
    for every snapshot count whose line reaches the dashed value, the Jaccard
    threshold theta* of the intersection is interpolated and the identity
    matching is re-run at exactly theta* on the cached Louvain communities.
    Each resulting dynamic group is drawn by lifespan (days between its first
    and last observation) and maximum size, one colour per snapshot count.
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
import numpy as np
import pandas as pd

from graph_matching import SECONDS_PER_DAY, find_project_root
from identity_events import assign_ids, build_identity_groups, load_snapshots

APPROACHES = ["cumulative", "interval", "overlap"]
COUNT_COLORS = {10: "#2a78d6", 20: "#eb6834", 30: "#1baf7a", 40: "#eda100", 50: "#4a3aa7"}
COUNT_MARKERS = {10: "o", 20: "s", 30: "^", 40: "D", 50: "v"}
# Round number of groups marked by the dashed line, chosen close to the
# value that intercepts the most snapshot-count lines.
GROUPS_LINE = {"cumulative": 70, "interval": 200, "overlap": 110}


def plot_groups_vs_jaccard(grid: pd.DataFrame, out: Path, groups_line: dict[str, int] | None) -> None:
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


def theta_star(line: pd.DataFrame, value: float) -> float | None:
    """Threshold at which a number-of-groups line reaches ``value`` (linear interpolation)."""
    line = line.sort_values("threshold")
    x, y = line["threshold"].to_numpy(), line["number_of_groups"].to_numpy()
    for (x0, y0), (x1, y1) in zip(zip(x, y), zip(x[1:], y[1:])):
        if y0 <= value <= y1 and y1 > y0:
            return float(x0 + (value - y0) * (x1 - x0) / (y1 - y0))
        if y0 == value:
            return float(x0)
    return None


def groups_at_threshold(communities: Path, approach: str, threshold: float) -> pd.DataFrame:
    """Dynamic groups of one run matched with absolute Jaccard >= threshold."""
    _, snapshots = load_snapshots(communities)
    ids, transitions = assign_ids(snapshots, approach, jaccard_threshold=threshold,
                                  criterion="jaccard")
    groups, _ = build_identity_groups(snapshots, ids, transitions)
    by_observation = {ids[(c.snapshot_index, c.local_id)]: c for s in snapshots for c in s}
    rows = []
    for group in groups.values():
        members = [by_observation[o] for o in group["observation_ids"].split("=")]
        ends = [c.window_end_ts / SECONDS_PER_DAY for c in members]
        rows.append({"group": group["identity_group"],
                     "lifespan_days": max(ends) - min(ends),
                     "max_size": max(len(c.nodes) for c in members)})
    return pd.DataFrame(rows)


def plot_lifespan_vs_size(grid: pd.DataFrame, runs: Path, out: Path, table_out: Path,
               groups_line: dict[str, int] | None) -> pd.DataFrame:
    grid = grid[grid["criterion"] == "jaccard"]
    fig, axes = plt.subplots(1, len(APPROACHES), figsize=(5.2 * len(APPROACHES), 4.4))
    table = []
    for ax, approach in zip(axes, APPROACHES):
        value = (groups_line or {}).get(approach, GROUPS_LINE[approach])
        sub = grid[grid["approach"] == approach]
        for count in sorted(sub["snapshot_count"].unique()):
            theta = theta_star(sub[sub["snapshot_count"] == count], value)
            if theta is None:
                continue
            communities = runs / approach / f"n{count}" / "graph_matching" / approach / "communities.csv"
            groups = groups_at_threshold(communities, approach, theta)
            ax.scatter(groups["lifespan_days"], groups["max_size"], s=14, alpha=0.55,
                       color=COUNT_COLORS[count], marker=COUNT_MARKERS[count],
                       label=f"S={count}, θ*={theta:.2f}")
            table.append({"approach": approach, "target_groups": value,
                          "snapshot_count": count, "theta_star": round(theta, 3),
                          "number_of_groups": len(groups),
                          "median_lifespan_days": round(groups["lifespan_days"].median(), 1),
                          "median_max_size": groups["max_size"].median(),
                          "single_snapshot_groups": int((groups["lifespan_days"] == 0).sum())})
        ax.set_yscale("log")
        ax.set_title(f"{approach} ({value} groups)", fontsize=11)
        ax.set_xlabel("lifespan (days)")
        ax.set_ylabel("maximum size (members)")
        ax.grid(color="#e5e7eb")
        ax.set_axisbelow(True)
        ax.legend(fontsize=8)
    fig.suptitle("Dynamic groups at the Jaccard threshold θ* reaching the dashed number of groups",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=170)
    plt.close(fig)
    table = pd.DataFrame(table)
    table.to_csv(table_out, index=False)
    return table


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
    parser.add_argument("--runs", type=Path, default=base / "runs")
    parser.add_argument("--groups-line", nargs="*", metavar="APPROACH=N",
                        help="Number of groups for the dashed line, per approach. "
                             f"Default: {GROUPS_LINE}.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.figures.mkdir(parents=True, exist_ok=True)
    grid = pd.read_csv(args.grid)
    groups_line = parse_groups_line(args.groups_line)
    plot_groups_vs_jaccard(grid, args.figures / "groups_vs_jaccard_by_snapshots.png", groups_line)
    table = plot_lifespan_vs_size(grid, args.runs, args.figures / "lifespan_vs_size_at_theta_star.png",
                                  args.figures.parent / "groups_at_theta_star.csv", groups_line)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
