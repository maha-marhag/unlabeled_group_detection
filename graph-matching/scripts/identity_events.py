#!/usr/bin/env python3
"""Assign observation IDs and identity groups to temporal communities.

Each detected community receives a snapshot-scoped observation ID:
``PREFIX-CXXYY`` where ``XX`` is the snapshot index and ``YY`` is the
1-based community number inside that snapshot. Identity transfer is recorded
separately as event evidence, so the outputs can distinguish unlabeled dynamic
groups from final labeled communities.
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


def observation_id(approach: str, snapshot_index: int, local_id: int) -> str:
    """Create a snapshot-scoped ID such as OVL-C0205."""
    prefix = APPROACH_PREFIXES.get(approach, approach[:3].upper())
    return f"{prefix}-C{snapshot_index:02d}{local_id + 1:02d}"


def persistent_id(approach: str, sequence: int) -> str:
    """Backward-compatible final-group ID helper."""
    return f"c{sequence:02d}"


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


def eligible_relations(
    relations: list[IdentityRelation],
    score_name: str,
    threshold: float,
) -> list[IdentityRelation]:
    """Return relations that pass the requested directional threshold."""
    return [
        relation
        for relation in relations
        if getattr(relation, score_name) >= threshold
    ]


def unique_best(relations: list[IdentityRelation], score_name: str) -> IdentityRelation | None:
    """Return a unique best relation, or None on a tie."""
    if not relations:
        return None

    best_score = max(getattr(relation, score_name) for relation in relations)
    winners = [
        relation
        for relation in relations
        if getattr(relation, score_name) == best_score
    ]
    return winners[0] if len(winners) == 1 else None


def best_overlaps_to_target(
    source: CommunityRecord,
    target_nodes: frozenset[int],
    next_snapshot: list[CommunityRecord],
) -> list[tuple[CommunityRecord, float]]:
    """Find next-step communities that best preserve source nodes in a target."""
    scored = []
    for candidate in next_snapshot:
        overlap = len(candidate.nodes & target_nodes)
        if overlap == 0:
            continue
        scored.append((candidate, overlap / len(target_nodes)))
    if not scored:
        return []

    best_score = max(score for _, score in scored)
    return [(candidate, score) for candidate, score in scored if score == best_score]


def break_forward_tie(
    all_snapshots: list[list[CommunityRecord]],
    tied_relations: list[IdentityRelation],
    origin_nodes: frozenset[int],
    start_snapshot_index: int,
) -> IdentityRelation | None:
    """Walk forward one snapshot at a time until a tied branch separates."""
    active: dict[int, list[CommunityRecord]] = {
        index: [relation.current]
        for index, relation in enumerate(tied_relations)
    }

    for snapshot_index in range(start_snapshot_index, len(all_snapshots)):
        scores = {}
        next_active: dict[int, list[CommunityRecord]] = {}

        for index, communities in active.items():
            branch_score = max(
                (len(community.nodes & origin_nodes) / len(origin_nodes))
                for community in communities
            )
            scores[index] = branch_score

            if snapshot_index + 1 < len(all_snapshots):
                descendants = []
                for community in communities:
                    descendants.extend(
                        candidate
                        for candidate, _ in best_overlaps_to_target(
                            community,
                            origin_nodes,
                            all_snapshots[snapshot_index + 1],
                        )
                    )
                if descendants:
                    next_active[index] = descendants

        best_score = max(scores.values())
        winners = [index for index, score in scores.items() if score == best_score]
        if len(winners) == 1:
            return tied_relations[winners[0]]
        if not next_active:
            return None
        active = {index: next_active[index] for index in winners if index in next_active}
        if len(active) <= 1:
            return tied_relations[next(iter(active))] if active else None

    return None


def break_backward_tie(
    all_snapshots: list[list[CommunityRecord]],
    tied_relations: list[IdentityRelation],
    origin_nodes: frozenset[int],
    previous_snapshot_index: int,
) -> IdentityRelation | None:
    """Walk backward one snapshot at a time until tied parents separate."""
    active: dict[int, list[CommunityRecord]] = {
        index: [relation.previous]
        for index, relation in enumerate(tied_relations)
    }

    for snapshot_index in range(previous_snapshot_index, -1, -1):
        scores = {}
        next_active: dict[int, list[CommunityRecord]] = {}
        for index, communities in active.items():
            branch_score = max(
                (len(community.nodes & origin_nodes) / len(origin_nodes))
                for community in communities
            )
            scores[index] = branch_score

            if snapshot_index - 1 >= 0:
                ancestors = []
                for community in communities:
                    ancestors.extend(
                        candidate
                        for candidate, _ in best_overlaps_to_target(
                            community,
                            origin_nodes,
                            all_snapshots[snapshot_index - 1],
                        )
                    )
                if ancestors:
                    next_active[index] = ancestors

        best_score = max(scores.values())
        winners = [index for index, score in scores.items() if score == best_score]
        if len(winners) == 1:
            return tied_relations[winners[0]]
        if not next_active:
            return None
        active = {index: next_active[index] for index in winners if index in next_active}
        if len(active) <= 1:
            return tied_relations[next(iter(active))] if active else None

    return None


def choose_best_relation(
    relations: list[IdentityRelation],
    score_name: str,
    all_snapshots: list[list[CommunityRecord]],
    snapshot_index: int,
    origin_nodes: frozenset[int],
    direction: str,
) -> IdentityRelation | None:
    """Choose the best relation and resolve exact ties stepwise."""
    best = unique_best(relations, score_name)
    if best is not None or not relations:
        return best

    best_score = max(getattr(relation, score_name) for relation in relations)
    tied = [
        relation
        for relation in relations
        if getattr(relation, score_name) == best_score
    ]
    if direction == "forward":
        return break_forward_tie(all_snapshots, tied, origin_nodes, snapshot_index)
    return break_backward_tie(all_snapshots, tied, origin_nodes, snapshot_index - 1)


def assign_ids(
    all_snapshots: list[list[CommunityRecord]],
    approach: str,
    jaccard_threshold: float = 0.0,
    stability_threshold: float = 0.4,
) -> tuple[dict[tuple[int, int], str], list[dict]]:
    """Assign observation IDs and return pairwise identity-decision rows."""
    assigned_ids: dict[tuple[int, int], str] = {}
    transitions: list[dict] = []

    if not all_snapshots:
        return assigned_ids, transitions

    for snapshot in all_snapshots:
        for community in snapshot:
            assigned_ids[(community.snapshot_index, community.local_id)] = observation_id(
                approach,
                community.snapshot_index,
                community.local_id,
            )

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
            prev.local_id: choose_best_relation(
                eligible_relations(
                    by_previous.get(prev.local_id, []),
                    "prospective_stability",
                    stability_threshold,
                ),
                "prospective_stability",
                all_snapshots,
                snapshot_index,
                prev.nodes,
                "forward",
            )
            for prev in previous
        }
        retrospective_nominees = {
            curr.local_id: choose_best_relation(
                eligible_relations(
                    by_current.get(curr.local_id, []),
                    "retrospective_stability",
                    stability_threshold,
                ),
                "retrospective_stability",
                all_snapshots,
                snapshot_index,
                curr.nodes,
                "backward",
            )
            for curr in current
        }

        for curr in current:
            inherited_from: CommunityRecord | None = None
            winning_relation: IdentityRelation | None = None
            decision = "new"

            parent_relations = by_current.get(curr.local_id, [])
            if len(parent_relations) == 1:
                candidate = parent_relations[0]
                if (
                    candidate.retrospective_stability >= stability_threshold
                    or candidate.prospective_stability >= stability_threshold
                ):
                    prospective_choice = prospective_nominees[candidate.previous.local_id]
                    parent_has_split = len(by_previous.get(candidate.previous.local_id, [])) > 1
                    if (
                        not parent_has_split
                        or (
                            prospective_choice is not None
                            and prospective_choice.current.local_id == curr.local_id
                        )
                    ):
                        inherited_from = candidate.previous
                        winning_relation = candidate
            elif len(parent_relations) > 1:
                retrospective_choice = retrospective_nominees[curr.local_id]
                if retrospective_choice is not None:
                    prev = retrospective_choice.previous
                    prospective_choice = prospective_nominees[prev.local_id]
                    concurrent_split_merge = len(by_previous.get(prev.local_id, [])) > 1
                    if (
                        not concurrent_split_merge
                        or (
                            prospective_choice is not None
                            and prospective_choice.current.local_id == curr.local_id
                        )
                    ):
                        inherited_from = prev
                        winning_relation = retrospective_choice

            if inherited_from is not None:
                decision = "inherited"

            current_id = assigned_ids[(curr.snapshot_index, curr.local_id)]
            transitions.append(
                transition_row(
                    approach=approach,
                    current=curr,
                    current_id=current_id,
                    inherited_from=inherited_from,
                    relation=winning_relation,
                    decision=decision,
                    candidate_relations=parent_relations,
                    assigned_ids=assigned_ids,
                )
            )

    return assigned_ids, transitions


def build_identity_groups(
    snapshots: list[list[CommunityRecord]],
    assigned_ids: dict[tuple[int, int], str],
    transitions: list[dict],
) -> tuple[dict[str, dict], dict[str, str]]:
    """Assemble inherited observation IDs into identity groups."""
    parent: dict[str, str] = {}

    def find(item: str) -> str:
        parent.setdefault(item, item)
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for snapshot in snapshots:
        for community in snapshot:
            find(assigned_ids[(community.snapshot_index, community.local_id)])

    for transition in transitions:
        if transition["decision"] == "inherited" and transition["from_observation_id"]:
            union(transition["from_observation_id"], transition["observation_id"])

    members_by_root: dict[str, list[CommunityRecord]] = defaultdict(list)
    for snapshot in snapshots:
        for community in snapshot:
            cid = assigned_ids[(community.snapshot_index, community.local_id)]
            members_by_root[find(cid)].append(community)

    last_snapshot = len(snapshots) - 1
    alive_roots = []
    for root, members in members_by_root.items():
        if any(member.snapshot_index == last_snapshot for member in members):
            final_member = sorted(
                [member for member in members if member.snapshot_index == last_snapshot],
                key=lambda item: item.local_id,
            )[0]
            alive_roots.append((final_member.local_id, root))

    final_label_by_root = {
        root: persistent_id("", index)
        for index, (_, root) in enumerate(sorted(alive_roots), start=1)
    }

    groups = {}
    observation_to_group = {}
    for root, members in members_by_root.items():
        ordered = sorted(members, key=lambda item: (item.snapshot_index, item.local_id))
        observation_ids = [
            assigned_ids[(member.snapshot_index, member.local_id)]
            for member in ordered
        ]
        group_id = final_label_by_root.get(root, f"dead-{root}")
        status = "alive" if root in final_label_by_root else "dead"
        group = {
            "identity_group": group_id,
            "status": status,
            "birth_snapshot": ordered[0].snapshot_index,
            "last_snapshot": ordered[-1].snapshot_index,
            "lifespan_snapshots": len({member.snapshot_index for member in ordered}),
            "observation_ids": "=".join(observation_ids),
            "observation_count": len(observation_ids),
        }
        groups[group_id] = group
        for observation in observation_ids:
            observation_to_group[observation] = group_id

    return groups, observation_to_group


def final_community_rows(
    groups: dict[str, dict],
    snapshots: list[list[CommunityRecord]],
    assigned_ids: dict[tuple[int, int], str],
    observation_to_group: dict[str, str],
) -> Iterable[dict]:
    """Return only identity groups alive in the final snapshot."""
    final_size_by_group = {}
    if snapshots:
        for community in snapshots[-1]:
            observation = assigned_ids[(community.snapshot_index, community.local_id)]
            final_size_by_group[observation_to_group[observation]] = len(community.nodes)

    for group in sorted(
        (item for item in groups.values() if item["status"] == "alive"),
        key=lambda item: item["identity_group"],
    ):
        yield {
            "identity_group": group["identity_group"],
            "birth_snapshot": group["birth_snapshot"],
            "last_snapshot": group["last_snapshot"],
            "lifespan_snapshots": group["lifespan_snapshots"],
            "final_size": final_size_by_group[group["identity_group"]],
            "observation_ids": group["observation_ids"],
            "observation_count": group["observation_count"],
            "events": "",
        }


def final_labeled_community_rows(
    snapshots: list[list[CommunityRecord]],
    assigned_ids: dict[tuple[int, int], str],
    observation_to_group: dict[str, str],
) -> Iterable[dict]:
    """Return final-snapshot communities with final labels and member nodes."""
    if not snapshots:
        return

    final_snapshot = snapshots[-1]
    for community in sorted(final_snapshot, key=lambda item: item.local_id):
        current_observation_id = assigned_ids[
            (community.snapshot_index, community.local_id)
        ]
        yield {
            "identity_group": observation_to_group[current_observation_id],
            "final_observation_id": current_observation_id,
            "snapshot_index": community.snapshot_index,
            "snapshot_label": community.snapshot_label,
            "local_id": community.local_id,
            "size": len(community.nodes),
            "nodes_json": json.dumps(sorted(community.nodes)),
        }


def identity_group_rows(groups: dict[str, dict]) -> Iterable[dict]:
    """Return every assembled identity group, including dead groups."""
    for group in sorted(
        groups.values(),
        key=lambda item: (item["status"] != "alive", item["identity_group"]),
    ):
        yield group


def transition_row(
    approach: str,
    current: CommunityRecord,
    current_id: str,
    inherited_from: CommunityRecord | None,
    relation: IdentityRelation | None,
    decision: str,
    candidate_relations: list[IdentityRelation],
    assigned_ids: dict[tuple[int, int], str],
) -> dict:
    """Build one auditable identity-decision row."""
    return {
        "approach": approach,
        "snapshot_index": current.snapshot_index,
        "local_id": current.local_id,
        "observation_id": current_id,
        "decision": decision,
        "from_snapshot": (
            inherited_from.snapshot_index if inherited_from is not None else ""
        ),
        "from_local_id": inherited_from.local_id if inherited_from is not None else "",
        "from_observation_id": (
            assigned_ids[(inherited_from.snapshot_index, inherited_from.local_id)]
            if inherited_from is not None
            else ""
        ),
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
        "candidate_parent_observation_ids": ";".join(
            assigned_ids[(item.previous.snapshot_index, item.previous.local_id)]
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
    observation_to_group: dict[str, str],
) -> Iterable[dict]:
    """Add observation IDs and final identity groups to community records."""
    for snapshot in snapshots:
        for community in snapshot:
            yield {
                "approach": community.approach,
                "snapshot_index": community.snapshot_index,
                "snapshot_label": community.snapshot_label,
                "window_start_ts": community.window_start_ts,
                "window_end_ts": community.window_end_ts,
                "local_id": community.local_id,
                "observation_id": assigned_ids[
                    (community.snapshot_index, community.local_id)
                ],
                "identity_group": observation_to_group[
                    assigned_ids[(community.snapshot_index, community.local_id)]
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
    groups, observation_to_group = build_identity_groups(
        snapshots,
        assigned_ids,
        transitions,
    )
    base = output_dir / approach
    write_csv(
        base / "identified_communities.csv",
        identified_community_rows(snapshots, assigned_ids, observation_to_group),
        [
            "approach",
            "snapshot_index",
            "snapshot_label",
            "window_start_ts",
            "window_end_ts",
            "local_id",
            "observation_id",
            "identity_group",
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
            "observation_id",
            "decision",
            "from_snapshot",
            "from_local_id",
            "from_observation_id",
            "overlap_size",
            "jaccard",
            "prospective_stability",
            "retrospective_stability",
            "candidate_parent_local_ids",
            "candidate_parent_observation_ids",
        ],
    )
    group_fields = [
        "identity_group",
        "status",
            "birth_snapshot",
            "last_snapshot",
            "lifespan_snapshots",
            "observation_ids",
            "observation_count",
        ]
    final_group_fields = [
        "identity_group",
        "birth_snapshot",
        "last_snapshot",
        "lifespan_snapshots",
        "final_size",
        "observation_ids",
        "observation_count",
        "events",
    ]
    write_csv(base / "identity_groups.csv", identity_group_rows(groups), group_fields)
    write_csv(
        base / "final_communities.csv",
        final_community_rows(groups, snapshots, assigned_ids, observation_to_group),
        final_group_fields,
    )
    write_csv(
        base / "final_labeled_communities.csv",
        final_labeled_community_rows(snapshots, assigned_ids, observation_to_group),
        [
            "identity_group",
            "final_observation_id",
            "snapshot_index",
            "snapshot_label",
            "local_id",
            "size",
            "nodes_json",
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
    parser.add_argument("--jaccard-threshold", type=float, default=0.0)
    parser.add_argument("--stability-threshold", type=float, default=0.4)
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
