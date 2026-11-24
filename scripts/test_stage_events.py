from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from graph_matching import CommunityRecord
from identity_events import assign_ids
from stage_events import classify_events


def community(snapshot: int, local_id: int, nodes: set[int]) -> CommunityRecord:
    return CommunityRecord(
        approach="interval",
        snapshot_index=snapshot,
        snapshot_label=f"snapshot_{snapshot}",
        window_start_ts=snapshot,
        window_end_ts=snapshot + 1,
        local_id=local_id,
        nodes=frozenset(nodes),
    )


def event_types(
    snapshots: list[list[CommunityRecord]], stability_threshold: float = 0.5
) -> Counter:
    assigned_ids, _ = assign_ids(
        snapshots,
        "interval",
        jaccard_threshold=0.5,
        stability_threshold=0.5,
    )
    events = classify_events(
        snapshots,
        "interval",
        assigned_ids,
        stability_threshold=stability_threshold,
        include_initial_births=False,
    )
    return Counter(event["event_type"] for event in events)


def test_continuation_is_exclusive_one_to_one() -> None:
    snapshots = [
        [community(0, 0, {1, 2, 3, 4})],
        [community(1, 0, {1, 2, 3, 5})],
    ]

    assert event_types(snapshots) == Counter({"continuation": 1})


def test_unmatched_communities_produce_birth_and_death() -> None:
    snapshots = [
        [community(0, 0, {1, 2, 3})],
        [community(1, 0, {4, 5, 6})],
    ]

    assert event_types(snapshots) == Counter({"death": 1, "birth": 1})


def test_one_to_many_produces_one_split_event() -> None:
    snapshots = [
        [community(0, 0, set(range(10)))],
        [
            community(1, 0, set(range(6))),
            community(1, 1, set(range(4, 10))),
        ],
    ]

    assert event_types(snapshots) == Counter({"split": 1})


def test_many_to_one_produces_one_merge_event() -> None:
    snapshots = [
        [
            community(0, 0, set(range(6))),
            community(0, 1, set(range(4, 10))),
        ],
        [community(1, 0, set(range(10)))],
    ]

    assert event_types(snapshots) == Counter({"merge": 1})


def test_simultaneous_split_and_merge_records_both_event_types() -> None:
    snapshots = [
        [
            community(0, 0, set(range(10))),
            community(0, 1, set(range(5, 15))),
        ],
        [
            community(1, 0, set(range(10))),
            community(1, 1, set(range(5, 15))),
        ],
    ]

    assert event_types(snapshots) == Counter(
        {"split": 2, "merge": 2}
    )


def test_directional_stability_detects_split_below_jaccard_threshold() -> None:
    snapshots = [
        [community(0, 0, set(range(10)))],
        [
            community(1, 0, set(range(6))),
            community(1, 1, set(range(6, 10))),
        ],
    ]

    assert event_types(snapshots) == Counter({"split": 1})
