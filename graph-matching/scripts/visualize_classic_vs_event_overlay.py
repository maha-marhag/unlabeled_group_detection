#!/usr/bin/env python3
"""Overlay split/merge events on the classic size-based stage lifespan plots.

Two figure families are produced per approach (cumulative, interval, overlap):

1. ``*_classic_with_events_grid.png``: the paper-style classic segmentation
   (blue size line, red dashed stage segments, gray dotted boundaries) with the
   split/merge events of the event-based approach marked as stars on the size
   line. A faint colored vertical line at each event snapshot makes it easy to
   see whether it coincides with a gray classic boundary.
2. ``*_stage_ribbons_grid.png``: the same size line with the event stars, plus
   two horizontal ribbons under the line showing the classic and event-based
   stage segments colored by stage type. This variant exposes both boundary
   alignment and stage-type agreement in one view.

A per-group agreement table is written to
``classic_event_boundary_agreement.csv`` and the per-snapshot boundary detail
to ``classic_event_boundary_detail.csv``.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "idp_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from graph_matching import find_project_root, write_csv
from stage_identification_analysis import (
    EVENT_PATTERN,
    build_system_data,
    load_final_communities,
    load_identified_communities,
    load_professor_package,
)
from visualize_stage_identification import (
    APPROACHES,
    apply_week_axis,
    load_stage_bounds,
    stage_objects,
)

SPLIT_COLOR = "#eb6834"  # orange
MERGE_COLOR = "#4a3aa7"  # violet
STAGE_COLORS = {
    "Organic-Growth": "#008300",
    "Dynamic-Growth": "#1baf7a",
    "Steady-Stability": "#2a78d6",
    "Fluid-Stability": "#9085e9",
    "Turnover-Shrinkage": "#eda100",
    "Erosion": "#e34948",
}
STAGE_ORDER = list(STAGE_COLORS)


# --------------------------------------------------------------------------- #
# Data preparation
# --------------------------------------------------------------------------- #
def parse_events(final_row: dict) -> dict[int, set[str]]:
    """Map the landing snapshot of each split/merge event to its event types."""
    events: dict[int, set[str]] = defaultdict(set)
    for match in EVENT_PATTERN.finditer(final_row.get("events", "")):
        event_type = match.group("event_type")
        if event_type in {"split", "merge"}:
            events[int(match.group("to"))].add(event_type)
    return events


def internal_boundaries(bounds: list[tuple[int, int, str]]) -> set[int]:
    """Snapshots that close one stage and open the next."""
    starts = {start for start, _, _ in bounds}
    ends = {end for _, end, _ in bounds}
    return starts & ends


def group_agreement_rows(
    approach: str,
    group: str,
    profile,
    classic_bounds: list[tuple[int, int, str]],
    event_bounds: list[tuple[int, int, str]],
    events: dict[int, set[str]],
) -> tuple[dict, list[dict]]:
    first, last = min(profile.presence_dates), max(profile.presence_dates)
    classic_b = internal_boundaries(classic_bounds)
    event_b = internal_boundaries(event_bounds)
    shared = classic_b & event_b
    union = classic_b | event_b
    detail = []
    for snapshot in sorted(union | set(events)):
        position = "internal" if first < snapshot < last else (
            "group_start" if snapshot == first else "group_end"
        )
        detail.append(
            {
                "approach": approach,
                "identity_group": group,
                "snapshot_index": snapshot,
                "position": position,
                "classic_boundary": snapshot in classic_b,
                "event_boundary": snapshot in event_b,
                "event_types": "+".join(sorted(events.get(snapshot, set()))),
                "group_size": len(profile.timeline[snapshot])
                if snapshot in profile.timeline
                else "",
            }
        )
    summary = {
        "approach": approach,
        "identity_group": group,
        "lifespan_snapshots": len(profile.presence_dates),
        "classic_stage_count": len(classic_bounds),
        "event_stage_count": len(event_bounds),
        "classic_internal_boundary_count": len(classic_b),
        "event_internal_boundary_count": len(event_b),
        "shared_boundary_count": len(shared),
        "boundary_jaccard": f"{len(shared) / len(union):.3f}" if union else "",
        "event_recall_of_classic": f"{len(shared) / len(classic_b):.3f}" if classic_b else "",
        "classic_recall_of_event": f"{len(shared) / len(event_b):.3f}" if event_b else "",
        "split_merge_events_at_start": "+".join(sorted(events.get(first, set()))),
    }
    return summary, detail


# --------------------------------------------------------------------------- #
# Drawing helpers
# --------------------------------------------------------------------------- #
def draw_event_markers(ax, profile, events: dict[int, set[str]], ymax: float) -> None:
    first, last = min(profile.presence_dates), max(profile.presence_dates)
    for snapshot, types in sorted(events.items()):
        if snapshot not in profile.timeline:
            continue
        size = len(profile.timeline[snapshot])
        # Events landing on the first or last observation cannot split a stage.
        at_start = snapshot in (first, last)
        both = {"split", "merge"} <= types
        face = SPLIT_COLOR if "split" in types else MERGE_COLOR
        edge = MERGE_COLOR if both else face
        if not at_start:
            ax.plot([snapshot, snapshot], [0, ymax], color=face, alpha=0.25, linewidth=1.4)
        ax.plot(
            snapshot,
            size,
            marker="*",
            markersize=15 if both else 13,
            markerfacecolor="white" if at_start else face,
            markeredgecolor=edge,
            markeredgewidth=2.0 if both else 1.2,
            linestyle="none",
            zorder=5,
        )


def draw_overlay(ax, profile, classic_stages, events, title, snapshot_labels) -> None:
    profile.plot_lifespan(ax, stages=classic_stages)
    ymax = max(len(members) for members in profile.timeline.values())
    draw_event_markers(ax, profile, events, ymax)
    ax.set_title(title, fontsize=9)
    apply_week_axis(ax, profile, snapshot_labels)


def draw_ribbons(
    ax,
    profile,
    classic_bounds,
    event_bounds,
    events,
    title,
    snapshot_labels,
) -> None:
    dates = sorted(profile.presence_dates)
    sizes = [len(profile.timeline[t]) for t in dates]
    ymax = max(sizes)
    ax.plot(dates, sizes, color="#2a78d6", linewidth=1.8, zorder=3)
    ax.plot(dates, sizes, linestyle="none", marker="o", markersize=3, color="#2a78d6", zorder=3)
    draw_event_markers(ax, profile, events, ymax)

    # Two ribbons below the size line, in a reserved negative band.
    band = max(ymax * 0.14, 1.0)
    ribbons = [("classic", classic_bounds, -band), ("event", event_bounds, -2 * band)]
    for label, bounds, y0 in ribbons:
        for start, end, stage_type in bounds:
            ax.add_patch(
                plt.Rectangle(
                    (start, y0),
                    end - start,
                    band * 0.85,
                    facecolor=STAGE_COLORS.get(stage_type, "#999999"),
                    edgecolor="white",
                    linewidth=1.0,
                    zorder=2,
                )
            )
        ax.text(
            dates[0] - 0.15,
            y0 + band * 0.42,
            label,
            fontsize=6.5,
            ha="right",
            va="center",
            color="#52514e",
        )
    for snapshot in internal_boundaries(classic_bounds):
        ax.plot([snapshot, snapshot], [0, ymax], linestyle="dotted", color="gray", linewidth=1)
    ax.axhline(0, color="#c3c2b7", linewidth=0.8)
    ax.set_ylim(-2.1 * band, ymax * 1.12)
    ax.set_yticks([tick for tick in ax.get_yticks() if 0 <= tick <= ymax * 1.12])
    ax.set_title(title, fontsize=9)
    apply_week_axis(ax, profile, snapshot_labels)


def legend_handles(include_stages: bool) -> list:
    handles = [
        Line2D([], [], color="#2a78d6", label="observed group size"),
        Line2D([], [], color="r", linestyle="dashed", label="classic stage segment"),
        Line2D([], [], color="gray", linestyle="dotted", label="classic stage boundary"),
        Line2D([], [], marker="*", color=SPLIT_COLOR, linestyle="none", markersize=11, label="split event"),
        Line2D([], [], marker="*", color=MERGE_COLOR, linestyle="none", markersize=11, label="merge event"),
        Line2D(
            [], [], marker="*", markerfacecolor=SPLIT_COLOR, markeredgecolor=MERGE_COLOR,
            markeredgewidth=2, color="none", linestyle="none", markersize=12, label="split + merge",
        ),
        Line2D(
            [], [], marker="*", markerfacecolor="white", markeredgecolor=SPLIT_COLOR,
            color="none", linestyle="none", markersize=11, label="event at first/last observation (cannot split a stage)",
        ),
    ]
    if include_stages:
        handles = [handles[0], *handles[3:]] + [
            Patch(facecolor=color, label=stage) for stage, color in STAGE_COLORS.items()
        ]
    return handles


def grid_figure(groups: list[str], draw_one, suptitle: str, legend: list, out_path: Path) -> None:
    columns = 3
    rows = max(1, (len(groups) + columns - 1) // columns)
    fig, axes = plt.subplots(rows, columns, figsize=(15, max(4.2, rows * 3.1)))
    axes = axes.flatten()
    for ax, group in zip(axes, groups):
        draw_one(ax, group)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(labelsize=7)
        for text in ax.texts:
            if text.get_rotation() == 90:
                text.set_fontsize(6.5)
    for ax in axes[len(groups):]:
        ax.axis("off")
    fig.suptitle(suptitle, fontsize=14)
    fig.supxlabel("Week span", y=0.055)
    fig.supylabel("Group's Size")
    fig.legend(
        handles=legend,
        loc="lower center",
        ncol=min(len(legend), 7),
        fontsize=8,
        frameon=False,
        bbox_to_anchor=(0.5, 0.0),
    )
    fig.tight_layout(rect=(0.02, 0.075, 1, 0.97))
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def run_approach(System, approach: str, stage_dir: Path, ident_dir: Path, fig_dir: Path):
    communities = load_identified_communities(ident_dir, approach)
    final_rows = load_final_communities(ident_dir, approach)
    snapshot_labels = {row["snapshot_index"]: row["snapshot_label"] for row in communities}
    system = System(build_system_data(communities), perform_checks=True)
    system.init_group_analysis()
    profiles = system.group_profiles

    classic = load_stage_bounds(stage_dir / approach, "classic")
    event_based = load_stage_bounds(stage_dir / approach, "event_based")
    events = {g: parse_events(final_rows[g]) for g in profiles}

    groups = [g for g in sorted(profiles) if stage_objects(profiles[g], classic.get(g, []))]
    summaries, details = [], []
    for g in groups:
        summary, detail = group_agreement_rows(
            approach, g, profiles[g], classic.get(g, []), event_based.get(g, []), events[g]
        )
        summaries.append(summary)
        details.extend(detail)
    by_group = {row["identity_group"]: row for row in summaries}

    def title(g: str) -> str:
        s = by_group[g]
        return (
            f"{g}  |  classic bnd {s['classic_internal_boundary_count']}, "
            f"event bnd {s['event_internal_boundary_count']}, shared {s['shared_boundary_count']}"
        )

    def overlay_one(ax, g):
        draw_overlay(
            ax, profiles[g], stage_objects(profiles[g], classic[g]), events[g], title(g), snapshot_labels
        )

    def ribbon_one(ax, g):
        draw_ribbons(
            ax, profiles[g], classic[g], event_based.get(g, []), events[g], title(g), snapshot_labels
        )

    grid_figure(
        groups,
        overlay_one,
        f"{approach.capitalize()}: classic stages with split/merge events overlaid",
        legend_handles(include_stages=False),
        fig_dir / f"{approach}_classic_with_events_grid.png",
    )
    grid_figure(
        groups,
        ribbon_one,
        f"{approach.capitalize()}: classic (top ribbon) vs event-based (bottom ribbon) stages",
        legend_handles(include_stages=True),
        fig_dir / f"{approach}_stage_ribbons_grid.png",
    )
    return summaries, details


def approach_totals(summaries: list[dict]) -> dict:
    classic_n = sum(r["classic_internal_boundary_count"] for r in summaries)
    event_n = sum(r["event_internal_boundary_count"] for r in summaries)
    shared = sum(r["shared_boundary_count"] for r in summaries)
    union = classic_n + event_n - shared
    return {
        "approach": summaries[0]["approach"],
        "identity_group": "ALL",
        "lifespan_snapshots": "",
        "classic_stage_count": sum(r["classic_stage_count"] for r in summaries),
        "event_stage_count": sum(r["event_stage_count"] for r in summaries),
        "classic_internal_boundary_count": classic_n,
        "event_internal_boundary_count": event_n,
        "shared_boundary_count": shared,
        "boundary_jaccard": f"{shared / union:.3f}" if union else "",
        "event_recall_of_classic": f"{shared / classic_n:.3f}" if classic_n else "",
        "classic_recall_of_event": f"{shared / event_n:.3f}" if event_n else "",
        "split_merge_events_at_start": "",
    }


def run(stage_dir: Path, ident_dir: Path, fig_dir: Path, approaches: list[str]) -> None:
    project_root = find_project_root()
    _, System = load_professor_package(project_root)
    fig_dir.mkdir(parents=True, exist_ok=True)
    all_summaries, all_details = [], []
    for approach in approaches:
        summaries, details = run_approach(System, approach, stage_dir, ident_dir, fig_dir)
        all_summaries.extend(summaries)
        all_summaries.append(approach_totals(summaries))
        all_details.extend(details)
    write_csv(
        stage_dir / "classic_event_boundary_agreement.csv",
        all_summaries,
        list(all_summaries[0].keys()),
    )
    write_csv(
        stage_dir / "classic_event_boundary_detail.csv",
        all_details,
        list(all_details[0].keys()),
    )


def parse_args() -> argparse.Namespace:
    root = find_project_root() / "code" / "graph-matching" / "outputs"
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage-analysis", type=Path, default=root / "stage_analysis")
    parser.add_argument("--stage-identification", type=Path, default=root / "stage_identification")
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "stage_analysis" / "figures" / "classic_event_overlay",
    )
    parser.add_argument("--approach", choices=[*APPROACHES, "all"], default="all")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    approaches = APPROACHES if args.approach == "all" else [args.approach]
    run(args.stage_analysis, args.stage_identification, args.output, approaches)


if __name__ == "__main__":
    main()
