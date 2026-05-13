# Graph Matching Phase

This workspace starts from the SNAP `email-Eu-core-temporal.txt` temporal edge list and implements the first phase described in the expose: snapshot construction, Louvain community detection, and community matching across consecutive snapshots.

## Data Assumptions

- Input format: `SRC DST UNIXTS`.
- The default preprocessing keeps the first `500` days.
- One day is treated as `86400` seconds.
- Email interactions are converted into an undirected weighted graph per snapshot, where each weight is the number of messages observed between two users in that window.

## Snapshot Approaches

Implemented now:

- `cumulative`: snapshot `i` contains all edges from day `0` to day `(i + 1) * 50`.
- `interval`: snapshot `i` contains only edges from day `i * 50` to day `(i + 1) * 50`.
- `overlap`: 50-day moving windows with 50% overlap by default, so the stride is 25 days.

Documented for later only:

- `decay`: keep an edge active until it expires if it is not renewed. This may later be combined with cumulative snapshots to study whether it helps detect splits, but it is intentionally not implemented in this first pass.

## Community Detection

The script uses NetworkX Louvain communities:

```bash
cd "/Users/maha_personal/Uni/SS 26/IDP"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r code/requirements.txt
python code/graph_matching.py --approach all --output code/outputs/graph_matching
```

If dependencies are missing:

```bash
python -m pip install -r code/requirements.txt
```

For notebook work, open `code/graph_matching_notebook.ipynb` in VS Code and select the `.venv` interpreter as the kernel.

## Outputs

For each approach, files are written under `code/outputs/graph_matching/<approach>/` when using the command above:

- `snapshot_stats.csv`: snapshot sizes, edge counts, node counts, and number of communities.
- `communities.csv`: local and persistent community ids with node membership.
- `matches.csv`: pairwise matches between consecutive snapshots using Jaccard overlap.
- `events.csv`: lifecycle labels: `birth`, `death`, `continuation`, `split`, `merge`, and `complex`.

The current matching rule is deliberately simple and inspectable: communities are connected across consecutive snapshots when their Jaccard overlap is at least `0.3`. Persistent IDs are inherited from the strongest parent; in splits the largest/best child keeps the parent ID, and in merges the strongest previous community provides the ID.
