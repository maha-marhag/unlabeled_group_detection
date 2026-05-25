#!/usr/bin/env python3
"""Temporal community detection and matching for SNAP Email-EU-core.

The pipeline implements the first project phase:
1. keep the active part of the temporal edge list (days 0-526)
2. build graph snapshots with several time-window strategies (interval, cumulative, and overlapping)
3. detect Louvain communities per snapshot
4. calculate Jaccard similarities and match communities across consecutive snapshots.
"""

from __future__ import annotations
import argparse
import csv
import importlib.util
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Iterable

LOCAL_DEPS = Path(__file__).resolve().parent / ".python_deps"
PROJECT_DEPS = Path(__file__).resolve().parent.parent / ".python_deps"
if importlib.util.find_spec("networkx") is None:
    for deps_path in (LOCAL_DEPS, PROJECT_DEPS):
        if deps_path.exists():
            sys.path.insert(0, str(deps_path))

import networkx as nx
import pandas as pd
from networkx.algorithms.community import louvain_communities


SECONDS_PER_DAY = 24 * 60 * 60


# Locate the project root so scripts and notebooks can find the shared dataset.
def find_project_root(start: Path | None = None) -> Path:
    """Find the folder that contains the shared dataset directory."""
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        data_path = candidate / "dataset" / "email-Eu-core-temporal.txt"
        if data_path.exists():
            return candidate

    return Path(__file__).resolve().parent


# Store the timestamp range represented by one graph snapshot.
@dataclass(frozen=True)
class SnapshotWindow:
    index: int
    label: str
    start_ts: int
    end_ts: int

    # Convert the snapshot start from seconds to days for readable outputs.
    @property
    def start_day(self) -> float:
        return self.start_ts / SECONDS_PER_DAY

    # Convert the snapshot end from seconds to days for readable outputs.
    @property
    def end_day(self) -> float:
        return self.end_ts / SECONDS_PER_DAY


# Store one detected community inside one snapshot before any future ID assignment.
@dataclass
class CommunityRecord:
    approach: str
    snapshot_index: int
    snapshot_label: str
    window_start_ts: int
    window_end_ts: int
    local_id: int
    nodes: frozenset[int]


# Load the temporal edge list and keep only the active period used in this phase.
def load_edges(path: Path, cutoff_days: int) -> pd.DataFrame:
    edges = pd.read_csv(path, sep=r"\s+", names=["src", "dst", "ts"], dtype=int)
    cutoff_ts = cutoff_days * SECONDS_PER_DAY
    edges = edges.loc[(edges["ts"] >= 0) & (edges["ts"] < cutoff_ts)].copy()
    edges.sort_values("ts", inplace=True, kind="mergesort")
    return edges


# Build the snapshot windows for interval, cumulative, or overlapping analyses.
def make_windows(
    approach: str,
    cutoff_days: int,
    snapshot_days: int,
    num_snapshots: int | None,
    overlap_fraction: float,
) -> list[SnapshotWindow]:
    snapshot_ts = snapshot_days * SECONDS_PER_DAY
    cutoff_ts = cutoff_days * SECONDS_PER_DAY
    snapshot_count = num_snapshots or ceil(cutoff_ts / snapshot_ts)

    if approach == "interval":
        return [
            SnapshotWindow(
                i,
                f"days_{(i * snapshot_ts) // SECONDS_PER_DAY}_{min((i + 1) * snapshot_ts, cutoff_ts) // SECONDS_PER_DAY}",
                i * snapshot_ts,
                min((i + 1) * snapshot_ts, cutoff_ts),
            )
            for i in range(snapshot_count)
            if i * snapshot_ts < cutoff_ts
        ]

    if approach == "cumulative":
        return [
            SnapshotWindow(
                i,
                f"days_0_{min((i + 1) * snapshot_ts, cutoff_ts) // SECONDS_PER_DAY}",
                0,
                min((i + 1) * snapshot_ts, cutoff_ts),
            )
            for i in range(snapshot_count)
            if i * snapshot_ts < cutoff_ts
        ]

    if approach == "overlap":
        if not 0 <= overlap_fraction < 1:
            raise ValueError("overlap_fraction must be in [0, 1).")
        # With a 50-day snapshot and 0.5 overlap, the stride is 25 days:
        # [0, 50], [25, 75], [50, 100], ... . In interval notation, this is
        # equivalent to taking [ts, ts+1] and [ts+1/2, ts+1/2+1].
        stride_ts = max(1, int(snapshot_ts * (1 - overlap_fraction)))
        windows = []
        start_ts = 0
        index = 0
        while start_ts + snapshot_ts <= cutoff_ts:
            end_ts = start_ts + snapshot_ts
            windows.append(
                SnapshotWindow(
                    index,
                    f"days_{start_ts // SECONDS_PER_DAY}_{end_ts // SECONDS_PER_DAY}",
                    start_ts,
                    end_ts,
                )
            )
            index += 1
            start_ts += stride_ts
        return windows

    raise ValueError(f"Unknown approach: {approach}")


# Select the temporal edges that fall inside one snapshot window.
def edges_for_window(edges: pd.DataFrame, window: SnapshotWindow) -> pd.DataFrame:
    return edges.loc[(edges["ts"] >= window.start_ts) & (edges["ts"] < window.end_ts)]


# Convert a temporal edge slice into an undirected weighted NetworkX graph.
def build_graph(window_edges: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    if window_edges.empty:
        return graph

    weighted_edges = defaultdict(int)
    for src, dst in zip(window_edges["src"], window_edges["dst"]):
        if src == dst:
            continue
        u, v = sorted((int(src), int(dst)))
        weighted_edges[(u, v)] += 1

    graph.add_weighted_edges_from((u, v, weight) for (u, v), weight in weighted_edges.items())
    return graph


# Run Louvain community detection and remove communities smaller than min_size.
def detect_communities(graph: nx.Graph, seed: int, resolution: float, min_size: int) -> list[frozenset[int]]:
    if graph.number_of_nodes() == 0:
        return []

    communities = louvain_communities(graph, weight="weight", seed=seed, resolution=resolution)
    cleaned = [frozenset(int(node) for node in community) for community in communities if len(community) >= min_size]
    return sorted(cleaned, key=lambda community: (-len(community), min(community)))


# Calculate node-overlap similarity between two communities.
def jaccard(left: frozenset[int], right: frozenset[int]) -> float:
    union_size = len(left | right)
    if union_size == 0:
        return 0.0
    return len(left & right) / union_size


# Compare all communities in two consecutive snapshots and keep matches above the threshold.
def match_pair(
    previous: list[CommunityRecord],
    current: list[CommunityRecord],
    threshold: float,
) -> tuple[list[dict], dict[int, list[dict]], dict[int, list[dict]]]:
    matches = []
    prev_to_curr: dict[int, list[dict]] = defaultdict(list)
    curr_to_prev: dict[int, list[dict]] = defaultdict(list)

    for prev in previous:
        for curr in current:
            overlap = len(prev.nodes & curr.nodes)
            if overlap == 0:
                continue
            score = jaccard(prev.nodes, curr.nodes)
            if score < threshold:
                continue
            row = {
                "from_snapshot": prev.snapshot_index,
                "to_snapshot": curr.snapshot_index,
                "from_local_id": prev.local_id,
                "to_local_id": curr.local_id,
                "overlap_size": overlap,
                "jaccard": score,
                "prev_size": len(prev.nodes),
                "curr_size": len(curr.nodes),
            }
            matches.append(row)
            prev_to_curr[prev.local_id].append(row)
            curr_to_prev[curr.local_id].append(row)

    sort_key = lambda row: (-row["jaccard"], -row["overlap_size"], row["from_local_id"], row["to_local_id"])
    for rows in prev_to_curr.values():
        rows.sort(key=sort_key)
    for rows in curr_to_prev.values():
        rows.sort(key=sort_key)
    matches.sort(key=lambda row: (row["from_snapshot"], row["to_snapshot"], row["from_local_id"], row["to_local_id"]))
    return matches, prev_to_curr, curr_to_prev


# Apply pairwise matching across the whole snapshot sequence.
def match_snapshots(all_snapshots: list[list[CommunityRecord]], threshold: float) -> list[dict]:
    matches_out: list[dict] = []
    for snapshot_index in range(1, len(all_snapshots)):
        previous = all_snapshots[snapshot_index - 1]
        current = all_snapshots[snapshot_index]
        matches, _, _ = match_pair(previous, current, threshold)
        matches_out.extend(matches)
    return matches_out


# Write a list of dictionaries to a CSV file with a stable column order.
def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# Run the full phase-one pipeline for one snapshot construction approach.
def run_approach(
    edges: pd.DataFrame,
    approach: str,
    output_dir: Path,
    cutoff_days: int,
    snapshot_days: int,
    num_snapshots: int,
    overlap_fraction: float,
    seed: int,
    resolution: float,
    min_community_size: int,
    match_threshold: float,
) -> None:
    windows = make_windows(approach, cutoff_days, snapshot_days, num_snapshots, overlap_fraction)
    snapshots: list[list[CommunityRecord]] = []
    stats_rows = []

    for window in windows:
        window_edges = edges_for_window(edges, window)
        graph = build_graph(window_edges)
        communities = detect_communities(graph, seed=seed, resolution=resolution, min_size=min_community_size)
        records = [
            CommunityRecord(
                approach=approach,
                snapshot_index=window.index,
                snapshot_label=window.label,
                window_start_ts=window.start_ts,
                window_end_ts=window.end_ts,
                local_id=i,
                nodes=community,
            )
            for i, community in enumerate(communities)
        ]
        snapshots.append(records)
        stats_rows.append(
            {
                "approach": approach,
                "snapshot_index": window.index,
                "snapshot_label": window.label,
                "start_day": f"{window.start_day:.2f}",
                "end_day": f"{window.end_day:.2f}",
                "temporal_edges": len(window_edges),
                "nodes": graph.number_of_nodes(),
                "weighted_edges": graph.number_of_edges(),
                "communities": len(communities),
            }
        )

    matches = match_snapshots(snapshots, match_threshold)

    community_rows = []
    for snapshot in snapshots:
        for community in snapshot:
            community_rows.append(
                {
                    "approach": approach,
                    "snapshot_index": community.snapshot_index,
                    "snapshot_label": community.snapshot_label,
                    "window_start_ts": community.window_start_ts,
                    "window_end_ts": community.window_end_ts,
                    "local_id": community.local_id,
                    "size": len(community.nodes),
                    "nodes_json": json.dumps(sorted(community.nodes)),
                }
            )

    base = output_dir / approach
    write_csv(
        base / "snapshot_stats.csv",
        stats_rows,
        ["approach", "snapshot_index", "snapshot_label", "start_day", "end_day", "temporal_edges", "nodes", "weighted_edges", "communities"],
    )
    write_csv(
        base / "communities.csv",
        community_rows,
        ["approach", "snapshot_index", "snapshot_label", "window_start_ts", "window_end_ts", "local_id", "size", "nodes_json"],
    )
    write_csv(
        base / "matches.csv",
        matches,
        [
            "from_snapshot",
            "to_snapshot",
            "from_local_id",
            "to_local_id",
            "overlap_size",
            "jaccard",
            "prev_size",
            "curr_size",
        ],
    )


# Parse command-line options for running the graph matching pipeline.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run temporal graph matching on SNAP Email-EU-core.")
    project_dir = find_project_root()
    parser.add_argument("--data", type=Path, default=project_dir / "dataset" / "email-Eu-core-temporal.txt")
    parser.add_argument("--output", type=Path, default=Path("outputs/graph_matching"))
    parser.add_argument("--approach", choices=["interval", "cumulative", "overlap", "all"], default="all")
    parser.add_argument("--cutoff-days", type=int, default=526)
    parser.add_argument("--snapshot-days", type=int, default=50)
    parser.add_argument("--num-snapshots", type=int, default=None)
    parser.add_argument("--overlap-fraction", type=float, default=0.5)
    parser.add_argument("--match-threshold", type=float, default=0.5)
    parser.add_argument("--min-community-size", type=int, default=3)
    parser.add_argument("--resolution", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


# Load the data and run the selected snapshot construction approach or all approaches.
def main() -> None:
    args = parse_args()
    approaches = ["cumulative", "interval", "overlap"] if args.approach == "all" else [args.approach]
    edges = load_edges(args.data, cutoff_days=args.cutoff_days)

    for approach in approaches:
        run_approach(
            edges=edges,
            approach=approach,
            output_dir=args.output,
            cutoff_days=args.cutoff_days,
            snapshot_days=args.snapshot_days,
            num_snapshots=args.num_snapshots,
            overlap_fraction=args.overlap_fraction,
            seed=args.seed,
            resolution=args.resolution,
            min_community_size=args.min_community_size,
            match_threshold=args.match_threshold,
        )


if __name__ == "__main__":
    main()
