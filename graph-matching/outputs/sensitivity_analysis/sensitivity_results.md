# Sensitivity analysis: Jaccard threshold and number of snapshots

Notes on the sensitivity analysis of dynamic-group identification.
All results use the **absolute Jaccard** matching criterion (a community in
snapshot t inherits the identity of a community in snapshot t-1 when their
Jaccard similarity is at least the threshold).

- Data: `number_of_groups.csv` (written by `scripts/config_sensitivity.py`).
- Figures: `scripts/sensitivity_plots.py` -> `figures/`
- Grid: approaches cumulative / interval / overlap, snapshot counts 10, 20, 30,
  40, 50, Jaccard thresholds 0.10 to 0.90 in steps of 0.05.

## Number of groups vs Jaccard threshold, one line per snapshot count

Figure: `figures/groups_vs_jaccard_by_snapshots.png`

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

## The dynamic groups at the intersection thresholds

Figure: `figures/lifespan_vs_size_at_theta_star.png`, table: `groups_at_theta_star.csv`

For every snapshot count whose line reaches the dashed value of the previous section, the
identity matching is re-run on the cached Louvain communities at exactly the
interpolated threshold θ*. Snapshot counts whose line never reaches the dashed
value are left out (interval S = 10, overlap S = 50). Each dynamic group is
drawn by lifespan (days between the end of its first and last snapshot window)
and maximum size (log scale).

| approach   | S  | θ*    | groups | median lifespan (days) | median max size | single-snapshot groups | groups ≥ 100 days |
|------------|----|-------|--------|------------------------|-----------------|------------------------|-------------------|
| cumulative | 10 | 0.867 | 66     | 0.0                    | 58.0            | 46                     | 16                |
| cumulative | 20 | 0.753 | 71     | 0.0                    | 51.0            | 39                     | 16                |
| cumulative | 30 | 0.564 | 72     | 17.5                   | 46.0            | 29                     | 17                |
| cumulative | 40 | 0.523 | 70     | 13.2                   | 33.5            | 30                     | 15                |
| cumulative | 50 | 0.433 | 70     | 10.5                   | 27.5            | 28                     | 15                |
| interval   | 20 | 0.517 | 205    | 0.0                    | 46.0            | 163                    | 7                 |
| interval   | 30 | 0.321 | 199    | 0.0                    | 40.0            | 134                    | 14                |
| interval   | 40 | 0.221 | 196    | 0.0                    | 29.5            | 108                    | 13                |
| interval   | 50 | 0.106 | 199    | 0.0                    | 26.0            | 107                    | 21                |
| overlap    | 10 | 0.793 | 110    | 0.0                    | 54.5            | 93                     | 2                 |
| overlap    | 20 | 0.463 | 112    | 25.0                   | 54.0            | 54                     | 13                |
| overlap    | 30 | 0.316 | 109    | 17.0                   | 33.0            | 40                     | ~17               |
| overlap    | 40 | 0.228 | 109    | 12.8                   | 32.0            | 43                     | 18                |

### Observations

- At θ* the number of groups lands within ±6 of the target for all configurations,
  so the interpolated thresholds are reliable.
- Cumulative: the number of long-lived groups (≥ 100 days) is almost constant
  (15 to 17) for all five snapshot counts. The groups spanning nearly the whole
  period (≥ 400 days) grow from 1 (S = 10) to 9 (S = 50): with few snapshots and a
  high θ*, long chains are broken more easily.
- The median maximum size decreases with S in every approach (cumulative 58 → 27.5,
  interval 46 → 26, overlap 54.5 → 32): with more snapshots each window covers
  less activity (interval, overlap) or more windows end early in the period
  (cumulative), so Louvain finds smaller communities, and small short-lived groups make up a
  larger share of the fixed group count.
- Interval is dominated by single-snapshot groups (more than half in every
  configuration, 82 % at S = 20), so a matching group count hides a large number of
  groups that are never continued.
- Overlap at S = 10 behaves differently from S = 20 to 40: 85 % of its groups live
  in one snapshot only and only 2 reach 100 days, whereas S = 20 to 40 give 13 to
  18 long-lived groups.
- Visually, the long-lived tail (lifespan > 100 days, size 30 to 200) is populated by
  every snapshot count in cumulative, and by S ≥ 20 in interval and overlap. The
  overall shapes are similar, which the next section checks at member level.
