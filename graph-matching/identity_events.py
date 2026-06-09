#!/usr/bin/env python3
"""Assign persistent IDs to communities across temporal snapshots.

Identity transfer uses three conditions:

1. Jaccard similarity meets the configured graph-matching threshold.
2. The previous community uniquely nominates the current community using
   prospective stability: overlap / previous size.
3. The current community uniquely nominates the previous community using
   retrospective stability: overlap / current size.

Requiring mutual, unique nominations keeps persistent IDs one-to-one through
splits, merges, and combinations of both. Ties do not transfer an ID.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from graph_matching import CommunityRecord, find_project_root, jaccard, write_csv


APPROACH_PREFIXES = {
    "cumulative": "CUM",
    "interval": "INT",
    "overlap": "OVL",
}


@dataclass(frozen=True)
class IdentityRelation:
    """Pairwise identity evidence between consecutive snapshots."""

    previous: CommunityRecord
    current: CommunityRecord
    overlap_size: int
    jaccard: float
    prospective_stability: float
    retrospective_stability: float


def persistent_id(approach: str, sequence: int) -> str:
    """Create an opaque, deterministic ID scoped to one snapshot approach."""
    prefix = APPROACH_PREFIXES.get(approach, approach[:3].upper())
    return f"{prefix}-C{sequence:04d}"


def identity_relations(
    previous: list[CommunityRecord],
    current: list[CommunityRecord],
) -> list[IdentityRelation]:
    """Calculate all non-empty overlaps between two community partitions."""
    relations = []
    for prev in previous:
        for curr in current:
            overlap_size = len(prev.nodes & curr.nodes)
            if overlap_size == 0:
                continue
            relations.append(
                IdentityRelation(
                    previous=prev,
                    current=curr,
                    overlap_size=overlap_size,
                    jaccard=jaccard(prev.nodes, curr.nodes),
                    prospective_stability=overlap_size / len(prev.nodes),
                    retrospective_stability=overlap_size / len(curr.nodes),
                )
            )
    return relations


def unique_best(
    relations: list[IdentityRelation],
    score_name: str,
    threshold: float,
) -> IdentityRelation | None:
    """Return a unique best relation above threshold, or None on a tie."""
    eligible = [
        relation
        for relation in relations
        if getattr(relation, score_name) >= threshold
    ]
    if not eligible:
        return None

    best_score = max(getattr(relation, score_name) for relation in eligible)
    winners = [
        relation
        for relation in eligible
        if getattr(relation, score_name) == best_score
    ]
    return winners[0] if len(winners) == 1 else None


def assign_ids(
    all_snapshots: list[list[CommunityRecord]],
    approach: str,
    jaccard_threshold: float = 0.5,
    stability_threshold: float = 0.5,
) -> tuple[dict[tuple[int, int], str], list[dict]]:
    """Assign persistent IDs and return pairwise identity-decision rows."""
    next_sequence = 1
    assigned_ids: dict[tuple[int, int], str] = {}
    transitions: list[dict] = []

    if not all_snapshots:
        return assigned_ids, transitions

    for community in all_snapshots[0]:
        assigned_ids[(community.snapshot_index, community.local_id)] = persistent_id(
            approach, next_sequence
        )
        next_sequence += 1

    for snapshot_index in range(1, len(all_snapshots)):
        previous = all_snapshots[snapshot_index - 1]
        current = all_snapshots[snapshot_index]
        relations = identity_relations(previous, current)

        by_previous: dict[int, list[IdentityRelation]] = defaultdict(list)
        by_current: dict[int, list[IdentityRelation]] = defaultdict(list)
        for relation in relations:
            if relation.jaccard < jaccard_threshold:
                continue
            by_previous[relation.previous.local_id].append(relation)
            by_current[relation.current.local_id].append(relation)

        prospective_nominees = {
            prev.local_id: unique_best(
                by_previous.get(prev.local_id, []),
                "prospective_stability",
                stability_threshold,
            )
            for prev in previous
        }
        retrospective_nominees = {
            curr.local_id: unique_best(
                by_current.get(curr.local_id, []),
                "retrospective_stability",
                stability_threshold,
            )
            for curr in current
        }

        for curr in current:
            retrospective_choice = retrospective_nominees[curr.local_id]
            inherited_from: CommunityRecord | None = None
            winning_relation: IdentityRelation | None = None

            if retrospective_choice is not None:
                prev = retrospective_choice.previous
                prospective_choice = prospective_nominees[prev.local_id]
                if (
                    prospective_choice is not None
                    and prospective_choice.current.local_id == curr.local_id
                ):
                    inherited_from = prev
                    winning_relation = retrospective_choice

            if inherited_from is None:
                current_id = persistent_id(approach, next_sequence)
                next_sequence += 1
                decision = "new"
            else:
                current_id = assigned_ids[
                    (inherited_from.snapshot_index, inherited_from.local_id)
                ]
                decision = "inherited"

            assigned_ids[(curr.snapshot_index, curr.local_id)] = current_id
            transitions.append(
                transition_row(
                    approach=approach,
                    current=curr,
                    current_id=current_id,
                    inherited_from=inherited_from,
                    relation=winning_relation,
                    decision=decision,
                    candidate_relations=by_current.get(curr.local_id, []),
                )
            )

    return assigned_ids, transitions


def transition_row(
    approach: str,
    current: CommunityRecord,
    current_id: str,
    inherited_from: CommunityRecord | None,
    relation: IdentityRelation | None,
    decision: str,
    candidate_relations: list[IdentityRelation],
) -> dict:
    """Build one auditable identity-decision row."""
    return {
        "approach": approach,
        "snapshot_index": current.snapshot_index,
        "local_id": current.local_id,
        "persistent_id": current_id,
        "decision": decision,
        "from_snapshot": (
            inherited_from.snapshot_index if inherited_from is not None else ""
        ),
        "from_local_id": inherited_from.local_id if inherited_from is not None else "",
        "from_persistent_id": current_id if inherited_from is not None else "",
        "overlap_size": relation.overlap_size if relation is not None else "",
        "jaccard": f"{relation.jaccard:.6f}" if relation is not None else "",
        "prospective_stability": (
            f"{relation.prospective_stability:.6f}" if relation is not None else ""
        ),
        "retrospective_stability": (
            f"{relation.retrospective_stability:.6f}" if relation is not None else ""
        ),
        "candidate_parent_local_ids": ";".join(
            str(item.previous.local_id)
            for item in sorted(
                candidate_relations,
                key=lambda item: (
                    -item.retrospective_stability,
                    -item.prospective_stability,
                    item.previous.local_id,
                ),
            )
        ),
    }


def load_snapshots(path: Path) -> tuple[str, list[list[CommunityRecord]]]:
    """Load phase-one communities.csv into CommunityRecord snapshots."""
    by_snapshot: dict[int, list[CommunityRecord]] = defaultdict(list)
    approach = ""

    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            approach = row["approach"]
            snapshot_index = int(row["snapshot_index"])
            by_snapshot[snapshot_index].append(
                CommunityRecord(
                    approach=approach,
                    snapshot_index=snapshot_index,
                    snapshot_label=row["snapshot_label"],
                    window_start_ts=int(row["window_start_ts"]),
                    window_end_ts=int(row["window_end_ts"]),
                    local_id=int(row["local_id"]),
                    nodes=frozenset(json.loads(row["nodes_json"])),
                )
            )

    if not by_snapshot:
        return approach, []

    snapshots = []
    for snapshot_index in range(max(by_snapshot) + 1):
        records = sorted(by_snapshot.get(snapshot_index, []), key=lambda item: item.local_id)
        snapshots.append(records)
    return approach, snapshots


def identified_community_rows(
    snapshots: list[list[CommunityRecord]],
    assigned_ids: dict[tuple[int, int], str],
) -> Iterable[dict]:
    """Add persistent IDs to the phase-one community records."""
    for snapshot in snapshots:
        for community in snapshot:
            yield {
                "approach": community.approach,
                "snapshot_index": community.snapshot_index,
                "snapshot_label": community.snapshot_label,
                "window_start_ts": community.window_start_ts,
                "window_end_ts": community.window_end_ts,
                "local_id": community.local_id,
                "persistent_id": assigned_ids[
                    (community.snapshot_index, community.local_id)
                ],
                "size": len(community.nodes),
                "nodes_json": json.dumps(sorted(community.nodes)),
            }


def run_approach(
    input_dir: Path,
    output_dir: Path,
    approach: str,
    jaccard_threshold: float,
    stability_threshold: float,
) -> None:
    """Assign IDs for one snapshot approach and write auditable CSV outputs."""
    input_path = input_dir / approach / "communities.csv"
    loaded_approach, snapshots = load_snapshots(input_path)
    if loaded_approach and loaded_approach != approach:
        raise ValueError(
            f"Expected approach {approach!r}, found {loaded_approach!r} in {input_path}."
        )

    assigned_ids, transitions = assign_ids(
        snapshots,
        approach=approach,
        jaccard_threshold=jaccard_threshold,
        stability_threshold=stability_threshold,
    )
    base = output_dir / approach
    write_csv(
        base / "identified_communities.csv",
        identified_community_rows(snapshots, assigned_ids),
        [
            "approach",
            "snapshot_index",
            "snapshot_label",
            "window_start_ts",
            "window_end_ts",
            "local_id",
            "persistent_id",
            "size",
            "nodes_json",
        ],
    )
    write_csv(
        base / "identity_transitions.csv",
        transitions,
        [
            "approach",
            "snapshot_index",
            "local_id",
            "persistent_id",
            "decision",
            "from_snapshot",
            "from_local_id",
            "from_persistent_id",
            "overlap_size",
            "jaccard",
            "prospective_stability",
            "retrospective_stability",
            "candidate_parent_local_ids",
        ],
    )


def parse_args() -> argparse.Namespace:
    project_dir = find_project_root()
    default_input = project_dir / "code" / "graph-matching" / "outputs" / "graph_matching"
    default_output = (
        project_dir / "code" / "graph-matching" / "outputs" / "stage_identification"
    )
    parser = argparse.ArgumentParser(
        description="Assign persistent IDs to temporal Louvain communities."
    )
    parser.add_argument("--input", type=Path, default=default_input)
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument(
        "--approach",
        choices=["interval", "cumulative", "overlap", "all"],
        default="all",
    )
    parser.add_argument("--jaccard-threshold", type=float, default=0.5)
    parser.add_argument("--stability-threshold", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    approaches = (
        ["cumulative", "interval", "overlap"]
        if args.approach == "all"
        else [args.approach]
    )
    for approach in approaches:
        run_approach(
            input_dir=args.input,
            output_dir=args.output,
            approach=approach,
            jaccard_threshold=args.jaccard_threshold,
            stability_threshold=args.stability_threshold,
        )


if __name__ == "__main__":
    main()
