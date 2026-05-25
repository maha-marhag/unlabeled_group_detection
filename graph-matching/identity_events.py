#!/usr/bin/env python3
"""Future phase: persistent community IDs and lifecycle event classification.

This module is intentionally separate from ``graph_matching.py``. The current
project phase stops after community detection and Jaccard-based matching. The
functions below keep the earlier identity/event logic available for the next
phase without including it in the phase-one outputs.
"""

from __future__ import annotations

from dataclasses import dataclass

from graph_matching import CommunityRecord, match_pair


# Pair a phase-one community record with a future persistent identifier.
@dataclass
class IdentifiedCommunity:
    record: CommunityRecord
    persistent_id: str


# Future-phase helper that assigns persistent IDs and derives lifecycle events.
def assign_ids_and_events(
    all_snapshots: list[list[CommunityRecord]],
    approach: str,
    threshold: float,
) -> tuple[dict[tuple[int, int], str], list[dict], list[dict]]:
    next_id = 1
    assigned_ids: dict[tuple[int, int], str] = {}
    matches_out: list[dict] = []
    events_out: list[dict] = []

    for community in all_snapshots[0] if all_snapshots else []:
        persistent_id = f"{approach.upper()}-{next_id:04d}"
        assigned_ids[(community.snapshot_index, community.local_id)] = persistent_id
        next_id += 1
        events_out.append(event_row(approach, "birth", None, community, assigned_ids, []))

    for snapshot_index in range(1, len(all_snapshots)):
        previous = all_snapshots[snapshot_index - 1]
        current = all_snapshots[snapshot_index]
        matches, prev_to_curr, curr_to_prev = match_pair(previous, current, threshold)

        for curr in current:
            parent_matches = curr_to_prev.get(curr.local_id, [])
            if not parent_matches:
                persistent_id = f"{approach.upper()}-{next_id:04d}"
                assigned_ids[(curr.snapshot_index, curr.local_id)] = persistent_id
                next_id += 1
                events_out.append(event_row(approach, "birth", None, curr, assigned_ids, []))
                continue

            best_parent = parent_matches[0]
            siblings = prev_to_curr[best_parent["from_local_id"]]
            is_primary_split_child = siblings[0]["to_local_id"] == curr.local_id
            if len(siblings) == 1 or is_primary_split_child:
                persistent_id = assigned_ids[(best_parent["from_snapshot"], best_parent["from_local_id"])]
            else:
                persistent_id = f"{approach.upper()}-{next_id:04d}"
                next_id += 1
            assigned_ids[(curr.snapshot_index, curr.local_id)] = persistent_id

        for row in matches:
            row = dict(row)
            row["from_persistent_id"] = assigned_ids[(row["from_snapshot"], row["from_local_id"])]
            row["to_persistent_id"] = assigned_ids[(row["to_snapshot"], row["to_local_id"])]
            matches_out.append(row)

        for prev in previous:
            child_matches = prev_to_curr.get(prev.local_id, [])
            if not child_matches:
                events_out.append(event_row(approach, "death", prev, None, assigned_ids, []))
            elif len(child_matches) == 1 and len(curr_to_prev[child_matches[0]["to_local_id"]]) == 1:
                events_out.append(event_row(approach, "continuation", prev, current[child_matches[0]["to_local_id"]], assigned_ids, child_matches))
            else:
                event_type = "split"
                if len(child_matches) > 1 and any(len(curr_to_prev[row["to_local_id"]]) > 1 for row in child_matches):
                    event_type = "complex"
                events_out.append(event_row(approach, event_type, prev, None, assigned_ids, child_matches))

        for curr in current:
            parent_matches = curr_to_prev.get(curr.local_id, [])
            if len(parent_matches) > 1:
                events_out.append(event_row(approach, "merge", None, curr, assigned_ids, parent_matches))

    return assigned_ids, matches_out, events_out


# Build one lifecycle-event output row for the future ID/event phase.
def event_row(
    approach: str,
    event_type: str,
    previous: CommunityRecord | None,
    current: CommunityRecord | None,
    assigned_ids: dict[tuple[int, int], str],
    matches: list[dict],
) -> dict:
    community = current if current is not None else previous
    if community is None:
        raise ValueError("Either previous or current community must be provided.")

    return {
        "approach": approach,
        "snapshot_index": community.snapshot_index,
        "event_type": event_type,
        "persistent_id": assigned_ids[(community.snapshot_index, community.local_id)],
        "local_id": community.local_id,
        "matched_local_ids": ";".join(
            str(row["to_local_id"] if previous is not None else row["from_local_id"]) for row in matches
        ),
        "match_scores": ";".join(f"{row['jaccard']:.4f}" for row in matches),
    }
