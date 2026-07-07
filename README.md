# Unlabeled Dynamic Groups in Social Networks

This project analyzes temporal email communication data from the SNAP Email-EU-core-temporal dataset. It creates graph snapshots, detects communities with Louvain, and matches communities over time.

## Project Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run Graph Matching

```bash
python graph-matching/graph_matching.py --approach all --output graph-matching/outputs/graph_matching
```

The default community matching threshold is Jaccard `0.5`.

## Run Identity And Event Analysis

```bash
python graph-matching/identity_events.py --approach all
python graph-matching/stage_events.py --approach all
```

Identity analysis now separates unlabeled group observations from final labeled
communities:

- `observation_id` uses `PREFIX-CXXYY`, where `XX` is the snapshot index and
  `YY` is the 1-based community number inside that snapshot, e.g. `OVL-C0205`.
- `identity_groups.csv` assembles inherited observations into chains such as
  `OVL-C0001=OVL-C0103=OVL-C0205`.
- `final_communities.csv` contains only groups alive in the last snapshot,
  relabels them as `c01`, `c02`, ..., keeps their observation chain, and lists
  each lifecycle event with the snapshot transition where it occurred. The
  `final_size` column is the number of nodes in the final community;
  `observation_count` is the number of snapshot observations in the lifespan
  chain.
- `final_communities_all_approaches.csv` combines the final-community rows for
  cumulative, interval, and overlap into one table with an `approach` column.
- `final_labeled_communities.csv` is the main final output for downstream
  work: one row per community found in the last snapshot, with its final label,
  final observation ID, size, and member list in `nodes_json`.
- `major_events_by_community.csv` lists split and merge involvement per group.
- `community_overlap_history.csv` records inter-snapshot overlap percentages
  and Jaccard scores for every non-empty overlap.

Prospective and retrospective stability use a default threshold of `0.4`.
Mutual nomination is applied only to simultaneous split-and-merge transitions;
ordinary continuations, splits, and merges inherit through the strongest
eligible prospective or retrospective stability candidate.

## Metric Visualizations In Notebook

For large graph snapshots, node-link diagrams are difficult to interpret. The recommended visualization is therefore metric evolution over time.

Open this notebook:

```text
graph-matching/metric_visualization_notebook.ipynb
```

It displays the metric tables and inline figures directly in the notebook. It does not write metric CSVs or dashboard HTML files.

The notebook covers:

- network size, density, transitivity, clustering, connected components, degree, weighted degree, and modularity
- community count, mean/median/max size, largest community share, effective community count, and internal density

## Visualize Final Community Transitions

```bash
python graph-matching/visualize_final_transitions.py --groups-per-approach 3
python graph-matching/visualize_transition_ego_graphs.py --groups-per-approach 3
```

These write:

```text
graph-matching/outputs/visualizations/final_community_transition_events.html
graph-matching/outputs/visualizations/branching_transition_graphs.html
```

The figure shows representative final labeled groups for cumulative, interval,
and overlap. Each line follows the group's observation IDs over snapshots, and
diamond markers show birth, continuation, split, and merge events at their
snapshot transitions.

`branching_transition_graphs.html` shows the split/merge structure around each
selected final group: dark nodes are the selected final group's own observation
chain, gray nodes are related communities pulled into the same transition
events, and colored edges show continuation, split, and merge relationships.

## Run Stage Identification Analysis

```bash
python graph-matching/stage_identification_analysis.py --approach overlap
python graph-matching/stage_identification_analysis.py --approach all
python graph-matching/visualize_stage_identification.py
```

This analysis uses `v020.zip`, the professor's `group_analysis` package, as a
runtime dependency. The script builds the required `(u,g,t)` structure from the
final labeled communities, where `u` is a member, `g` is a final label such as
`c01`, and `t` is the snapshot index.

Main outputs are written to `graph-matching/outputs/stage_analysis/`:

- `labeled_group_memberships_u_g_t.csv`: one row per member-group-snapshot
  membership.
- `labeled_group_sizes_by_timestamp.csv`: the compact `(g,t)` count table.
- `classic_stage_segments.csv`: size-based stages from
  `Group.identify_stages()` and `Stage.classify()`.
- `event_based_stage_segments.csv`: split/merge-boundary stages classified
  with the same stage classifier.
- `classic_vs_event_stage_overlap.csv`: interval overlaps between both
  segmentation approaches.
- `figures/paper_style/overlap_classic_paper_style_grid.png` and
  `figures/paper_style/overlap_event_based_paper_style_grid.png`: paper-style
  overview grids for the overlap baseline, with week-span x-axis labels.
- `figures/paper_style/overlap_classic_paper_style_stages.pdf` and
  `figures/paper_style/overlap_event_based_paper_style_stages.pdf`: one
  paper-style lifespan plot per final labeled group.
