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
