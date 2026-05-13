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
- lifecycle event counts: birth, death, continuation, split, merge, complex

## Optional Interactive Network HTML

A node-link visualizer still exists for spot checks. It follows one persistent community over time for each approach and merges the cumulative, interval, and overlap views into one tabbed HTML file. By default, it follows the largest community in snapshot 0 for each approach:

```bash
python graph-matching/visualize_graph_matching.py --approach all --max-nodes 220
```

The combined file is saved here:

```text
graph-matching/outputs/visualizations/focused_community_evolution.html
```

To follow a specific persistent community ID:

```bash
python graph-matching/visualize_graph_matching.py --approach interval --focus-community INTERVAL-0001
```

In the interactive graph, blue circles are stable members, green diamonds are new members, and red x markers are departed members from the previously matched version of the same community.
