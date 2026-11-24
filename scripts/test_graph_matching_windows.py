from __future__ import annotations

import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from graph_matching import SECONDS_PER_DAY, make_fixed_windows, make_windows
from visualize_stage_identification import week_label


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


def test_default_windows_are_full_width_and_anchored_at_the_cutoff() -> None:
    overlap = make_windows("overlap", 526, 50, None, .5)
    assert len(overlap) == 20
    assert (overlap[0].start_day, overlap[0].end_day) == (1, 51)
    assert overlap[1].start_day == 26
    assert overlap[-1].end_day == 526

    interval = make_windows("interval", 526, 50, None, .5)
    assert len(interval) == 10
    assert (interval[0].start_day, interval[0].end_day) == (26, 76)
    assert interval[-1].end_day == 526
    assert all(window.end_day - window.start_day == 50 for window in interval + overlap)

    cumulative = make_windows("cumulative", 526, 50, None, .5)
    assert [window.end_ts for window in cumulative] == [window.end_ts for window in interval]
    assert all(window.start_ts == 0 for window in cumulative)


def test_default_windows_match_the_sensitivity_analysis_windows() -> None:
    assert make_windows("overlap", 526, 50, None, .5) == make_fixed_windows("overlap", 526, 50, 2)
    assert make_windows("interval", 526, 50, None, .5) == make_fixed_windows("interval", 526, 50, 1)
    assert make_windows("cumulative", 526, 50, None, .5) == make_fixed_windows("cumulative", 526, 50, 1)


def test_week_label_supports_fractional_snapshot_days() -> None:
    assert week_label("days_10.31_30.94") == "w1.5-4.4"
