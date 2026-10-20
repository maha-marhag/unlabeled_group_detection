# Sensitivity analysis: Jaccard threshold and number of snapshots

Notes on the step-by-step sensitivity analysis of dynamic-group identification.
All results use the **absolute Jaccard** matching criterion (a community in
snapshot t inherits the identity of a community in snapshot t-1 when their
Jaccard similarity is at least the threshold).

- Data: `number_of_groups.csv` (written by `scripts/config_sensitivity.py`).
- Figures: `scripts/sensitivity_plots.py` -> `figures/step1_*.png`, ...
- Grid: approaches cumulative / interval / overlap, snapshot counts 10, 20, 30,
  40, 50, Jaccard thresholds 0.10 to 0.90 in steps of 0.05.

## Step 1: number of groups vs Jaccard threshold, one line per snapshot count

Figure: `figures/step1_groups_vs_jaccard_by_snapshots.png`

One subplot per approach. x axis: Jaccard threshold, y axis: number of groups,
one line per number of snapshots (10 to 50). A horizontal dashed line marks a
round number of groups chosen close to the value that intercepts the most
lines; the intersections give, per snapshot count, the Jaccard threshold that
yields that many groups.

### Observations

- For every approach and snapshot count the number of groups grows
  monotonically with the Jaccard threshold: a stricter threshold breaks more
  chains, so more distinct groups are produced.
- More snapshots always give more groups at the same threshold. The lines never
  cross: the 50-snapshot line lies above the 40-snapshot line, and so on.
- Cumulative is the least sensitive approach (25 to 286 groups over the whole
  grid); interval is the most sensitive (33 to 803 groups).
- Only the cumulative approach has a number of groups reachable by all five
  snapshot counts (any value between 59 and 83). For interval and overlap the
  10-snapshot line stays below the lowest value of the 50-snapshot line, so no
  single group count intercepts all five lines.

### Dashed line and intersections

Jaccard threshold at which each snapshot-count line reaches the dashed value
(linear interpolation between the two neighbouring grid points).

| approach   | dashed line | lines intercepted | 10 snap. | 20 snap. | 30 snap. | 40 snap. | 50 snap. |
|------------|-------------|-------------------|----------|----------|----------|----------|----------|
| cumulative | 70 groups   | 5 of 5            | 0.87     | 0.75     | 0.56     | 0.52     | 0.43     |
| interval   | 200 groups  | 4 of 5            | never (max 143) | 0.52 | 0.32 | 0.22 | 0.11 |
| overlap    | 110 groups  | 4 of 5            | 0.79     | 0.46     | 0.32     | 0.23     | never (min 128) |

- Interval at 200 groups: the 10-snapshot run peaks at 143 groups at Jaccard
  0.90, so it never reaches 200.
- Overlap at 110 groups: the 50-snapshot run already starts at 128 groups at
  Jaccard 0.10, so it never comes down to 110. Any value from 103 (minimum of
  the 40-snapshot line) to 127 (maximum of the 10-snapshot line) intercepts
  4 of 5 lines; 110 is the round value inside that window.
- Reading across a row: to keep the same number of groups when the number of
  snapshots increases, the Jaccard threshold has to be lowered substantially
  (cumulative: from 0.87 at 10 snapshots to 0.43 at 50).
