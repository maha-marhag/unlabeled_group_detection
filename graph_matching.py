#!/usr/bin/env python3
"""Temporal community detection and matching for SNAP Email-EU-core.

The pipeline implements the first project phase:
1. keep the first part of the temporal edge list,
2. build graph snapshots with several time-window strategies,
3. detect Louvain communities per snapshot,
4. match communities across consecutive snapshots and label events.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
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


@dataclass(frozen=True)
class SnapshotWindow:
    index: int
    label: str
    start_ts: int
    end_ts: int

    @property
    def start_day(self) -> float:
        return self.start_ts / SECONDS_PER_DAY

    @property
    def end_day(self) -> float:
        return self.end_ts / SECONDS_PER_DAY


@dataclass
class CommunityRecord:
    approach: str
    snapshot_index: int
    snapshot_label: str
    window_start_ts: int
    window_end_ts: int
    local_id: int
    persistent_id: str
    nodes: frozenset[int]


def load_edges(path: Path, cutoff_days: int) -> pd.DataFrame:
    edges = pd.read_csv(path, sep=r"\s+", names=["src", "dst", "ts"], dtype=int)
    cutoff_ts = cutoff_days * SECONDS_PER_DAY
    edges = edges.loc[(edges["ts"] >= 0) & (edges["ts"] < cutoff_ts)].copy()
    edges.sort_values("ts", inplace=True, kind="mergesort")
    return edges


def make_windows(
    approach: str,
    cutoff_days: int,
    snapshot_days: int,
    num_snapshots: int,
    overlap_fraction: float,
) -> list[SnapshotWindow]:
    snapshot_ts = snapshot_days * SECONDS_PER_DAY
    cutoff_ts = cutoff_days * SECONDS_PER_DAY

    if approach == "interval":
        return [
            SnapshotWindow(i, f"days_{i * snapshot_days}_{(i + 1) * snapshot_days}", i * snapshot_ts, (i + 1) * snapshot_ts)
            for i in range(num_snapshots)
        ]

    if approach == "cumulative":
        return [
            SnapshotWindow(i, f"days_0_{(i + 1) * snapshot_days}", 0, (i + 1) * snapshot_ts)
            for i in range(num_snapshots)
        ]

    if approach == "overlap":
        if not 0 <= overlap_fraction < 1:
            raise ValueError("overlap_fraction must be in [0, 1).")
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


def edges_for_window(edges: pd.DataFrame, window: SnapshotWindow) -> pd.DataFrame:
    return edges.loc[(edges["ts"] >= window.start_ts) & (edges["ts"] < window.end_ts)]


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


def detect_communities(graph: nx.Graph, seed: int, resolution: float, min_size: int) -> list[frozenset[int]]:
    if graph.number_of_nodes() == 0:
        return []

    communities = louvain_communities(graph, weight="weight", seed=seed, resolution=resolution)
    cleaned = [frozenset(int(node) for node in community) for community in communities if len(community) >= min_size]
    return sorted(cleaned, key=lambda community: (-len(community), min(community)))


def jaccard(left: frozenset[int], right: frozenset[int]) -> float:
    union_size = len(left | right)
    if union_size == 0:
        return 0.0
    return len(left & right) / union_size


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
                "from_persistent_id": prev.persistent_id,
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


def assign_ids_and_events(
    all_snapshots: list[list[CommunityRecord]],
    approach: str,
    threshold: float,
) -> tuple[list[dict], list[dict]]:
    next_id = 1
    matches_out: list[dict] = []
    events_out: list[dict] = []

    for community in all_snapshots[0] if all_snapshots else []:
        community.persistent_id = f"{approach.upper()}-{next_id:04d}"
        next_id += 1
        events_out.append(event_row(approach, "birth", None, community, []))

    for snapshot_index in range(1, len(all_snapshots)):
        previous = all_snapshots[snapshot_index - 1]
        current = all_snapshots[snapshot_index]
        matches, prev_to_curr, curr_to_prev = match_pair(previous, current, threshold)

        for curr in current:
            parent_matches = curr_to_prev.get(curr.local_id, [])
            if not parent_matches:
                curr.persistent_id = f"{approach.upper()}-{next_id:04d}"
                next_id += 1
                events_out.append(event_row(approach, "birth", None, curr, []))
                continue

            best_parent = parent_matches[0]
            siblings = prev_to_curr[best_parent["from_local_id"]]
            is_primary_split_child = siblings[0]["to_local_id"] == curr.local_id
            if len(siblings) == 1 or is_primary_split_child:
                curr.persistent_id = best_parent["from_persistent_id"]
            else:
                curr.persistent_id = f"{approach.upper()}-{next_id:04d}"
                next_id += 1

        for row in matches:
            matched_current = current[row["to_local_id"]]
            row["to_persistent_id"] = matched_current.persistent_id
            matches_out.append(row)

        for prev in previous:
            child_matches = prev_to_curr.get(prev.local_id, [])
            if not child_matches:
                events_out.append(event_row(approach, "death", prev, None, []))
            elif len(child_matches) == 1 and len(curr_to_prev[child_matches[0]["to_local_id"]]) == 1:
                events_out.append(event_row(approach, "continuation", prev, current[child_matches[0]["to_local_id"]], child_matches))
            else:
                event_type = "split"
                if len(child_matches) > 1 and any(len(curr_to_prev[row["to_local_id"]]) > 1 for row in child_matches):
                    event_type = "complex"
                events_out.append(event_row(approach, event_type, prev, None, child_matches))

        for curr in current:
            parent_matches = curr_to_prev.get(curr.local_id, [])
            if len(parent_matches) > 1:
                events_out.append(event_row(approach, "merge", None, curr, parent_matches))

    return matches_out, events_out


def event_row(
    approach: str,
    event_type: str,
    previous: CommunityRecord | None,
    current: CommunityRecord | None,
    matches: list[dict],
) -> dict:
    snapshot_index = current.snapshot_index if current is not None else previous.snapshot_index
    persistent_id = current.persistent_id if current is not None else previous.persistent_id
    local_id = current.local_id if current is not None else previous.local_id
    return {
        "approach": approach,
        "snapshot_index": snapshot_index,
        "event_type": event_type,
        "persistent_id": persistent_id,
        "local_id": local_id,
        "matched_local_ids": ";".join(
            str(row["to_local_id"] if previous is not None else row["from_local_id"]) for row in matches
        ),
        "match_scores": ";".join(f"{row['jaccard']:.4f}" for row in matches),
    }


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


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
                persistent_id="",
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

    matches, events = assign_ids_and_events(snapshots, approach, match_threshold)

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
                    "persistent_id": community.persistent_id,
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
        ["approach", "snapshot_index", "snapshot_label", "window_start_ts", "window_end_ts", "local_id", "persistent_id", "size", "nodes_json"],
    )
    write_csv(
        base / "matches.csv",
        matches,
        [
            "from_snapshot",
            "to_snapshot",
            "from_local_id",
            "to_local_id",
            "from_persistent_id",
            "to_persistent_id",
            "overlap_size",
            "jaccard",
            "prev_size",
            "curr_size",
        ],
    )
    write_csv(
        base / "events.csv",
        events,
        ["approach", "snapshot_index", "event_type", "persistent_id", "local_id", "matched_local_ids", "match_scores"],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run temporal graph matching on SNAP Email-EU-core.")
    script_dir = Path(__file__).resolve().parent
    project_dir = script_dir.parent
    parser.add_argument("--data", type=Path, default=project_dir / "dataset" / "email-Eu-core-temporal.txt")
    parser.add_argument("--output", type=Path, default=Path("outputs/graph_matching"))
    parser.add_argument("--approach", choices=["interval", "cumulative", "overlap", "all"], default="all")
    parser.add_argument("--cutoff-days", type=int, default=500)
    parser.add_argument("--snapshot-days", type=int, default=50)
    parser.add_argument("--num-snapshots", type=int, default=10)
    parser.add_argument("--overlap-fraction", type=float, default=0.5)
    parser.add_argument("--match-threshold", type=float, default=0.3)
    parser.add_argument("--min-community-size", type=int, default=3)
    parser.add_argument("--resolution", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


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
