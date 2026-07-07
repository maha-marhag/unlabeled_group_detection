#!/usr/bin/env python3
"""Paper-style visualizations for overlap stage identification.

The figure style follows the stage-lifespan plot in the provided paper and the
``Group.plot_lifespan`` method in ``v020.zip``:

- blue line for observed group size;
- red dashed lines for identified stage segments;
- gray dotted vertical boundaries;
- vertical stage labels near the x-axis.
"""

from __future__ import annotations

import argparse
import csv
import os
import tempfile
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "idp_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from graph_matching import find_project_root
from stage_identification_analysis import (
    build_system_data,
    load_identified_communities,
    load_professor_package,
)


METHOD_FILES = {
    "classic": "classic_stage_segments.csv",
    "event_based": "event_based_stage_segments.csv",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_stage_bounds(stage_dir: Path, method: str) -> dict[str, list[tuple[int, int, str]]]:
    rows = read_csv(stage_dir / METHOD_FILES[method])
    by_group: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    for row in rows:
        start = int(row["t_start"])
        end = int(row["t_end"])
        if start == end:
            continue
        by_group[row["identity_group"]].append(
            (start, end, row["stage_type"])
        )
    for group in by_group:
        by_group[group].sort(key=lambda item: (item[0], item[1], item[2]))
    return by_group


def stage_objects(profile, bounds: list[tuple[int, int, str]]):
    """Create v020 Stage objects from saved segment bounds."""
    return [profile.make_stage(start, end) for start, end, _ in bounds if start < end]


def week_label(snapshot_label: str) -> str:
    """Convert days_400_450 to a readable week-span label."""
    _, start_day, end_day = snapshot_label.split("_")
    start_week = int(start_day) / 7
    end_week = int(end_day) / 7
    return f"w{start_week:.1f}-{end_week:.1f}"


def apply_week_axis(ax, profile, snapshot_labels: dict[int, str]) -> None:
    ticks = profile.presence_dates
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        [week_label(snapshot_labels[t]) for t in ticks],
        rotation=45,
        ha="right",
        fontsize=7,
    )
    ax.set_xlabel("Week span")


def draw_with_v020_plot_lifespan(
    ax,
    profile,
    stages: list,
    title: str,
    snapshot_labels: dict[int, str],
) -> None:
    """Draw one group through v020's Group.plot_lifespan implementation."""
    profile.plot_lifespan(ax, stages=stages)
    ax.set_title(title, fontsize=10)
    apply_week_axis(ax, profile, snapshot_labels)


def write_method_figures(
    output_dir: Path,
    method: str,
    group_profiles: dict,
    bounds_by_group: dict[str, list[tuple[int, int, str]]],
    snapshot_labels: dict[int, str],
) -> None:
    method_dir = output_dir / method
    method_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = output_dir / f"overlap_{method}_paper_style_stages.pdf"
    with PdfPages(pdf_path) as pdf:
        for group_name in sorted(group_profiles):
            stages = stage_objects(group_profiles[group_name], bounds_by_group[group_name])
            if not stages:
                continue
            fig, ax = plt.subplots(figsize=(8.5, 4.2))
            draw_with_v020_plot_lifespan(
                ax,
                group_profiles[group_name],
                stages,
                f"{group_name} - {method.replace('_', ' ')} stages",
                snapshot_labels,
            )
            fig.tight_layout()
            fig.savefig(method_dir / f"{group_name}_{method}_paper_style.png", dpi=180)
            pdf.savefig(fig)
            plt.close(fig)

    groups = [
        group_name
        for group_name in sorted(group_profiles)
        if stage_objects(group_profiles[group_name], bounds_by_group[group_name])
    ]
    columns = 3
    rows = max(1, (len(groups) + columns - 1) // columns)
    fig, axes = plt.subplots(rows, columns, figsize=(14, max(4, rows * 2.8)), sharex=False)
    if not isinstance(axes, list):
        axes = getattr(axes, "flatten", lambda: [axes])()
    axes = axes.flatten()
    for ax, group_name in zip(axes, groups):
        stages = stage_objects(group_profiles[group_name], bounds_by_group[group_name])
        draw_with_v020_plot_lifespan(
            ax,
            group_profiles[group_name],
            stages,
            group_name,
            snapshot_labels,
        )
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(labelsize=7)
        for text in ax.texts:
            text.set_fontsize(6.5)
    for ax in axes[len(groups) :]:
        ax.axis("off")
    fig.suptitle(f"Overlap {method.replace('_', ' ')} stage identification", fontsize=14)
    fig.supxlabel("Week span")
    fig.supylabel("Group's Size")
    fig.tight_layout(rect=(0.02, 0.02, 1, 0.97))
    fig.savefig(output_dir / f"overlap_{method}_paper_style_grid.png", dpi=180)
    plt.close(fig)


def run(input_dir: Path, output_dir: Path) -> None:
    project_root = find_project_root()
    _, System = load_professor_package(project_root)
    stage_identification_dir = (
        project_root / "code" / "graph-matching" / "outputs" / "stage_identification"
    )
    communities = load_identified_communities(stage_identification_dir, "overlap")
    snapshot_labels = {
        row["snapshot_index"]: row["snapshot_label"]
        for row in communities
    }

    system = System(build_system_data(communities), perform_checks=True)
    system.init_group_analysis()

    output_dir.mkdir(parents=True, exist_ok=True)
    for method in METHOD_FILES:
        bounds_by_group = load_stage_bounds(input_dir / "overlap", method)
        write_method_figures(
            output_dir,
            method,
            system.group_profiles,
            bounds_by_group,
            snapshot_labels,
        )


def parse_args() -> argparse.Namespace:
    project_root = find_project_root()
    parser = argparse.ArgumentParser(
        description="Draw paper-style classic and event-based overlap stage plots."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=project_root / "code" / "graph-matching" / "outputs" / "stage_analysis",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root
        / "code"
        / "graph-matching"
        / "outputs"
        / "stage_analysis"
        / "figures"
        / "paper_style",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(args.input, args.output)


if __name__ == "__main__":
    main()
