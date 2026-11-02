#!/usr/bin/env python3
"""Compare the communities of two community detection algorithms at a fixed number of snapshots.

For every approach (cumulative, interval, overlap) with S snapshots, the snapshot
graphs are partitioned by Louvain (the pipeline's algorithm) and by greedy modularity
maximisation (Clauset-Newman-Moore). At every snapshot the two community sets are
compared in a cross table of Jaccard indices (Louvain rows, greedy columns) and
matched one-to-one by linear sum assignment.

Outputs (``outputs/algorithm_comparison``):

- ``crosstabs/{approach}_t{index}.csv``: cross table per snapshot, matched pairs on
  the diagonal (best first), cells with Jaccard 0 left empty.
- ``matched_pairs.csv``: every matched pair of communities with its Jaccard.
- ``snapshot_summary.csv``: one row per approach and snapshot.
- ``approach_summary.csv``: one row per approach.
- ``figures/crosstab_example.png``: one annotated excerpt of a cross table per approach.
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
from networkx.algorithms.community import greedy_modularity_communities
from scipy.optimize import linear_sum_assignment

import graph_matching
from graph_matching import SECONDS_PER_DAY, build_graph, detect_communities, edges_for_window, find_project_root

APPROACHES = ["cumulative", "interval", "overlap"]
SNAPSHOTS = 20
# Same settings as the Louvain runs of the sensitivity analysis.
CUTOFF_DAYS = 526
SNAPSHOT_DAYS = 50
OVERLAP_FRACTION = 0.5
SEED = 42
RESOLUTION = 1.0
MIN_COMMUNITY_SIZE = 3
EXAMPLE_ROWS = 5
EXAMPLE_EXTRA_COLUMNS = 3


def greedy_communities(graph, resolution: float, min_size: int) -> list[frozenset[int]]:
    """Greedy modularity communities, filtered and ordered like ``detect_communities``."""
    if graph.number_of_nodes() == 0:
        return []
    communities = greedy_modularity_communities(graph, weight="weight", resolution=resolution)
    cleaned = [frozenset(int(node) for node in community) for community in communities if len(community) >= min_size]
    return sorted(cleaned, key=lambda community: (-len(community), min(community)))


def windows_for(approach: str):
    # The 20-snapshot overlap run is the baseline construction (50-day windows, 25-day stride).
    count = None if approach == "overlap" and SNAPSHOTS == 20 else SNAPSHOTS
    windows = graph_matching.make_windows(approach, CUTOFF_DAYS, SNAPSHOT_DAYS, count, OVERLAP_FRACTION)
    if len(windows) != SNAPSHOTS:
        raise ValueError(f"{approach}: expected {SNAPSHOTS} windows, got {len(windows)}")
    return windows


def jaccard_table(left: list[frozenset[int]], right: list[frozenset[int]]) -> np.ndarray:
    return np.array([[len(a & b) / len(a | b) for b in right] for a in left])


def compare(edges: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    (out / "crosstabs").mkdir(parents=True, exist_ok=True)
    snapshot_rows, matched_rows, tables = [], [], {}
    for approach in APPROACHES:
        for window in windows_for(approach):
            graph = build_graph(edges_for_window(edges, window))
            louvain = detect_communities(graph, seed=SEED, resolution=RESOLUTION, min_size=MIN_COMMUNITY_SIZE)
            greedy = greedy_communities(graph, resolution=RESOLUTION, min_size=MIN_COMMUNITY_SIZE)
            table = jaccard_table(louvain, greedy)
            r, c = linear_sum_assignment(table, maximize=True)
            order = np.argsort(-table[r, c])
            r, c = r[order], c[order]
            values = table[r, c]
            day = round(window.end_ts / SECONDS_PER_DAY, 1)
            for rank, (k, l, value) in enumerate(zip(r, c, values), start=1):
                matched_rows.append({"approach": approach, "snapshot_index": window.index, "day": day,
                                     "rank": rank, "louvain_size": len(louvain[k]),
                                     "greedy_size": len(greedy[l]), "jaccard": round(value, 4)})
            snapshot_rows.append({
                "approach": approach, "snapshot_index": window.index, "day": day,
                "nodes": graph.number_of_nodes(),
                "louvain_communities": len(louvain), "greedy_communities": len(greedy),
                "matched_pairs": len(values),
                "mean_matched_jaccard": round(float(values.mean()), 3),
                "median_matched_jaccard": round(float(np.median(values)), 3),
                "identical_pairs": int((values >= 0.99).sum()),
                "partners_per_louvain_community": round(float((table > 0).sum(axis=1).mean()), 2),
            })
            # Matched pairs first (best first, C_k <-> C'_k), unmatched communities after them.
            row_order = list(r) + [k for k in range(len(louvain)) if k not in set(r)]
            col_order = list(c) + [l for l in range(len(greedy)) if l not in set(c)]
            frame = pd.DataFrame(
                np.where(table > 0, table, np.nan)[np.ix_(row_order, col_order)].round(3),
                index=[f"C{n + 1} ({len(louvain[k])})" for n, k in enumerate(row_order)],
                columns=[f"C'{n + 1} ({len(greedy[l])})" for n, l in enumerate(col_order)])
            frame.index.name = "louvain \\ greedy"
            frame.to_csv(out / "crosstabs" / f"{approach}_t{window.index:02d}.csv")
            tables[approach, window.index] = frame
        print(f"{approach} done", flush=True)
    return pd.DataFrame(snapshot_rows), pd.DataFrame(matched_rows), tables


def summarise(snapshots: pd.DataFrame, matched: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for approach in APPROACHES:
        snap = snapshots[snapshots["approach"] == approach]
        values = matched.loc[matched["approach"] == approach, "jaccard"]
        rows.append({
            "approach": approach, "snapshots": len(snap),
            "louvain_communities": int(snap["louvain_communities"].sum()),
            "greedy_communities": int(snap["greedy_communities"].sum()),
            "matched_pairs": len(values),
            "mean_matched_jaccard": round(values.mean(), 3),
            "median_matched_jaccard": round(values.median(), 3),
            "identical_share": round((values >= 0.99).mean(), 3),
            "share_at_least_0_5": round((values >= 0.5).mean(), 3),
            "partners_per_louvain_community": round(snap["partners_per_louvain_community"].mean(), 2),
        })
    return pd.DataFrame(rows)


def plot_examples(tables: dict, snapshots: pd.DataFrame, out: Path) -> None:
    """Annotated excerpt per approach: at the snapshot with the median mean matched Jaccard,
    EXAMPLE_ROWS Louvain communities around the median matched rank (typical, not best,
    matches), their matched greedy communities and their strongest other partners."""
    fig, axes = plt.subplots(1, len(APPROACHES), figsize=(5.6 * len(APPROACHES), 4.6))
    cmap = plt.get_cmap("Blues")
    for ax, approach in zip(axes, APPROACHES):
        snap = snapshots[snapshots["approach"] == approach].sort_values("mean_matched_jaccard")
        index = int(snap.iloc[len(snap) // 2]["snapshot_index"])
        day = snap.iloc[len(snap) // 2]["day"]
        table = tables[approach, index].fillna(0)
        matched = min(table.shape)
        first = max(0, min(matched // 2 - EXAMPLE_ROWS // 2, matched - EXAMPLE_ROWS))
        rows = list(range(first, min(first + EXAMPLE_ROWS, matched)))
        others = table.iloc[rows].drop(columns=table.columns[rows]).sum()
        extra = [table.columns.get_loc(c) for c in others[others > 0].nlargest(EXAMPLE_EXTRA_COLUMNS).index]
        excerpt = table.iloc[rows, rows + extra].to_numpy()
        ax.imshow(np.where(excerpt > 0, excerpt, np.nan), cmap=cmap, vmin=0, vmax=1.15)
        for (k, l), value in np.ndenumerate(excerpt):
            if value > 0:
                ax.text(l, k, f"{value:.2f}" if value >= 0.005 else "<0.01", ha="center", va="center",
                        fontsize=9, fontweight="bold" if k == l else "normal",
                        color="white" if value > 0.6 else "#1f2937")
        ax.add_patch(plt.Rectangle((-0.5, -0.5), len(rows), len(rows), fill=False,
                                   edgecolor="#52514e", linewidth=1, linestyle="dashed"))
        ax.set_xticks(range(len(rows) + len(extra)))
        ax.set_xticklabels([table.columns[c] for c in rows + extra], fontsize=7, rotation=45)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([table.index[r] for r in rows], fontsize=8)
        ax.set_xticks(np.arange(-0.5, len(rows) + len(extra)), minor=True)
        ax.set_yticks(np.arange(-0.5, len(rows)), minor=True)
        ax.grid(which="minor", color="#e5e7eb")
        ax.tick_params(which="minor", length=0)
        ax.set_xlabel("greedy modularity communities (size)")
        ax.set_ylabel("Louvain communities (size)")
        ax.set_title(f"{approach}\nsnapshot {index + 1} of {SNAPSHOTS} (day {day:.0f}), "
                     f"matched ranks {first + 1}–{first + len(rows)} of {matched}", fontsize=10)
    fig.suptitle(f"Louvain vs greedy modularity, S={SNAPSHOTS}: Jaccard per pair of communities "
                 "(matched pairs on the diagonal, empty = 0)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    root = find_project_root()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=root / "dataset" / "email-Eu-core-temporal.txt")
    parser.add_argument("--output", type=Path,
                        default=root / "code" / "graph-matching" / "outputs" / "algorithm_comparison")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    (args.output / "figures").mkdir(parents=True, exist_ok=True)
    edges = graph_matching.load_edges(args.data, cutoff_days=CUTOFF_DAYS)
    snapshots, matched, tables = compare(edges, args.output)
    snapshots.to_csv(args.output / "snapshot_summary.csv", index=False)
    matched.to_csv(args.output / "matched_pairs.csv", index=False)
    summary = summarise(snapshots, matched)
    summary.to_csv(args.output / "approach_summary.csv", index=False)
    plot_examples(tables, snapshots, args.output / "figures" / "crosstab_example.png")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
