#!/usr/bin/env python3
"""Match the group sets of the 20- and 50-snapshot runs.

Both runs are matched with the current rule (stability 0.4). Two comparisons
are made per approach:

1. Final labeled groups (alive in the last snapshot). Both runs end at day
   526, so their final member sets are matched one-to-one, greedily by Jaccard.
2. All dynamic groups (alive and dead). Each group is described by the union of
   its members over its lifetime and by its time span in days. A group is
   matched when a group of the other run overlaps it in time and has a member
   Jaccard >= MATCH_JACCARD.

A group is called *stable* when it lives at least STABLE_DAYS days and reaches
at least STABLE_SIZE members; otherwise it is *unstable*. The question answered
is whether the groups that have no counterpart in the other run are the
unstable ones.

Outputs (``outputs/sensitivity_analysis``):

- ``group_matching_20_vs_50.csv``: one row per group of both runs and every
  approach, with its counterpart and stability class.
- ``figures/group_matching_20_vs_50_{approach}.png``: final-group matching (left) and
  lifespan/size scatter of matched vs unmatched groups (right).
"""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "idp_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from graph_matching import SECONDS_PER_DAY, find_project_root, jaccard
from identity_events import assign_ids, build_identity_groups, load_snapshots

APPROACHES = ["cumulative", "interval", "overlap"]
RUNS = (20, 50)
STABILITY_THRESHOLD = 0.4
MATCH_JACCARD = 0.5
STABLE_DAYS = 100
STABLE_SIZE = 10
RUN_COLORS = {20: "#2a78d6", 50: "#eb6834"}


def load_groups(run_dir: Path, approach: str) -> list[dict]:
    _, snapshots = load_snapshots(run_dir / "graph_matching" / approach / "communities.csv")
    ids, transitions = assign_ids(snapshots, approach, stability_threshold=STABILITY_THRESHOLD)
    groups, _ = build_identity_groups(snapshots, ids, transitions)
    by_observation = {ids[(c.snapshot_index, c.local_id)]: c for s in snapshots for c in s}
    rows = []
    for group in groups.values():
        members = [by_observation[o] for o in group["observation_ids"].split("=")]
        rows.append(
            {
                "group": group["identity_group"],
                "status": group["status"],
                "snapshots": len(snapshots),
                "lifespan_snapshots": group["lifespan_snapshots"],
                "start_day": round(min(c.window_start_ts for c in members) / SECONDS_PER_DAY, 1),
                "end_day": round(max(c.window_end_ts for c in members) / SECONDS_PER_DAY, 1),
                "max_size": max(len(c.nodes) for c in members),
                "members": frozenset().union(*(c.nodes for c in members)),
                "final_members": members[-1].nodes if group["status"] == "alive" else None,
            }
        )
    for row in rows:
        row["lifespan_days"] = round(row["end_day"] - row["start_day"], 1)
        row["stable"] = row["lifespan_days"] >= STABLE_DAYS and row["max_size"] >= STABLE_SIZE
    return rows


def match_final_groups(left: list[dict], right: list[dict]) -> dict[str, tuple[str, float]]:
    """Greedy one-to-one matching of final member sets by Jaccard."""
    pairs = sorted(
        (
            (jaccard(a["final_members"], b["final_members"]), a["group"], b["group"])
            for a in left if a["status"] == "alive"
            for b in right if b["status"] == "alive"
        ),
        reverse=True,
    )
    matched: dict[str, tuple[str, float]] = {}
    used = set()
    for score, a, b in pairs:
        if score <= 0 or a in matched or b in used:
            continue
        matched[a] = (b, score)
        used.add(b)
    return matched


def best_counterpart(group: dict, others: list[dict]) -> tuple[str, float]:
    best = ("", 0.0)
    for other in others:
        if other["end_day"] <= group["start_day"] or other["start_day"] >= group["end_day"]:
            continue
        score = jaccard(group["members"], other["members"])
        if score > best[1]:
            best = (other["group"], score)
    return best


def compare(approach: str, runs_dir: Path) -> list[dict]:
    groups = {n: load_groups(runs_dir / approach / f"n{n}", approach) for n in RUNS}
    final_matches = match_final_groups(groups[20], groups[50])
    reverse_final = {b: (a, s) for a, (b, s) in final_matches.items()}
    rows = []
    for run in RUNS:
        other = groups[50 if run == 20 else 20]
        finals = final_matches if run == 20 else reverse_final
        for group in groups[run]:
            counterpart, score = best_counterpart(group, other)
            final_counterpart, final_score = finals.get(group["group"], ("", 0.0))
            rows.append(
                {
                    "approach": approach,
                    "run_snapshots": run,
                    "group": group["group"],
                    "status": group["status"],
                    "lifespan_snapshots": group["lifespan_snapshots"],
                    "start_day": group["start_day"],
                    "end_day": group["end_day"],
                    "lifespan_days": group["lifespan_days"],
                    "max_size": group["max_size"],
                    "stable": group["stable"],
                    "counterpart": counterpart,
                    "counterpart_jaccard": round(score, 3),
                    "matched": score >= MATCH_JACCARD,
                    "final_counterpart": final_counterpart,
                    "final_counterpart_jaccard": round(final_score, 3) if final_counterpart else "",
                }
            )
    return rows


def plot(approach: str, frame: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), gridspec_kw={"width_ratios": [1.2, 1, 1]})

    # Left: final labeled groups of both runs, lines for matches.
    ax = axes[0]
    finals = {n: frame[(frame.run_snapshots == n) & (frame.status == "alive")]
              .sort_values("max_size", ascending=False).reset_index(drop=True) for n in RUNS}
    positions = {}
    for x, n in zip((0, 1), RUNS):
        for y, row in finals[n].iterrows():
            positions[(n, row.group)] = y
            color = RUN_COLORS[n]
            face = color if row.stable else "white"
            ax.plot(x, y, marker="o", markersize=9, markerfacecolor=face, markeredgecolor=color, markeredgewidth=1.6)
            ax.text(x + (-0.06 if x == 0 else 0.06), y,
                    f"{row.group}  {int(row.max_size)} members, {row.lifespan_days:.0f} d",
                    ha="right" if x == 0 else "left", va="center", fontsize=7)
    for _, row in finals[20].iterrows():
        if row.final_counterpart:
            y2 = positions[(50, row.final_counterpart)]
            score = float(row.final_counterpart_jaccard)
            ax.plot([0, 1], [positions[(20, row.group)], y2], color="#52514e",
                    linewidth=0.8 + 3 * score, alpha=0.35 + 0.6 * score)
            ax.text(0.5, (positions[(20, row.group)] + y2) / 2, f"{score:.2f}", fontsize=6.5,
                    ha="center", va="center", color="#0b0b0b",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none"))
    ax.set_xlim(-1.1, 2.1)
    ax.set_xticks([0, 1], ["20 snapshots", "50 snapshots"])
    ax.set_yticks([])
    ax.invert_yaxis()
    ax.set_title("Final labeled groups (line = match, label = Jaccard of final members)", fontsize=9)
    for spine in ("left", "right", "top"):
        ax.spines[spine].set_visible(False)

    # Right: all groups, lifespan vs size, matched vs unmatched.
    for ax, n in zip(axes[1:], RUNS):
        sub = frame[frame.run_snapshots == n]
        color = RUN_COLORS[n]
        for matched, marker_face, label in ((True, color, "has counterpart"), (False, "white", "no counterpart")):
            part = sub[sub.matched == matched]
            ax.scatter(part.lifespan_days, part.max_size, s=34, facecolor=marker_face,
                       edgecolor=color, linewidth=1.2, label=f"{label} ({len(part)})", zorder=3)
        ax.axvline(STABLE_DAYS, color="#52514e", linestyle="dotted", linewidth=1)
        ax.axhline(STABLE_SIZE, color="#52514e", linestyle="dotted", linewidth=1)
        ax.set_yscale("log")
        ax.set_xlabel("lifespan (days)")
        ax.set_ylabel("max size (members)")
        stable = sub[sub.stable]
        unstable = sub[~sub.stable]
        ax.set_title(
            f"All groups, {n} snapshots: stable matched {int(stable.matched.sum())}/{len(stable)}, "
            f"unstable matched {int(unstable.matched.sum())}/{len(unstable)}",
            fontsize=9,
        )
        ax.legend(fontsize=7, loc="lower right")
        ax.grid(color="#e5e7eb")
        ax.set_axisbelow(True)
    fig.suptitle(
        f"{approach.capitalize()}: 20 vs 50 snapshots (stability 0.4). "
        f"Filled = stable (>= {STABLE_DAYS} days and >= {STABLE_SIZE} members). "
        f"Counterpart = time overlap and member Jaccard >= {MATCH_JACCARD}.",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(out, dpi=170)
    plt.close(fig)


def summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (approach, n), sub in frame.groupby(["approach", "run_snapshots"]):
        finals = sub[sub.status == "alive"]
        stable, unstable = sub[sub.stable], sub[~sub.stable]
        rows.append(
            {
                "approach": approach,
                "run_snapshots": n,
                "groups": len(sub),
                "final_groups": len(finals),
                "final_groups_matched": int((finals.final_counterpart != "").sum()),
                "stable_groups": len(stable),
                "stable_matched": int(stable.matched.sum()),
                "unstable_groups": len(unstable),
                "unstable_matched": int(unstable.matched.sum()),
                "unmatched_that_are_unstable": int((~sub.matched & ~sub.stable).sum()),
                "unmatched_total": int((~sub.matched).sum()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    root = find_project_root() / "code" / "graph-matching" / "outputs" / "sensitivity_analysis"
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=root)
    parser.add_argument("--approach", choices=[*APPROACHES, "all"], default="all")
    args = parser.parse_args()
    approaches = APPROACHES if args.approach == "all" else [args.approach]

    rows = []
    for approach in approaches:
        rows.extend(compare(approach, args.output / "runs"))
    frame = pd.DataFrame(rows)
    frame.to_csv(args.output / "group_matching_20_vs_50.csv", index=False)
    (args.output / "figures").mkdir(exist_ok=True)
    for approach in approaches:
        plot(approach, frame[frame.approach == approach], args.output / "figures" / f"group_matching_20_vs_50_{approach}.png")
    print(summary(frame).to_string(index=False))


if __name__ == "__main__":
    main()
