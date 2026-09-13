from __future__ import annotations

import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from graph_matching import SECONDS_PER_DAY, make_windows


def test_explicit_overlap_snapshot_count_covers_full_period() -> None:
    windows = make_windows("overlap", 526, 50, 50, .5)

    assert len(windows) == 50
    assert windows[0].start_ts == 0
    assert windows[-1].end_ts == 526 * SECONDS_PER_DAY
    assert all(window.start_ts < window.end_ts for window in windows)
    assert all(
        left.start_ts < right.start_ts
        for left, right in zip(windows, windows[1:])
    )
    assert all(
        left.end_ts > right.start_ts
        for left, right in zip(windows, windows[1:])
    )


def test_default_overlap_windows_keep_existing_50_day_behavior() -> None:
    windows = make_windows("overlap", 526, 50, None, .5)

    assert len(windows) == 20
    assert windows[0].start_day == 0
    assert windows[0].end_day == 50
    assert windows[1].start_day == 25
    assert windows[-1].end_day == 525
