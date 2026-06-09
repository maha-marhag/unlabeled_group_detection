from __future__ import annotations

import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from graph_matching import CommunityRecord
from identity_events import assign_ids


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


def test_split_larger_child_inherits_and_smaller_child_is_new() -> None:
    snapshots = [
        [community(0, 0, set(range(10)))],
        [
            community(1, 0, set(range(6))),
            community(1, 1, set(range(6, 10))),
        ],
    ]

    ids, _ = assign_ids(snapshots, "interval")

    assert ids[(1, 0)] == ids[(0, 0)]
    assert ids[(1, 1)] != ids[(0, 0)]


def test_merge_larger_parent_contribution_inherits() -> None:
    snapshots = [
        [
            community(0, 0, set(range(6))),
            community(0, 1, set(range(6, 10))),
        ],
        [community(1, 0, set(range(10)))],
    ]

    ids, _ = assign_ids(snapshots, "interval")

    assert ids[(1, 0)] == ids[(0, 0)]
    assert ids[(1, 0)] != ids[(0, 1)]


def test_exact_split_tie_creates_new_ids_for_both_children() -> None:
    snapshots = [
        [community(0, 0, set(range(10)))],
        [
            community(1, 0, set(range(5))),
            community(1, 1, set(range(5, 10))),
        ],
    ]

    ids, _ = assign_ids(snapshots, "interval")

    assert ids[(1, 0)] != ids[(0, 0)]
    assert ids[(1, 1)] != ids[(0, 0)]
    assert ids[(1, 0)] != ids[(1, 1)]


def test_when_two_children_exceed_threshold_unique_higher_score_wins() -> None:
    snapshots = [
        [community(0, 0, set(range(10)))],
        [
            community(1, 0, set(range(8))),
            community(1, 1, set(range(6)) | {10}),
        ],
    ]

    ids, _ = assign_ids(snapshots, "interval")

    assert ids[(1, 0)] == ids[(0, 0)]
    assert ids[(1, 1)] != ids[(0, 0)]


def test_below_threshold_overlap_does_not_transfer_id() -> None:
    snapshots = [
        [community(0, 0, set(range(10)))],
        [community(1, 0, {0, 1, 2, 10, 11, 12, 13})],
    ]

    ids, _ = assign_ids(snapshots, "interval")

    assert ids[(1, 0)] != ids[(0, 0)]


def test_simultaneous_split_and_merge_uses_mutual_nomination() -> None:
    snapshots = [
        [
            community(0, 0, set(range(10))),
            community(0, 1, set(range(10, 16))),
        ],
        [
            community(1, 0, set(range(6)) | set(range(10, 12))),
            community(1, 1, set(range(6, 10)) | set(range(12, 16))),
        ],
    ]

    ids, _ = assign_ids(
        snapshots,
        "interval",
        jaccard_threshold=0.4,
        stability_threshold=0.5,
    )

    assert ids[(1, 0)] == ids[(0, 0)]
    assert ids[(1, 1)] == ids[(0, 1)]
    assert len({ids[(1, 0)], ids[(1, 1)]}) == 2
