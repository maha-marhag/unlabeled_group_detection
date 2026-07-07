#!/usr/bin/env python3
"""Analyze final labeled dynamic groups with classic and event-based stages.

The baseline input is the final labeled group output produced by
``stage_events.py``.  This script keeps the final labels (``c01``, ``c02``, ...)
and builds the membership structure required by the stage-identification
package from ``v020.zip``:

    (u, g, t) = (member, final labeled group, snapshot index)

It then runs two segmentation approaches:

1. classic size-based bottom-up segmentation from the professor's package;
2. event-delimited segmentation where split/merge transitions define the
   segment boundaries.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import os
import re
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "idp_matplotlib"))

from graph_matching import find_project_root, write_csv


APPROACHES = ["cumulative", "interval", "overlap"]
EVENT_PATTERN = re.compile(
    r"(?P<event_id>[^:;]+):(?P<event_type>[^@;]+)@s(?P<from>\d+)->s(?P<to>\d+)"
)


def load_professor_package(project_root: Path):
    """Import the group-analysis package from the provided v020.zip archive."""
    if not hasattr(itertools, "pairwise"):
        def pairwise(iterable):
            iterator = iter(iterable)
            previous = next(iterator, None)
            for current in iterator:
                yield previous, current
                previous = current

        itertools.pairwise = pairwise  # type: ignore[attr-defined]

    try:
        from group_analysis import Group, System  # type: ignore

        return Group, System
    except ImportError:
        pass

    archive_path = project_root / "v020.zip"
    if not archive_path.exists():
        raise FileNotFoundError(f"Missing professor package archive: {archive_path}")

    tmpdir = tempfile.TemporaryDirectory(prefix="idp_group_analysis_")
    with zipfile.ZipFile(archive_path) as archive:
        members = [
            name
            for name in archive.namelist()
            if name.startswith("v020/group_analysis/group_analysis/")
        ]
        archive.extractall(tmpdir.name, members)

    package_parent = Path(tmpdir.name) / "v020" / "group_analysis"
    sys.path.insert(0, str(package_parent))
    from group_analysis import Group, System  # type: ignore

    # Keep the temporary extraction alive for the duration of this process.
    load_professor_package._tmpdir = tmpdir  # type: ignore[attr-defined]
    return Group, System


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_identified_communities(stage_dir: Path, approach: str) -> list[dict]:
    rows = []
    for row in read_csv(stage_dir / approach / "identified_communities.csv"):
        group = row["identity_group"]
        if not group.startswith("c"):
            continue
        rows.append(
            {
                "approach": approach,
                "snapshot_index": int(row["snapshot_index"]),
                "snapshot_label": row["snapshot_label"],
                "observation_id": row["observation_id"],
                "identity_group": group,
                "size": int(row["size"]),
                "nodes": set(json.loads(row["nodes_json"])),
            }
        )
    return rows


def load_final_communities(stage_dir: Path, approach: str) -> dict[str, dict]:
    rows = {}
    for row in read_csv(stage_dir / approach / "final_communities.csv"):
        rows[row["identity_group"]] = row
    return rows


def membership_rows(communities: list[dict]) -> list[dict]:
    rows = []
    for community in sorted(
        communities,
        key=lambda item: (item["snapshot_index"], item["identity_group"]),
    ):
        for member in sorted(community["nodes"]):
            rows.append(
                {
                    "approach": community["approach"],
                    "user_id": member,
                    "identity_group": community["identity_group"],
                    "snapshot_index": community["snapshot_index"],
                    "snapshot_label": community["snapshot_label"],
                    "observation_id": community["observation_id"],
                }
            )
    return rows


def group_timestamp_rows(communities: list[dict]) -> list[dict]:
    return [
        {
            "approach": item["approach"],
            "identity_group": item["identity_group"],
            "snapshot_index": item["snapshot_index"],
            "snapshot_label": item["snapshot_label"],
            "observation_id": item["observation_id"],
            "member_count": item["size"],
        }
        for item in sorted(
            communities,
            key=lambda row: (row["identity_group"], row["snapshot_index"]),
        )
    ]


def build_system_data(communities: list[dict]) -> list[tuple[int, str, int]]:
    data = []
    for row in communities:
        for member in row["nodes"]:
            data.append((member, row["identity_group"], row["snapshot_index"]))
    return data


def finite(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def stage_to_row(approach: str, method: str, group: str, index: int, stage) -> dict:
    info = stage.to_dict()
    return {
        "approach": approach,
        "method": method,
        "identity_group": group,
        "stage_index": index,
        "t_start": stage.t_start,
        "t_end": stage.t_end,
        "length": stage.length,
        "stage_type": stage.stage_type,
        "start_size": len(stage.timeline[stage.t_start]),
        "end_size": len(stage.timeline[stage.t_end]),
        "global_P": info.get("global_P", ""),
        "global_C": info.get("global_C", ""),
        "global_L": info.get("global_L", ""),
        "global_R": info.get("global_R", ""),
        "global_N": info.get("global_N", ""),
        "global_growth": finite(info.get("global_growth", "")),
        "global_churn": finite(info.get("global_churn", "")),
        "global_revitalization": finite(info.get("global_revitalization", "")),
        "global_prosp_stability": finite(info.get("global_prosp_stability", "")),
        "global_retro_stability": finite(info.get("global_retro_stability", "")),
        "solidity": finite(info.get("solidity", "")),
        "density": finite(info.get("density", "")),
        "segmentation_error": finite(info.get("segmentation_error", "")),
    }


def classic_stage_rows(approach: str, system, max_error: float) -> list[dict]:
    rows = []
    for group_name, profile in sorted(system.group_profiles.items()):
        if len(profile.presence_dates) == 1:
            continue
        if len(profile.presence_dates) == 2:
            start, end = profile.presence_dates
            rows.append(
                stage_to_row(
                    approach,
                    "classic_size_bottom_up",
                    group_name,
                    1,
                    profile.make_stage(start, end),
                )
            )
            continue

        for index, stage in enumerate(profile.identify_stages(max_error=max_error), start=1):
            rows.append(
                stage_to_row(
                    approach,
                    "classic_size_bottom_up",
                    group_name,
                    index,
                    stage,
                )
            )
    return rows


def parse_major_event_boundaries(final_row: dict) -> tuple[list[int], int, int]:
    split_merge_events = []
    boundaries = set()
    for match in EVENT_PATTERN.finditer(final_row.get("events", "")):
        event_type = match.group("event_type")
        if event_type not in {"split", "merge"}:
            continue
        split_merge_events.append(match.group("event_id"))
        boundaries.add(int(match.group("to")))
    return sorted(boundaries), len(split_merge_events), len(set(boundaries))


def event_segments_for_group(profile, final_row: dict) -> tuple[list[tuple[int, int]], int, int]:
    boundaries, event_count, unique_transition_count = parse_major_event_boundaries(final_row)
    dates = profile.presence_dates
    start, end = min(dates), max(dates)
    usable_boundaries = [boundary for boundary in boundaries if start < boundary <= end]

    segments = []
    segment_start = start
    for boundary in usable_boundaries:
        segment_end = boundary - 1
        if segment_start <= segment_end:
            segments.append((segment_start, segment_end))
        segment_start = boundary
    if segment_start <= end:
        segments.append((segment_start, end))

    return segments, event_count, unique_transition_count


def event_stage_rows(approach: str, system, final_rows: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    rows = []
    summary = []
    for group_name, profile in sorted(system.group_profiles.items()):
        segments, event_count, unique_transition_count = event_segments_for_group(
            profile,
            final_rows[group_name],
        )
        summary.append(
            {
                "approach": approach,
                "identity_group": group_name,
                "birth_snapshot": min(profile.presence_dates),
                "last_snapshot": max(profile.presence_dates),
                "lifespan_snapshots": len(profile.presence_dates),
                "split_merge_event_rows": event_count,
                "split_merge_transition_breakpoints": unique_transition_count,
                "event_based_stage_count": sum(1 for start, end in segments if start < end),
                "point_observation_count": sum(1 for start, end in segments if start == end),
                "segment_bounds": ";".join(f"{start}-{end}" for start, end in segments),
            }
        )
        stage_index = 1
        for start, end in segments:
            if start == end:
                continue
            rows.append(
                stage_to_row(
                    approach,
                    "event_split_merge_boundaries",
                    group_name,
                    stage_index,
                    profile.make_stage(start, end),
                )
            )
            stage_index += 1
    return rows, summary


def compare_stage_rows(classic: list[dict], event_based: list[dict]) -> list[dict]:
    classic_by_group = defaultdict(list)
    event_by_group = defaultdict(list)
    for row in classic:
        classic_by_group[row["identity_group"]].append(row)
    for row in event_based:
        event_by_group[row["identity_group"]].append(row)

    rows = []
    for group in sorted(event_by_group):
        for event_stage in event_by_group[group]:
            event_start = int(event_stage["t_start"])
            event_end = int(event_stage["t_end"])
            for classic_stage in classic_by_group[group]:
                classic_start = int(classic_stage["t_start"])
                classic_end = int(classic_stage["t_end"])
                overlap_start = max(event_start, classic_start)
                overlap_end = min(event_end, classic_end)
                if overlap_start > overlap_end:
                    continue
                rows.append(
                    {
                        "approach": event_stage["approach"],
                        "identity_group": group,
                        "event_stage_index": event_stage["stage_index"],
                        "event_t_start": event_start,
                        "event_t_end": event_end,
                        "event_stage_type": event_stage["stage_type"],
                        "classic_stage_index": classic_stage["stage_index"],
                        "classic_t_start": classic_start,
                        "classic_t_end": classic_end,
                        "classic_stage_type": classic_stage["stage_type"],
                        "overlap_snapshot_count": overlap_end - overlap_start + 1,
                        "same_stage_type": event_stage["stage_type"]
                        == classic_stage["stage_type"],
                    }
                )
    return rows


def stage_summary_rows(rows: list[dict]) -> list[dict]:
    counts = Counter(
        (row["approach"], row["method"], row["stage_type"]) for row in rows
    )
    return [
        {
            "approach": approach,
            "method": method,
            "stage_type": stage_type,
            "stage_count": count,
        }
        for (approach, method, stage_type), count in sorted(counts.items())
    ]


def run_approach(
    project_root: Path,
    input_dir: Path,
    output_dir: Path,
    approach: str,
    max_error: float,
) -> tuple[list[dict], list[dict]]:
    _, System = load_professor_package(project_root)
    communities = load_identified_communities(input_dir, approach)
    final_rows = load_final_communities(input_dir, approach)

    system = System(build_system_data(communities), perform_checks=True)
    system.init_group_analysis()

    membership = membership_rows(communities)
    group_sizes = group_timestamp_rows(communities)
    classic = classic_stage_rows(approach, system, max_error)
    event_based, event_summary = event_stage_rows(approach, system, final_rows)
    comparison = compare_stage_rows(classic, event_based)

    approach_dir = output_dir / approach
    write_csv(
        approach_dir / "labeled_group_memberships_u_g_t.csv",
        membership,
        [
            "approach",
            "user_id",
            "identity_group",
            "snapshot_index",
            "snapshot_label",
            "observation_id",
        ],
    )
    write_csv(
        approach_dir / "labeled_group_sizes_by_timestamp.csv",
        group_sizes,
        [
            "approach",
            "identity_group",
            "snapshot_index",
            "snapshot_label",
            "observation_id",
            "member_count",
        ],
    )

    stage_fields = [
        "approach",
        "method",
        "identity_group",
        "stage_index",
        "t_start",
        "t_end",
        "length",
        "stage_type",
        "start_size",
        "end_size",
        "global_P",
        "global_C",
        "global_L",
        "global_R",
        "global_N",
        "global_growth",
        "global_churn",
        "global_revitalization",
        "global_prosp_stability",
        "global_retro_stability",
        "solidity",
        "density",
        "segmentation_error",
    ]
    write_csv(approach_dir / "classic_stage_segments.csv", classic, stage_fields)
    write_csv(approach_dir / "event_based_stage_segments.csv", event_based, stage_fields)
    write_csv(
        approach_dir / "event_based_segmentation_summary.csv",
        event_summary,
        [
            "approach",
            "identity_group",
            "birth_snapshot",
            "last_snapshot",
            "lifespan_snapshots",
            "split_merge_event_rows",
            "split_merge_transition_breakpoints",
            "event_based_stage_count",
            "point_observation_count",
            "segment_bounds",
        ],
    )
    write_csv(
        approach_dir / "classic_vs_event_stage_overlap.csv",
        comparison,
        [
            "approach",
            "identity_group",
            "event_stage_index",
            "event_t_start",
            "event_t_end",
            "event_stage_type",
            "classic_stage_index",
            "classic_t_start",
            "classic_t_end",
            "classic_stage_type",
            "overlap_snapshot_count",
            "same_stage_type",
        ],
    )
    return classic, event_based


def combine_outputs(output_dir: Path, approaches: list[str]) -> None:
    combined_stages = []
    combined_summary = []
    for approach in approaches:
        approach_dir = output_dir / approach
        for filename in ["classic_stage_segments.csv", "event_based_stage_segments.csv"]:
            path = approach_dir / filename
            if path.exists():
                combined_stages.extend(read_csv(path))
        summary_path = approach_dir / "event_based_segmentation_summary.csv"
        if summary_path.exists():
            combined_summary.extend(read_csv(summary_path))

    if combined_stages:
        write_csv(
            output_dir / "stage_type_summary.csv",
            stage_summary_rows(combined_stages),
            ["approach", "method", "stage_type", "stage_count"],
        )
    if combined_summary:
        write_csv(
            output_dir / "event_based_segmentation_summary_all_approaches.csv",
            combined_summary,
            [
                "approach",
                "identity_group",
                "birth_snapshot",
                "last_snapshot",
                "lifespan_snapshots",
                "split_merge_event_rows",
                "split_merge_transition_breakpoints",
                "event_based_stage_count",
                "point_observation_count",
                "segment_bounds",
            ],
        )


def parse_args() -> argparse.Namespace:
    project_root = find_project_root()
    default_input = (
        project_root / "code" / "graph-matching" / "outputs" / "stage_identification"
    )
    default_output = (
        project_root / "code" / "graph-matching" / "outputs" / "stage_analysis"
    )
    parser = argparse.ArgumentParser(
        description="Run classic and event-based stage analysis on final labeled groups."
    )
    parser.add_argument("--input", type=Path, default=default_input)
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument(
        "--approach",
        choices=[*APPROACHES, "all"],
        default="overlap",
        help="Use overlap as the baseline; pass all to include comparison approaches.",
    )
    parser.add_argument(
        "--max-error",
        type=float,
        default=100.0,
        help="Maximum bottom-up segmentation merge error used by Group.identify_stages.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = find_project_root()
    approaches = APPROACHES if args.approach == "all" else [args.approach]
    for approach in approaches:
        run_approach(project_root, args.input, args.output, approach, args.max_error)
    combine_outputs(args.output, approaches)


if __name__ == "__main__":
    main()
