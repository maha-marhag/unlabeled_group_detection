from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from compare_approaches import (
    accepted_overlaps,
    dimension_b_row,
    lineage_coordinates,
    stage_distribution_rows,
)


def test_relation_is_accepted_by_either_directional_stability() -> None:
    rows = pd.DataFrame(
        [
            {"source_overlap_pct": .5, "target_overlap_pct": .1},
            {"source_overlap_pct": .1, "target_overlap_pct": .5},
            {"source_overlap_pct": .3, "target_overlap_pct": .3},
        ]
    )

    accepted = accepted_overlaps(rows, .4)

    assert list(accepted.index) == [0, 1]


def test_network_metrics_and_coordinates_include_intermediate_nodes() -> None:
    graph = nx.DiGraph()
    graph.add_node("a", snapshot=0, local_id=0, identity_group="dead-a", size=10)
    graph.add_node("b", snapshot=1, local_id=0, identity_group="c01", size=6)
    graph.add_node("c", snapshot=1, local_id=1, identity_group="c02", size=4)
    graph.add_edges_from([("a", "b"), ("a", "c")])

    positions, components = lineage_coordinates(graph)
    summary = dimension_b_row("overlap", graph)

    assert set(positions) == {"a", "b", "c"}
    assert positions["a"][0] == 0
    assert positions["b"][0] == positions["c"][0] == 1
    assert len(set(components.values())) == 1
    assert summary["observation_nodes"] == 3
    assert summary["split_nodes"] == 1
    assert summary["weakly_connected_components"] == 1
    assert summary["max_depth_edges"] == 1


def test_stage_duration_uses_transitions_not_inclusive_snapshot_count() -> None:
    stages = pd.DataFrame(
        [
            {"identity_group": "c01", "stage_type": "Erosion", "t_start": 0, "t_end": 2, "length": 3},
            {"identity_group": "c01", "stage_type": "Organic-Growth", "t_start": 2, "t_end": 3, "length": 2},
        ]
    )

    rows = pd.DataFrame(stage_distribution_rows("overlap", "event_based", stages))
    erosion = rows.loc[rows["stage_type"] == "Erosion"].iloc[0]
    growth = rows.loc[rows["stage_type"] == "Organic-Growth"].iloc[0]

    assert erosion["transition_duration"] == 2
    assert growth["transition_duration"] == 1
    assert erosion["transition_duration_share"] == 2 / 3
    assert growth["transition_duration_share"] == 1 / 3
