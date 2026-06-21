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
