#!/usr/bin/env python3
"""Sensitivity figures on the Jaccard threshold and the number of snapshots.

Reads ``outputs/sensitivity_analysis/number_of_groups.csv`` written by
``config_sensitivity.py`` and draws the figures below.

``groups_vs_jaccard_by_snapshots.png``:
    one subplot per approach; x = Jaccard threshold, y = number of groups,
    one line per snapshot count (fixed 50-day windows, see ``config_sensitivity.py``:
    10, 20, 29, 39, 48 snapshots; interval only 10). A horizontal dashed line marks a
    number of groups, so the intersections with the five lines can be read off.

``lifespan_classes_at_theta_star.png``, ``groups_at_theta_star.csv``:
    for every snapshot count whose line reaches the dashed value, the Jaccard
    threshold theta* of the intersection is interpolated and the identity
    matching is re-run at exactly theta* on the cached Louvain communities.
    Per snapshot count, two bars: groups observed in a single snapshot and
    groups living at least LONG_LIVED_DAYS days (between first and last window end).

``crosstabs/{approach}_S{i}_vs_S{j}.csv``, ``group_matching_summary.csv``,
``group_matching_pairs.csv``:
    for every pair of snapshot counts S_i < S_j reaching the dashed value, the
    dynamic groups at theta* are compared over their common time points (the window
    ends shared by both runs; with fixed-width windows anchored at the cutoff they
    coincide exactly).
    The cross table holds the mean Jaccard of the member sets of every pair of
    groups over the common time points at which they overlap (cells equal to 0 are
    left empty), and the groups are matched one-to-one by linear sum assignment.

``crosstab_example_S20_vs_S39.png``:
    one small excerpt of the cross table per approach with both snapshot counts, with the Jaccard value
    written in each cell (empty where 0). Rows: EXAMPLE_ROWS consecutive groups of
    S_i around the median matched rank. Columns: their matched groups of S_j
    (diagonal) followed by up to EXAMPLE_EXTRA_COLUMNS other partners with the
    largest Jaccard sum over these rows.
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
from scipy.optimize import linear_sum_assignment

from graph_matching import SECONDS_PER_DAY, find_project_root
from identity_events import assign_ids, build_identity_groups, load_snapshots

APPROACHES = ["cumulative", "interval", "overlap"]
COUNT_COLORS = {10: "#2a78d6", 20: "#eb6834", 29: "#1baf7a", 39: "#eda100", 48: "#4a3aa7"}
COUNT_MARKERS = {10: "o", 20: "s", 29: "^", 39: "D", 48: "v"}
# Round number of groups marked by the dashed line, chosen close to the
# value that intercepts the most snapshot-count lines.
GROUPS_LINE = {"cumulative": 70, "interval": 110, "overlap": 110}
LONG_LIVED_DAYS = 100
EXAMPLE_ROWS = 5
EXAMPLE_EXTRA_COLUMNS = 3


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
        ax.annotate(f"{value} groups ({hits}/{len(ranges)} lines)", xy=(0.9, value), xytext=(0, -5),
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


def dynamic_groups(communities: Path, approach: str, threshold: float
                   ) -> tuple[list[float], dict[str, dict[float, frozenset[int]]]]:
    """Time points (window ends, days) and chronicles {group: {t: U(D, t)}} of one run
    matched with absolute Jaccard >= threshold."""
    _, snapshots = load_snapshots(communities)
    ids, transitions = assign_ids(snapshots, approach, jaccard_threshold=threshold,
                                  criterion="jaccard")
    groups, _ = build_identity_groups(snapshots, ids, transitions)
    by_observation = {ids[(c.snapshot_index, c.local_id)]: c for s in snapshots for c in s}
    times = [s[0].window_end_ts / SECONDS_PER_DAY for s in snapshots]
    chronicles = {}
    for group in groups.values():
        chronicle: dict[float, frozenset[int]] = {}
        for observation in group["observation_ids"].split("="):
            community = by_observation[observation]
            t = community.window_end_ts / SECONDS_PER_DAY
            chronicle[t] = chronicle.get(t, frozenset()) | frozenset(community.nodes)
        chronicles[group["identity_group"]] = chronicle
    return times, chronicles


def groups_at_threshold(communities: Path, approach: str, threshold: float) -> pd.DataFrame:
    """Lifespan and maximum size of the dynamic groups of one run."""
    _, chronicles = dynamic_groups(communities, approach, threshold)
    return pd.DataFrame([{"group": group,
                          "lifespan_days": max(chronicle) - min(chronicle),
                          "max_size": max(len(members) for members in chronicle.values())}
                         for group, chronicle in chronicles.items()])


def plot_lifespan_classes(grid: pd.DataFrame, runs: Path, out: Path, table_out: Path,
                          groups_line: dict[str, int] | None) -> pd.DataFrame:
    grid = grid[grid["criterion"] == "jaccard"]
    table = []
    for approach in APPROACHES:
        value = (groups_line or {}).get(approach, GROUPS_LINE[approach])
        sub = grid[grid["approach"] == approach]
        for count in sorted(sub["snapshot_count"].unique()):
            theta = theta_star(sub[sub["snapshot_count"] == count], value)
            if theta is None:
                continue
            communities = runs / approach / f"n{count}" / "graph_matching" / approach / "communities.csv"
            groups = groups_at_threshold(communities, approach, theta)
            table.append({"approach": approach, "target_groups": value,
                          "snapshot_count": count, "theta_star": round(theta, 3),
                          "number_of_groups": len(groups),
                          "median_lifespan_days": round(groups["lifespan_days"].median(), 1),
                          "median_max_size": groups["max_size"].median(),
                          "single_snapshot_groups": int((groups["lifespan_days"] == 0).sum()),
                          "long_lived_groups": int((groups["lifespan_days"] >= LONG_LIVED_DAYS).sum())})
    table = pd.DataFrame(table)
    table.to_csv(table_out, index=False)

    fig, axes = plt.subplots(1, len(APPROACHES), figsize=(5.2 * len(APPROACHES), 4.4), sharey=True)
    width = 0.38
    for ax, approach in zip(axes, APPROACHES):
        sub = table[table["approach"] == approach]
        x = np.arange(len(sub))
        for offset, column, color, label in (
            (-width / 2, "single_snapshot_groups", "#9ca3af", "observed in one snapshot only"),
            (width / 2, "long_lived_groups", "#2a78d6", f"living ≥ {LONG_LIVED_DAYS} days"),
        ):
            bars = ax.bar(x + offset, sub[column], width, color=color, label=label)
            ax.bar_label(bars, fontsize=8, color="#52514e")
        ax.set_xticks(x)
        ax.set_xticklabels([f"S={c}\nθ*={t:.2f}" for c, t in zip(sub["snapshot_count"], sub["theta_star"])],
                           fontsize=8)
        ax.set_title(f"{approach} ({sub['target_groups'].iloc[0]} groups)", fontsize=11)
        ax.grid(axis="y", color="#e5e7eb")
        ax.set_axisbelow(True)
        ax.legend(fontsize=8)
    axes[0].set_ylabel("number of dynamic groups")
    fig.suptitle("Short-lived and long-lived dynamic groups at the Jaccard threshold θ*", fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=170)
    plt.close(fig)
    return table


def time_pairs(times_i: list[float], times_j: list[float], approach: str
               ) -> list[tuple[float, float]]:
    """Common time points P_ij of two runs, S_i having fewer snapshots than S_j."""
    common = {round(t, 6) for t in times_i} & {round(t, 6) for t in times_j}
    return [(t, t) for t in times_i if round(t, 6) in common]


def crosstab(chronicles_i: dict, chronicles_j: dict, pairs: list[tuple[float, float]],
             min_points: int = 1) -> tuple[np.ndarray, list[str], list[str]]:
    """Mean Jaccard over the common time points at which the two groups overlap (J_t > 0).

    Time points with J_t = 0 (one group missing or no shared member) are left out of the
    sum and of the count; a pair that never overlaps gets 0.

    Groups that exist at fewer than ``min_points`` common time points are dropped.
    """
    rows = [g for g, c in chronicles_i.items() if sum(t in c for t, _ in pairs) >= min_points]
    cols = [g for g, c in chronicles_j.items() if sum(t in c for _, t in pairs) >= min_points]
    if not rows or not cols:
        return np.zeros((len(rows), len(cols))), rows, cols
    present_i = np.array([[t in chronicles_i[g] for t, _ in pairs] for g in rows])
    present_j = np.array([[t in chronicles_j[g] for _, t in pairs] for g in cols])
    total = np.zeros((len(rows), len(cols)))
    overlapping = np.zeros((len(rows), len(cols)))
    for p, (t_i, t_j) in enumerate(pairs):
        alive_i = [(k, chronicles_i[rows[k]][t_i]) for k in np.flatnonzero(present_i[:, p])]
        alive_j = [(l, chronicles_j[cols[l]][t_j]) for l in np.flatnonzero(present_j[:, p])]
        for k, left in alive_i:
            for l, right in alive_j:
                shared = len(left & right)
                if shared:
                    total[k, l] += shared / len(left | right)
                    overlapping[k, l] += 1
    return np.divide(total, overlapping, out=np.zeros_like(total), where=overlapping > 0), rows, cols


def compare_snapshot_counts(grid: pd.DataFrame, runs: Path, out_dir: Path,
                            groups_line: dict[str, int] | None) -> pd.DataFrame:
    grid = grid[grid["criterion"] == "jaccard"]
    summary, matched = [], []
    (out_dir / "crosstabs").mkdir(exist_ok=True)
    for approach in APPROACHES:
        value = (groups_line or {}).get(approach, GROUPS_LINE[approach])
        sub = grid[grid["approach"] == approach]
        runs_at = {}
        for count in sorted(sub["snapshot_count"].unique()):
            theta = theta_star(sub[sub["snapshot_count"] == count], value)
            if theta is not None:
                communities = runs / approach / f"n{count}" / "graph_matching" / approach / "communities.csv"
                runs_at[count] = (theta, *dynamic_groups(communities, approach, theta))
        counts = sorted(runs_at)
        for a, s_i in enumerate(counts):
            for b, s_j in enumerate(counts):
                if b <= a:
                    continue
                _, times_i, chron_i = runs_at[s_i]
                _, times_j, chron_j = runs_at[s_j]
                pairs = time_pairs(times_i, times_j, approach)
                table, rows, cols = crosstab(chron_i, chron_j, pairs)
                r, c = linear_sum_assignment(table, maximize=True)
                order = np.argsort(-table[r, c])
                r, c = r[order], c[order]
                values = table[r, c]
                for n, (k, l, v) in enumerate(zip(r, c, values), start=1):
                    matched.append({"approach": approach, "s_i": s_i, "s_j": s_j, "rank": n,
                                    "group_i": rows[k], "group_j": cols[l], "mean_jaccard": round(v, 4)})
                summary.append({"approach": approach, "s_i": s_i, "s_j": s_j,
                                "theta_i": round(runs_at[s_i][0], 3), "theta_j": round(runs_at[s_j][0], 3),
                                "time_points_i": len(times_i), "time_points_j": len(times_j),
                                "common_time_points": len(pairs),
                                "groups_i": len(chron_i), "groups_j": len(chron_j),
                                "excluded_i": len(chron_i) - len(rows), "excluded_j": len(chron_j) - len(cols),
                                "compared_i": len(rows), "compared_j": len(cols),
                                "mean_chronicle_length_i": round(float(np.mean(
                                    [sum(t in chron_i[g] for t, _ in pairs) for g in rows])), 1),
                                "mean_chronicle_length_j": round(float(np.mean(
                                    [sum(t in chron_j[g] for _, t in pairs) for g in cols])), 1),
                                "matched_pairs": len(values),
                                "mean_matched_jaccard": round(values.mean(), 3),
                                "median_matched_jaccard": round(float(np.median(values)), 3)})
                # Matched pairs first (best first, D_k <-> D'_k), unmatched groups after them.
                row_order = list(r) + [k for k in range(len(rows)) if k not in set(r)]
                col_order = list(c) + [l for l in range(len(cols)) if l not in set(c)]
                # Pairs of groups with Jaccard 0 are left empty.
                crosstab_frame = pd.DataFrame(
                    np.where(table > 0, table, np.nan)[np.ix_(row_order, col_order)].round(3),
                    index=[f"D{n + 1} ({rows[k]})" for n, k in enumerate(row_order)],
                    columns=[f"D'{n + 1} ({cols[l]})" for n, l in enumerate(col_order)])
                crosstab_frame.index.name = f"S={s_i} \\ S={s_j}"
                crosstab_frame.to_csv(out_dir / "crosstabs" / f"{approach}_S{s_i}_vs_S{s_j}.csv")
    pd.DataFrame(matched).to_csv(out_dir / "group_matching_pairs.csv", index=False)
    summary = pd.DataFrame(summary)
    summary.to_csv(out_dir / "group_matching_summary.csv", index=False)
    return summary


def plot_crosstab_examples(crosstabs: Path, out: Path, s_i: int, s_j: int) -> None:
    approaches = [a for a in APPROACHES if (crosstabs / f"{a}_S{s_i}_vs_S{s_j}.csv").exists()]
    fig, axes = plt.subplots(1, len(approaches), figsize=(5.4 * len(approaches), 3.9), squeeze=False)
    cmap = plt.get_cmap("Blues")
    for ax, approach in zip(axes[0], approaches):
        table = pd.read_csv(crosstabs / f"{approach}_S{s_i}_vs_S{s_j}.csv", index_col=0).fillna(0)
        matched = min(table.shape)
        first = max(0, min(matched // 2 - EXAMPLE_ROWS // 2, matched - EXAMPLE_ROWS))
        rows = list(range(first, first + EXAMPLE_ROWS))
        others = table.iloc[rows].drop(columns=table.columns[rows]).sum()
        extra = [table.columns.get_loc(c) for c in others[others > 0].nlargest(EXAMPLE_EXTRA_COLUMNS).index]
        excerpt = table.iloc[rows, rows + extra].to_numpy()
        ax.imshow(np.where(excerpt > 0, excerpt, np.nan), cmap=cmap, vmin=0, vmax=1.15)
        for (k, l), value in np.ndenumerate(excerpt):
            if value > 0:
                ax.text(l, k, f"{value:.2f}" if value >= 0.005 else "<0.01", ha="center", va="center", fontsize=9,
                        fontweight="bold" if k == l else "normal",
                        color="white" if value > 0.6 else "#1f2937")
        ax.add_patch(plt.Rectangle((-0.5, -0.5), EXAMPLE_ROWS, EXAMPLE_ROWS, fill=False,
                                   edgecolor="#52514e", linewidth=1, linestyle="dashed"))
        ax.set_xticks(range(len(rows) + len(extra)))
        ax.set_xticklabels([table.columns[c].split(" ")[0] for c in rows + extra], fontsize=8)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([table.index[r].split(" ")[0] for r in rows], fontsize=8)
        ax.set_xticks(np.arange(-0.5, len(rows) + len(extra)), minor=True)
        ax.set_yticks(np.arange(-0.5, len(rows)), minor=True)
        ax.grid(which="minor", color="#e5e7eb")
        ax.tick_params(which="minor", length=0)
        ax.set_xlabel(f"dynamic groups, S={s_j}")
        ax.set_ylabel(f"dynamic groups, S={s_i}")
        ax.set_title(f"{approach}\nmatched ranks {first + 1}–{first + EXAMPLE_ROWS} of {matched}", fontsize=10)
    fig.suptitle(f"Excerpt of the cross table, S={s_i} vs S={s_j}: mean Jaccard per pair of groups "
                 "(matched pairs on the diagonal, empty = 0)", fontsize=11)
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
    table = plot_lifespan_classes(grid, args.runs, args.figures / "lifespan_classes_at_theta_star.png",
                                  args.figures.parent / "groups_at_theta_star.csv", groups_line)
    print(table.to_string(index=False))
    summary = compare_snapshot_counts(grid, args.runs, args.figures.parent, groups_line)
    print(summary.to_string(index=False))
    plot_crosstab_examples(args.figures.parent / "crosstabs",
                           args.figures / "crosstab_example_S20_vs_S39.png", 20, 39)


if __name__ == "__main__":
    main()
