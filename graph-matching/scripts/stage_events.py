#!/usr/bin/env python3
"""Classify temporal community events between consecutive snapshots.

Events are derived from the cardinality of directional stability relations:

- zero-to-one: birth
- one-to-zero: death
- one-to-one: continuation
- one-to-many: split
- many-to-one: merge

A relation participates when its prospective stability or retrospective
stability meets the configured threshold. Jaccard remains an audit metric.

A complex transition may contain both split and merge events.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from graph_matching import CommunityRecord, find_project_root, write_csv
from identity_events import (
    APPROACH_PREFIXES,
    IdentityRelation,
    assign_ids,
    build_identity_groups,
    identity_relations,
    load_snapshots,
)


def accepted_relations(
    previous: list[CommunityRecord],
    current: list[CommunityRecord],
    stability_threshold: float,
) -> tuple[dict[int, list[IdentityRelation]], dict[int, list[IdentityRelation]]]:
    """Index relations accepted by either directional stability measure."""
    by_previous = defaultdict(list)
    by_current = defaultdict(list)
    for relation in identity_relations(previous, current):
        if (
            relation.prospective_stability < stability_threshold
            and relation.retrospective_stability < stability_threshold
        ):
            continue
        by_previous[relation.previous.local_id].append(relation)
        by_current[relation.current.local_id].append(relation)

    relation_key = lambda relation: (
        -relation.jaccard,
        -relation.overlap_size,
        relation.previous.local_id,
        relation.current.local_id,
    )
    for relations in by_previous.values():
        relations.sort(key=relation_key)
    for relations in by_current.values():
        relations.sort(key=relation_key)
    return by_previous, by_current


def classify_events(
    all_snapshots: list[list[CommunityRecord]],
    approach: str,
    assigned_ids: dict[tuple[int, int], str],
    stability_threshold: float = 0.4,
    include_initial_births: bool = True,
) -> list[dict]:
    """Classify lifecycle events over every consecutive snapshot pair."""
    events = []
    event_sequence = 1

    if not all_snapshots:
        return events

    if include_initial_births:
        for community in all_snapshots[0]:
            events.append(
                event_row(
                    approach=approach,
                    event_sequence=event_sequence,
                    event_type="birth",
                    from_snapshot=None,
                    to_snapshot=community.snapshot_index,
                    sources=[],
                    targets=[community],
                    relations=[],
                    assigned_ids=assigned_ids,
                    stability_threshold=stability_threshold,
                )
            )
            event_sequence += 1

    for snapshot_index in range(1, len(all_snapshots)):
        previous = all_snapshots[snapshot_index - 1]
        current = all_snapshots[snapshot_index]
        by_previous, by_current = accepted_relations(
            previous, current, stability_threshold
        )

        for prev in previous:
            child_relations = by_previous.get(prev.local_id, [])
            if not child_relations:
                events.append(
                    event_row(
                        approach,
                        event_sequence,
                        "death",
                        prev.snapshot_index,
                        snapshot_index,
                        [prev],
                        [],
                        [],
                        assigned_ids,
                        stability_threshold,
                    )
                )
                event_sequence += 1
            elif len(child_relations) > 1:
                events.append(
                    event_row(
                        approach,
                        event_sequence,
                        "split",
                        prev.snapshot_index,
                        snapshot_index,
                        [prev],
                        [relation.current for relation in child_relations],
                        child_relations,
                        assigned_ids,
                        stability_threshold,
                    )
                )
                event_sequence += 1

        for curr in current:
            parent_relations = by_current.get(curr.local_id, [])
            if not parent_relations:
                events.append(
                    event_row(
                        approach,
                        event_sequence,
                        "birth",
                        snapshot_index - 1,
                        curr.snapshot_index,
                        [],
                        [curr],
                        [],
                        assigned_ids,
                        stability_threshold,
                    )
                )
                event_sequence += 1
            elif len(parent_relations) > 1:
                events.append(
                    event_row(
                        approach,
                        event_sequence,
                        "merge",
                        snapshot_index - 1,
                        curr.snapshot_index,
                        [relation.previous for relation in parent_relations],
                        [curr],
                        parent_relations,
                        assigned_ids,
                        stability_threshold,
                    )
                )
                event_sequence += 1
            else:
                relation = parent_relations[0]
                if len(by_previous[relation.previous.local_id]) == 1:
                    events.append(
                        event_row(
                            approach,
                            event_sequence,
                            "continuation",
                            relation.previous.snapshot_index,
                            curr.snapshot_index,
                            [relation.previous],
                            [curr],
                            [relation],
                            assigned_ids,
                            stability_threshold,
                        )
                    )
                    event_sequence += 1

    return events


def event_row(
    approach: str,
    event_sequence: int,
    event_type: str,
    from_snapshot: int | None,
    to_snapshot: int,
    sources: list[CommunityRecord],
    targets: list[CommunityRecord],
    relations: list[IdentityRelation],
    assigned_ids: dict[tuple[int, int], str],
    stability_threshold: float,
) -> dict:
    """Build one event row with all participating communities and scores."""

    def ids(communities: list[CommunityRecord]) -> str:
        return ";".join(
            assigned_ids[(community.snapshot_index, community.local_id)]
            for community in communities
        )

    event_prefix = APPROACH_PREFIXES.get(approach, approach[:3].upper())
    return {
        "approach": approach,
        "event_id": f"{event_prefix}-E{event_sequence:04d}",
        "event_type": event_type,
        "from_snapshot": "" if from_snapshot is None else from_snapshot,
        "to_snapshot": to_snapshot,
        "source_local_ids": ";".join(str(item.local_id) for item in sources),
        "source_observation_ids": ids(sources),
        "target_local_ids": ";".join(str(item.local_id) for item in targets),
        "target_observation_ids": ids(targets),
        "source_count": len(sources),
        "target_count": len(targets),
        "overlap_sizes": ";".join(str(item.overlap_size) for item in relations),
        "jaccard_scores": ";".join(f"{item.jaccard:.6f}" for item in relations),
        "prospective_stabilities": ";".join(
            f"{item.prospective_stability:.6f}" for item in relations
        ),
        "retrospective_stabilities": ";".join(
            f"{item.retrospective_stability:.6f}" for item in relations
        ),
        "relation_qualifiers": ";".join(
            relation_qualifier(item, stability_threshold) for item in relations
        ),
    }


def relation_qualifier(
    relation: IdentityRelation,
    stability_threshold: float = 0.4,
) -> str:
    """Describe which directional stability condition accepts a relation."""
    prospective = relation.prospective_stability >= stability_threshold
    retrospective = relation.retrospective_stability >= stability_threshold
    if prospective and retrospective:
        return "both"
    if prospective:
        return "prospective"
    if retrospective:
        return "retrospective"
    return "none"


def add_event(
    events: list[dict],
    approach: str,
    event_sequence: int,
    event_type: str,
    from_snapshot: int | None,
    to_snapshot: int,
    sources: list[CommunityRecord],
    targets: list[CommunityRecord],
    relations: list[IdentityRelation],
    assigned_ids: dict[tuple[int, int], str],
    stability_threshold: float,
) -> int:
    """Append an event and return the next sequence number."""
    events.append(
        event_row(
            approach,
            event_sequence,
            event_type,
            from_snapshot,
            to_snapshot,
            sources,
            targets,
            relations,
            assigned_ids,
            stability_threshold,
        )
    )
    return event_sequence + 1


def event_participants(event: dict) -> list[str]:
    """Return all observation IDs listed in an event row."""
    values = []
    for key in ("source_observation_ids", "target_observation_ids"):
        if event[key]:
            values.extend(event[key].split(";"))
    return values


def event_citation(event: dict) -> str:
    """Format one event with its snapshot or snapshot transition."""
    from_snapshot = event["from_snapshot"]
    to_snapshot = event["to_snapshot"]
    if from_snapshot == "":
        snapshot_ref = f"s{to_snapshot}"
    elif str(from_snapshot) == str(to_snapshot):
        snapshot_ref = f"s{to_snapshot}"
    else:
        snapshot_ref = f"s{from_snapshot}->s{to_snapshot}"
    return f"{event['event_id']}:{event['event_type']}@{snapshot_ref}"


def final_community_event_rows(
    groups: dict[str, dict],
    events: list[dict],
    observation_to_group: dict[str, str],
    snapshots: list[list[CommunityRecord]],
    assigned_ids: dict[tuple[int, int], str],
) -> list[dict]:
    """Return final communities with their full event history."""
    events_by_group: dict[str, list[str]] = defaultdict(list)
    for event in events:
        groups_in_event = {
            observation_to_group[observation]
            for observation in event_participants(event)
            if observation in observation_to_group
        }
        citation = event_citation(event)
        for group in groups_in_event:
            events_by_group[group].append(citation)

    final_size_by_group = {}
    if snapshots:
        for community in snapshots[-1]:
            observation = assigned_ids[(community.snapshot_index, community.local_id)]
            final_size_by_group[observation_to_group[observation]] = len(community.nodes)

    rows = []
    for group in sorted(
        (item for item in groups.values() if item["status"] == "alive"),
        key=lambda item: item["identity_group"],
    ):
        rows.append(
            {
                "identity_group": group["identity_group"],
                "birth_snapshot": group["birth_snapshot"],
                "last_snapshot": group["last_snapshot"],
                "lifespan_snapshots": group["lifespan_snapshots"],
                "final_size": final_size_by_group[group["identity_group"]],
                "observation_ids": group["observation_ids"],
                "observation_count": group["observation_count"],
                "events": ";".join(events_by_group.get(group["identity_group"], [])),
            }
        )
    return rows


def major_event_rows(
    events: list[dict],
    observation_to_group: dict[str, str],
) -> list[dict]:
    """Summarize split and merge involvement by final identity group."""
    by_group: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for event in events:
        event_type = event["event_type"]
        for observation in event_participants(event):
            group = observation_to_group.get(observation)
            if group is not None:
                by_group[group][event_type].append(event["event_id"])

    rows = []
    for group, grouped_events in sorted(by_group.items()):
        rows.append(
            {
                "identity_group": group,
                "birth_events": ";".join(grouped_events.get("birth", [])),
                "continuation_events": ";".join(grouped_events.get("continuation", [])),
                "split_events": ";".join(grouped_events.get("split", [])),
                "merge_events": ";".join(grouped_events.get("merge", [])),
                "death_events": ";".join(grouped_events.get("death", [])),
                "split_count": len(grouped_events.get("split", [])),
                "merge_count": len(grouped_events.get("merge", [])),
            }
        )
    return rows


def overlap_history_rows(
    snapshots: list[list[CommunityRecord]],
    assigned_ids: dict[tuple[int, int], str],
    observation_to_group: dict[str, str],
) -> list[dict]:
    """Record all non-empty inter-snapshot overlaps with percentages."""
    rows = []
    for snapshot_index in range(1, len(snapshots)):
        for relation in identity_relations(snapshots[snapshot_index - 1], snapshots[snapshot_index]):
            source_id = assigned_ids[
                (relation.previous.snapshot_index, relation.previous.local_id)
            ]
            target_id = assigned_ids[
                (relation.current.snapshot_index, relation.current.local_id)
            ]
            rows.append(
                {
                    "from_snapshot": relation.previous.snapshot_index,
                    "to_snapshot": relation.current.snapshot_index,
                    "source_observation_id": source_id,
                    "target_observation_id": target_id,
                    "source_identity_group": observation_to_group[source_id],
                    "target_identity_group": observation_to_group[target_id],
                    "overlap_size": relation.overlap_size,
                    "source_overlap_pct": f"{relation.prospective_stability:.6f}",
                    "target_overlap_pct": f"{relation.retrospective_stability:.6f}",
                    "jaccard": f"{relation.jaccard:.6f}",
                }
            )
    return rows


def overlap_summary_rows(overlap_rows: list[dict]) -> list[dict]:
    """Count how many distinct groups each observation overlaps with."""
    summary: dict[str, set[str]] = defaultdict(set)
    for row in overlap_rows:
        summary[row["source_observation_id"]].add(row["target_identity_group"])
        summary[row["target_observation_id"]].add(row["source_identity_group"])

    return [
        {
            "observation_id": observation_id,
            "overlapped_identity_groups": ";".join(sorted(groups)),
            "overlapped_group_count": len(groups),
        }
        for observation_id, groups in sorted(summary.items())
    ]


def run_approach(
    input_dir: Path,
    output_dir: Path,
    approach: str,
    jaccard_threshold: float,
    stability_threshold: float,
) -> None:
    """Load communities, assign IDs, classify events, and write event CSV."""
    loaded_approach, snapshots = load_snapshots(
        input_dir / approach / "communities.csv"
    )
    if loaded_approach and loaded_approach != approach:
        raise ValueError(
            f"Expected approach {approach!r}, found {loaded_approach!r}."
        )

    assigned_ids, transitions = assign_ids(
        snapshots,
        approach=approach,
        jaccard_threshold=jaccard_threshold,
        stability_threshold=stability_threshold,
    )
    groups, observation_to_group = build_identity_groups(snapshots, assigned_ids, transitions)
    events = classify_events(
        snapshots,
        approach=approach,
        assigned_ids=assigned_ids,
        stability_threshold=stability_threshold,
    )
    overlaps = overlap_history_rows(snapshots, assigned_ids, observation_to_group)
    write_csv(
        output_dir / approach / "community_events.csv",
        events,
        [
            "approach",
            "event_id",
            "event_type",
            "from_snapshot",
            "to_snapshot",
            "source_local_ids",
            "source_observation_ids",
            "target_local_ids",
            "target_observation_ids",
            "source_count",
            "target_count",
            "overlap_sizes",
            "jaccard_scores",
            "prospective_stabilities",
            "retrospective_stabilities",
            "relation_qualifiers",
        ],
    )
    write_csv(
        output_dir / approach / "final_communities.csv",
        final_community_event_rows(
            groups,
            events,
            observation_to_group,
            snapshots,
            assigned_ids,
        ),
        [
            "identity_group",
            "birth_snapshot",
            "last_snapshot",
            "lifespan_snapshots",
            "final_size",
            "observation_ids",
            "observation_count",
            "events",
        ],
    )
    write_csv(
        output_dir / approach / "major_events_by_community.csv",
        major_event_rows(events, observation_to_group),
        [
            "identity_group",
            "birth_events",
            "continuation_events",
            "split_events",
            "merge_events",
            "death_events",
            "split_count",
            "merge_count",
        ],
    )
    write_csv(
        output_dir / approach / "community_overlap_history.csv",
        overlaps,
        [
            "from_snapshot",
            "to_snapshot",
            "source_observation_id",
            "target_observation_id",
            "source_identity_group",
            "target_identity_group",
            "overlap_size",
            "source_overlap_pct",
            "target_overlap_pct",
            "jaccard",
        ],
    )
    write_csv(
        output_dir / approach / "community_overlap_summary.csv",
        overlap_summary_rows(overlaps),
        [
            "observation_id",
            "overlapped_identity_groups",
            "overlapped_group_count",
        ],
    )


def combine_final_communities(output_dir: Path, approaches: list[str]) -> None:
    """Write one final-community table containing every selected approach."""
    rows = []
    for approach in approaches:
        path = output_dir / approach / "final_communities.csv"
        if not path.exists():
            continue
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                rows.append({"approach": approach, **row})

    write_csv(
        output_dir / "final_communities_all_approaches.csv",
        rows,
        [
            "approach",
            "identity_group",
            "birth_snapshot",
            "last_snapshot",
            "lifespan_snapshots",
            "final_size",
            "observation_ids",
            "observation_count",
            "events",
        ],
    )


def parse_args() -> argparse.Namespace:
    project_dir = find_project_root()
    default_input = project_dir / "code" / "graph-matching" / "outputs" / "graph_matching"
    default_output = (
        project_dir / "code" / "graph-matching" / "outputs" / "stage_identification"
    )
    parser = argparse.ArgumentParser(
        description="Classify temporal community lifecycle events."
    )
    parser.add_argument("--input", type=Path, default=default_input)
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument(
        "--approach",
        choices=["interval", "cumulative", "overlap", "all"],
        default="all",
    )
    parser.add_argument(
        "--jaccard-threshold",
        type=float,
        default=0.0,
        help="Minimum Jaccard used for identity inheritance candidates.",
    )
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
    combine_final_communities(args.output, approaches)


if __name__ == "__main__":
    main()
