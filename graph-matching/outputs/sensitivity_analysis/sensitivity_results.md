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

Figure: `figures/lifespan_classes_at_theta_star.png`, table: `groups_at_theta_star.csv`

For every snapshot count whose line reaches the dashed value of the previous section, the
identity matching is re-run on the cached Louvain communities at exactly the
interpolated threshold θ*. Snapshot counts whose line never reaches the dashed
value are left out (interval S = 10, overlap S = 50). The figure shows, per
snapshot count, two bars: the groups observed in one snapshot only and the groups
living at least 100 days (lifespan = days between the end of the first and the
last snapshot window of the group).

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
| overlap    | 30 | 0.316 | 109    | 17.0                   | 33.0            | 40                     | 16                |
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

## Community comparison across snapshot counts

Methodology: see the section "Robustness of the dynamic groups to the number of
snapshots" in `paper_notes.md`.

Tables: `group_matching_summary.csv` (one row per pair), `group_matching_pairs.csv`
(every matched group pair with its mean Jaccard), and the full cross tables in
`crosstabs/{approach}_S{i}_vs_S{j}.csv`.

### Final table: Jaccard thresholds and the communities they produce

The hypothesis is formulated for the thresholds $\theta^*_S$ that give every snapshot
count the same number of dynamic groups $N^*$. For each pair of configurations
$(S_i, \theta^*_{S_i})$ and $(S_j, \theta^*_{S_j})$ the table reports how well the
resulting communities agree: the median and mean similarity of the one-to-one matched
groups ($\mathcal{J}_{ij}$), the share of matched groups whose chronicles are
identical on the common time points ($\bar{J} \ge 0.99$) and the ARI.

**cumulative** (reference level $N^* = 70$ groups): $\theta^*_{10} = 0.867$, $\theta^*_{20} = 0.753$, $\theta^*_{30} = 0.564$, $\theta^*_{40} = 0.523$, $\theta^*_{50} = 0.433$

| $(S_i, \theta^*_{S_i})$ | $(S_j, \theta^*_{S_j})$ | median $\mathcal{J}_{ij}$ | mean $\mathcal{J}_{ij}$ | identical matched groups | ARI |
|---|---|---|---|---|---|
| (10, 0.867) | (20, 0.753) | 1.00 | 0.81 | 59 % | 0.67 |
| (10, 0.867) | (30, 0.564) | 1.00 | 0.83 | 63 % | 0.68 |
| (10, 0.867) | (40, 0.523) | 1.00 | 0.82 | 58 % | 0.67 |
| (10, 0.867) | (50, 0.433) | 1.00 | 0.86 | 65 % | 0.60 |
| (20, 0.753) | (30, 0.564) | 1.00 | 0.82 | 70 % | 0.76 |
| (20, 0.753) | (40, 0.523) | 1.00 | 0.78 | 57 % | 0.88 |
| (20, 0.753) | (50, 0.433) | 1.00 | 0.83 | 65 % | 0.91 |
| (30, 0.564) | (40, 0.523) | 1.00 | 0.86 | 68 % | 0.81 |
| (30, 0.564) | (50, 0.433) | 1.00 | 0.90 | 76 % | 0.76 |
| (40, 0.523) | (50, 0.433) | 1.00 | 0.89 | 76 % | 0.90 |

**interval** (reference level $N^* = 200$ groups): $\theta^*_{20} = 0.517$, $\theta^*_{30} = 0.321$, $\theta^*_{40} = 0.221$, $\theta^*_{50} = 0.106$

| $(S_i, \theta^*_{S_i})$ | $(S_j, \theta^*_{S_j})$ | median $\mathcal{J}_{ij}$ | mean $\mathcal{J}_{ij}$ | identical matched groups | ARI |
|---|---|---|---|---|---|
| (20, 0.517) | (30, 0.321) | 0.53 | 0.52 | 1 % | 0.51 |
| (20, 0.517) | (40, 0.221) | 0.35 | 0.37 | 5 % | 0.44 |
| (20, 0.517) | (50, 0.106) | 0.33 | 0.34 | 0 % | 0.49 |
| (30, 0.321) | (40, 0.221) | 0.44 | 0.47 | 4 % | 0.57 |
| (30, 0.321) | (50, 0.106) | 0.37 | 0.35 | 2 % | 0.52 |
| (40, 0.221) | (50, 0.106) | 0.46 | 0.46 | 8 % | 0.54 |

**overlap** (reference level $N^* = 110$ groups): $\theta^*_{10} = 0.793$, $\theta^*_{20} = 0.463$, $\theta^*_{30} = 0.316$, $\theta^*_{40} = 0.228$

| $(S_i, \theta^*_{S_i})$ | $(S_j, \theta^*_{S_j})$ | median $\mathcal{J}_{ij}$ | mean $\mathcal{J}_{ij}$ | identical matched groups | ARI |
|---|---|---|---|---|---|
| (10, 0.793) | (20, 0.463) | 0.40 | 0.39 | 1 % | 0.41 |
| (10, 0.793) | (30, 0.316) | 0.30 | 0.32 | 1 % | 0.27 |
| (10, 0.793) | (40, 0.228) | 0.23 | 0.25 | 0 % | 0.28 |
| (20, 0.463) | (30, 0.316) | 0.28 | 0.32 | 1 % | 0.51 |
| (20, 0.463) | (40, 0.228) | 0.22 | 0.27 | 1 % | 0.52 |
| (30, 0.316) | (40, 0.228) | 0.33 | 0.35 | 5 % | 0.58 |

### Example of each approach

Figure: `figures/crosstab_example_S20_vs_S40.png` (S = 20 vs S = 40, the only pair
available for all three approaches with 20 common time points).

For each approach a small excerpt of the cross table, with the mean Jaccard written
in each cell (empty = 0). Rows: 5 consecutive groups of $\mathbb{D}_{S=20}$ around the
median matched rank, i.e. typical rather than best matches. Columns: their matched
groups of $\mathbb{D}_{S=40}$ (diagonal, inside the dashed box), followed by up to 3
other groups of $S = 40$ that share members with these rows (largest Jaccard sum).

- Cumulative (ranks 25–29 of 53): diagonal of 1.00 and no other partner at all, a
  1:1 correspondence even for a typical group.
- Interval (ranks 68–72 of 138): matched values about 0.35, plus small overlaps
  (0.04 to 0.06) with other groups.
- Overlap (ranks 39–43 of 81): matched values about 0.22, and the rows spread over
  several further groups (up to 0.07).

Partners per group (cells with Jaccard > 0 per row), over all pairs of snapshot
counts: cumulative 1.00 to 1.11, interval 4.1 to 5.0, overlap 4.3 to 6.9.

### How to read a cross table

Each file is a matrix: the rows are the dynamic groups $D_1, D_2, \ldots$ of
$\mathbb{D}_{S_i}$, the columns the dynamic groups $D'_1, D'_2, \ldots$ of
$\mathbb{D}_{S_j}$ (original group id in brackets), and each cell is the mean
Jaccard index of the two groups' member sets over the common time points
(0 at a time point where only one of the two exists). Rows and columns are ordered
by the linear sum assignment: $D_k$ is matched to $D'_k$, so the matched values
lie on the diagonal, sorted from best to worst; groups left without a partner come
last. Cells with Jaccard 0 are left empty. A clean 1:1 correspondence shows up as a
diagonal of values near 1 with empty cells elsewhere.

Excerpts (six matched pairs spread evenly from the best to the worst match; the
diagonal, in bold, is the matched value; empty cells have Jaccard 0):

**Cumulative, S = 10 vs S = 20** (`crosstabs/cumulative_S10_vs_S20.csv`, 66 × 46; showing matched ranks 1, 10, 19, 28, 37, 46 of 46)

| S=10 \\ S=20 | D'1 | D'10 | D'19 | D'28 | D'37 | D'46 |
|---|---|---|---|---|---|---|
| D1 | **1.00** |  |  |  |  |  |
| D10 |  | **1.00** |  |  |  |  |
| D19 |  |  | **1.00** |  |  |  |
| D28 |  |  |  | **0.83** |  |  |
| D37 |  |  |  |  | **0.60** |  |
| D46 |  |  |  |  | 0.30 |  |

**Interval, S = 20 vs S = 30** (`crosstabs/interval_S20_vs_S30.csv`, 117 × 93; showing matched ranks 1, 19, 38, 56, 75, 93 of 93)

| S=20 \\ S=30 | D'1 | D'19 | D'38 | D'56 | D'75 | D'93 |
|---|---|---|---|---|---|---|
| D1 | **1.00** |  |  |  |  |  |
| D19 |  | **0.75** |  |  |  |  |
| D38 |  |  | **0.60** |  |  |  |
| D56 |  |  |  | **0.48** |  |  |
| D75 |  |  |  |  | **0.35** |  |
| D93 |  |  |  |  |  |  |

**Overlap, S = 10 vs S = 20** (`crosstabs/overlap_S10_vs_S20.csv`, 110 × 83; showing matched ranks 1, 17, 34, 50, 67, 83 of 83)

| S=10 \\ S=20 | D'1 | D'17 | D'34 | D'50 | D'67 | D'83 |
|---|---|---|---|---|---|---|
| D1 | **1.00** |  |  |  |  |  |
| D17 |  | **0.59** |  |  |  |  |
| D34 |  |  | **0.41** |  |  |  |
| D50 |  |  |  | **0.33** |  |  |
| D67 |  |  |  |  | **0.23** |  |
| D83 |  |  |  |  |  |  |


| approach | $S_i$–$S_j$ | $\lvert T_{S_i} \rvert$ / $\lvert T_{S_j} \rvert$ | $\lvert T_{ij} \rvert$ | $\lvert \mathbb{D}_{S_i} \rvert$ / $\lvert \mathbb{D}_{S_j} \rvert$ | chronicles compared | mean chronicle length on $T_{ij}$ | size of $\mathbf{M}^{(ij)}$ | matched pairs | mean $\mathcal{J}_{ij}$ | median $\mathcal{J}_{ij}$ | ARI |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cumulative | 10–20 | 10 / 20 | 10 | 66 / 71 | 66 / 46 | 2.0 / 2.9 | 66 × 46 | 46 | 0.814 | 1.000 | 0.674 |
| cumulative | 10–30 | 10 / 30 | 10 | 66 / 72 | 66 / 43 | 2.0 / 3.1 | 66 × 43 | 43 | 0.835 | 1.000 | 0.679 |
| cumulative | 10–40 | 10 / 40 | 10 | 66 / 70 | 66 / 38 | 2.0 / 3.5 | 66 × 38 | 38 | 0.821 | 1.000 | 0.673 |
| cumulative | 10–50 | 10 / 50 | 10 | 66 / 70 | 66 / 34 | 2.0 / 3.9 | 66 × 34 | 34 | 0.858 | 1.000 | 0.602 |
| cumulative | 20–30 | 20 / 30 | 10 | 71 / 72 | 46 / 43 | 2.9 / 3.1 | 46 × 43 | 43 | 0.824 | 1.000 | 0.758 |
| cumulative | 20–40 | 20 / 40 | 20 | 71 / 70 | 71 / 53 | 3.8 / 5.0 | 71 × 53 | 53 | 0.782 | 1.000 | 0.877 |
| cumulative | 20–50 | 20 / 50 | 10 | 71 / 70 | 46 / 34 | 2.9 / 3.9 | 46 × 34 | 34 | 0.831 | 1.000 | 0.905 |
| cumulative | 30–40 | 30 / 40 | 10 | 72 / 70 | 43 / 38 | 3.1 / 3.5 | 43 × 38 | 38 | 0.857 | 1.000 | 0.807 |
| cumulative | 30–50 | 30 / 50 | 10 | 72 / 70 | 43 / 34 | 3.1 / 3.9 | 43 × 34 | 34 | 0.895 | 1.000 | 0.759 |
| cumulative | 40–50 | 40 / 50 | 10 | 70 / 70 | 38 / 34 | 3.5 / 3.9 | 38 × 34 | 34 | 0.891 | 1.000 | 0.903 |
| interval | 20–30 | 20 / 30 | 10 | 205 / 199 | 117 / 93 | 1.2 / 1.5 | 117 × 93 | 93 | 0.521 | 0.526 | 0.508 |
| interval | 20–40 | 20 / 40 | 20 | 205 / 196 | 205 / 138 | 1.5 / 2.2 | 205 × 138 | 138 | 0.373 | 0.351 | 0.444 |
| interval | 20–50 | 20 / 50 | 10 | 205 / 199 | 117 / 90 | 1.2 / 1.7 | 117 × 90 | 90 | 0.337 | 0.329 | 0.491 |
| interval | 30–40 | 30 / 40 | 10 | 199 / 196 | 93 / 89 | 1.5 / 1.6 | 93 × 89 | 89 | 0.470 | 0.444 | 0.574 |
| interval | 30–50 | 30 / 50 | 10 | 199 / 199 | 93 / 90 | 1.5 / 1.7 | 93 × 90 | 90 | 0.352 | 0.370 | 0.522 |
| interval | 40–50 | 40 / 50 | 10 | 196 / 199 | 89 / 90 | 1.6 / 1.7 | 89 × 90 | 89 | 0.459 | 0.455 | 0.544 |
| overlap | 10–20 | 10 / 20 | 10 | 110 / 112 | 110 / 83 | 1.3 / 1.7 | 110 × 83 | 83 | 0.390 | 0.395 | 0.411 |
| overlap | 10–30 | 10 / 30 | 10 | 110 / 109 | 110 / 69 | 1.3 / 2.2 | 110 × 69 | 69 | 0.322 | 0.299 | 0.269 |
| overlap | 10–40 | 10 / 40 | 10 | 110 / 109 | 110 / 65 | 1.3 / 2.3 | 110 × 65 | 65 | 0.247 | 0.227 | 0.275 |
| overlap | 20–30 | 20 / 30 | 20 | 112 / 109 | 112 / 94 | 2.6 / 3.2 | 112 × 94 | 94 | 0.324 | 0.278 | 0.509 |
| overlap | 20–40 | 20 / 40 | 20 | 112 / 109 | 112 / 81 | 2.6 / 3.6 | 112 × 81 | 81 | 0.267 | 0.220 | 0.520 |
| overlap | 30–40 | 30 / 40 | 30 | 109 / 109 | 109 / 100 | 4.2 / 4.4 | 109 × 100 | 100 | 0.353 | 0.327 | 0.578 |

- $|T_{S_i}|$, $|T_{S_j}|$: number of time points (snapshots) of each configuration.
- $|T_{ij}|$: number of common time points (for overlapping windows, paired nearest window ends).
- $|\mathbb{D}_{S_i}|$, $|\mathbb{D}_{S_j}|$: number of dynamic groups at $\theta^*$.
- chronicles compared: dynamic groups that exist at one or more common time points; the
  others exist only between common time points and are excluded.
- mean chronicle length on $T_{ij}$: average number of common time points at which a
  compared group exists.
- size of $\mathbf{M}^{(ij)}$: dimensions of the cross table; matched pairs $= \min(n_i, n_j)$.

### Observations

- Cumulative: median matched similarity 1.0 for every pair, clean 1:1 diagonal,
  ARI 0.60 to 0.91 (lowest with S = 10). 65 % of the matched pairs are identical on
  the common time points.
- Cumulative snapshots at a common time point are the same graph [0, t], and Louvain
  (seed 42) returns identical communities there (checked for S = 10 vs 50 at all 10
  time points), so the disagreement comes only from how communities are chained.
- Interval: median 0.33 to 0.53, ARI 0.44 to 0.57, 3.6 % identical pairs.
- Overlap: median 0.22 to 0.40, ARI 0.27 to 0.58, 1.8 % identical pairs; pairs with
  S = 10 agree least.
- Many groups exist only between common time points and are excluded (up to 36 of
  70 for cumulative S = 50 vs 10, up to 109 of 199 for interval).
- Hypothesis supported for cumulative; for interval and overlap not supported at the
  equal-count thresholds θ*, nor at any other threshold combination (see the joint
  search below).

## Joint search for the best-matching thresholds

Tables: `joint_threshold_search.csv` (every pair, every θ_i × θ_j, 17 × 17),
`joint_threshold_search_best.csv` (best combination per pair). Methodology: section
"Joint search for the best-matching thresholds" in `paper_notes.md`.

- Both thresholds varied over 0.10 to 0.90 (step 0.05).
- Only groups with a history are compared: groups present at ≥ 2 common time points.
- Score = sum of matched mean Jaccard / max(n_i, n_j) (unmatched groups count as 0).
- A combination is eligible only with ≥ 10 such groups on both sides (best scores are
  the same for any minimum from 5 to 15).

| approach | $S_i$–$S_j$ | $(\hat{\theta}_{S_i}, \hat{\theta}_{S_j})$ | compared groups $n_i / n_j$ | best score | median $\mathcal{J}_{ij}$ | ARI | single-snapshot groups ($S_i$ / $S_j$) |
|---|---|---|---|---|---|---|---|
| cumulative | 10–20 | (0.45, 0.35) | 18 / 17 | 0.94 | 1.00 | 0.98 | 33 % / 40 % |
| cumulative | 10–30 | (0.70, 0.55) | 22 / 20 | 0.81 | 1.00 | 0.88 | 45 % / 41 % |
| cumulative | 10–40 | (0.45, 0.10) | 18 / 16 | 0.80 | 1.00 | 0.98 | 33 % / 33 % |
| cumulative | 10–50 | (0.80, 0.70) | 20 / 20 | 0.77 | 0.95 | 0.88 | 61 % / 52 % |
| cumulative | 20–30 | (0.60, 0.65) | 23 / 23 | 0.84 | 1.00 | 0.74 | 45 % / 51 % |
| cumulative | 20–40 | (0.35, 0.35) | 23 / 22 | 0.81 | 1.00 | 0.96 | 40 % / 31 % |
| cumulative | 20–50 | (0.35, 0.45) | 17 / 16 | 0.76 | 1.00 | 0.96 | 40 % / 41 % |
| cumulative | 30–40 | (0.30, 0.40) | 16 / 16 | 0.92 | 1.00 | 0.96 | 31 % / 34 % |
| cumulative | 30–50 | (0.30, 0.10) | 16 / 16 | 0.89 | 1.00 | 0.97 | 31 % / 37 % |
| cumulative | 40–50 | (0.40, 0.10) | 16 / 16 | 0.87 | 1.00 | 0.94 | 34 % / 37 % |
| interval | 20–30 | (0.25, 0.25) | 26 / 25 | 0.50 | 0.56 | 0.60 | 50 % / 56 % |
| interval | 20–40 | (0.35, 0.25) | 50 / 47 | 0.31 | 0.35 | 0.55 | 60 % / 60 % |
| interval | 20–50 | (0.50, 0.35) | 17 / 17 | 0.38 | 0.41 | 0.54 | 75 % / 75 % |
| interval | 30–40 | (0.45, 0.40) | 15 / 15 | 0.49 | 0.62 | 0.69 | 74 % / 76 % |
| interval | 30–50 | (0.40, 0.35) | 17 / 17 | 0.46 | 0.56 | 0.62 | 69 % / 75 % |
| interval | 40–50 | (0.40, 0.40) | 15 / 16 | 0.57 | 0.77 | 0.67 | 76 % / 79 % |
| overlap | 10–20 | (0.10, 0.25) | 20 / 21 | 0.41 | 0.44 | 0.50 | 36 % / 32 % |
| overlap | 10–30 | (0.65, 0.40) | 23 / 22 | 0.37 | 0.44 | 0.53 | 72 % / 42 % |
| overlap | 10–40 | (0.45, 0.10) | 24 / 24 | 0.33 | 0.31 | 0.46 | 52 % / 37 % |
| overlap | 20–30 | (0.80, 0.75) | 37 / 39 | 0.42 | 0.46 | 0.57 | 84 % / 82 % |
| overlap | 20–40 | (0.45, 0.40) | 60 / 51 | 0.31 | 0.36 | 0.60 | 44 % / 53 % |
| overlap | 30–40 | (0.70, 0.65) | 68 / 61 | 0.45 | 0.55 | 0.65 | 78 % / 77 % |

### Observations

- Cumulative: best score 0.76–0.94, median matched similarity 1.0 (0.95 for 10–50), ARI
  0.74–0.99. Flat optimum: 22–90 of 289 combinations within 0.05 of the best, thresholds
  from 0.10 to about 0.80.
- Interval: best score 0.31–0.57; overlap: 0.31–0.45. No threshold combination makes
  their dynamic groups agree.
- An earlier version without the two restrictions picked thresholds that link almost
  nothing (84–99 % single-snapshot groups) for interval and overlap, and once a
  combination with a single compared group; the restrictions remove both effects.

## Community detection algorithm: Louvain vs greedy modularity

Independent of the threshold analysis. Script: `scripts/algorithm_comparison.py`;
outputs in `outputs/algorithm_comparison/`:
`approach_summary.csv`, `snapshot_summary.csv` (one row per snapshot),
`matched_pairs.csv` (every matched pair of communities), `crosstabs/{approach}_tNN.csv`
(cross table per snapshot, Louvain rows, greedy columns, matched pairs on the diagonal,
empty = Jaccard 0), `figures/crosstab_example.png` (one excerpt per approach: the
snapshot with the median mean matched Jaccard, matched ranks around the median).

S = 20 for all approaches; static communities compared snapshot by snapshot (no dynamic
groups, no threshold). Louvain reproduces the existing 20-snapshot runs exactly.

| approach | communities Louvain / greedy | matched pairs | mean $J$ | median $J$ | $J \ge 0.5$ | identical ($J \ge 0.99$) | partners per community | mean $J$ per snapshot (min–max) | mean $J$, size ≥ 20 / < 20 |
|---|---|---|---|---|---|---|---|---|---|
| cumulative | 267 / 269 | 258 | 0.71 | 0.79 | 78 % | 14 % | 2.68 | 0.55–0.83 | 0.69 / 0.83 |
| interval | 301 / 300 | 287 | 0.75 | 0.83 | 83 % | 17 % | 2.53 | 0.62–0.88 | 0.72 / 0.94 |
| overlap | 289 / 285 | 280 | 0.72 | 0.78 | 79 % | 16 % | 2.55 | 0.54–0.87 | 0.70 / 0.85 |

### Observations

- Almost the same number of communities from both algorithms; nearly all matched.
- Median matched Jaccard 0.78–0.83, 78–83 % of pairs ≥ 0.5, 14–17 % identical;
  2.5–2.7 partners per community (boundary members assigned differently).
- Large communities (≥ 20 members) agree less (0.69–0.72) than small ones (0.83–0.94).
- The three approaches are affected equally (mean 0.71 / 0.75 / 0.72).
- Largely 1:1 correspondence: broadly robust to the algorithm, but boundaries of large
  communities vary.

## Fixed window width: robustness to the number of snapshots

Window width fixed to W = 50 days, stride Δ = W/k (k = 1…5), window ends t = 50 + jΔ.
Cumulative windows [0, t], sliding windows [t − 50, t]; for k = 1 the sliding windows
do not overlap and are the interval approach with 50-day windows. Common time points
are the exact intersections of the window ends (≥ 10 per pair, 20 for k = 2 vs 4).
One Jaccard threshold θ for both configurations, swept over 0.10–0.90; θ chosen per
approach by the highest mean score over the 10 pairs.

| $k$ | stride $\Delta$ (days) | window ends $t$ (days) | $S$ |
|---|---|---|---|
| 1 | 50 | 50, 100, …, 500 | 10 |
| 2 | 25 | 50, 75, …, 525 | 20 |
| 3 | 16.7 | 50, 66.7, …, 516.7 | 29 |
| 4 | 12.5 | 50, 62.5, …, 525 | 39 |
| 5 | 10 | 50, 60, …, 520 | 48 |

### Score per threshold (mean over the 10 pairs, minimum in brackets)

| $\theta$ | cumulative: mean score (min) | cumulative: mean ARI | overlapping: mean score (min) | overlapping: mean ARI |
|---|---|---|---|---|
| 0.10 | 0.77 (0.71) | 0.89 | 0.57 (0.49) | 0.74 |
| 0.20 | 0.77 (0.71) | 0.89 | 0.57 (0.49) | 0.74 |
| 0.30 | 0.81 (0.73) | 0.90 | 0.61 (0.54) | 0.77 |
| 0.35 | 0.79 (0.73) | 0.92 | 0.68 (0.62) | 0.83 |
| 0.40 | 0.79 (0.72) | 0.92 | 0.64 (0.56) | 0.83 |
| 0.50 | 0.80 (0.74) | 0.92 | 0.66 (0.53) | 0.91 |
| 0.55 | 0.75 (0.69) | 0.85 | 0.68 (0.53) | 0.94 |
| 0.60 | 0.72 (0.61) | 0.82 | 0.68 (0.50) | 0.91 |
| 0.70 | 0.69 (0.64) | 0.83 | 0.55 (0.42) | 0.80 |

### Cumulative, θ = 0.30

| $(k_i, k_j)$ | $S_i$ / $S_j$ | common time points | groups $S_i$ / $S_j$ | single-snapshot groups | compared groups $n_i$ / $n_j$ | median $\mathcal{J}_{ij}$ | score | ARI |
|---|---|---|---|---|---|---|---|---|
| (1, 2) | 10 / 20 | 10 | 28 / 36 | 43 % / 39 % | 16 / 16 | 1.00 | 0.88 | 0.98 |
| (1, 3) | 10 / 29 | 10 | 28 / 47 | 43 % / 36 % | 16 / 16 | 1.00 | 0.83 | 0.82 |
| (1, 4) | 10 / 39 | 10 | 28 / 47 | 43 % / 38 % | 16 / 18 | 1.00 | 0.74 | 0.94 |
| (1, 5) | 10 / 48 | 10 | 28 / 47 | 43 % / 23 % | 16 / 16 | 1.00 | 0.85 | 0.96 |
| (2, 3) | 20 / 29 | 10 | 36 / 47 | 39 % / 36 % | 16 / 16 | 0.92 | 0.80 | 0.81 |
| (2, 4) | 20 / 39 | 20 | 36 / 47 | 39 % / 38 % | 22 / 23 | 1.00 | 0.83 | 0.97 |
| (2, 5) | 20 / 48 | 10 | 36 / 47 | 39 % / 23 % | 16 / 16 | 1.00 | 0.82 | 0.98 |
| (3, 4) | 29 / 39 | 10 | 47 / 47 | 36 % / 38 % | 16 / 18 | 1.00 | 0.73 | 0.79 |
| (3, 5) | 29 / 48 | 10 | 47 / 47 | 36 % / 23 % | 16 / 16 | 1.00 | 0.79 | 0.80 |
| (4, 5) | 39 / 48 | 10 | 47 / 47 | 38 % / 23 % | 18 / 16 | 1.00 | 0.78 | 0.94 |

### Overlapping (sliding) windows, θ = 0.35

| $(k_i, k_j)$ | $S_i$ / $S_j$ | common time points | groups $S_i$ / $S_j$ | single-snapshot groups | compared groups $n_i$ / $n_j$ | median $\mathcal{J}_{ij}$ | score | ARI |
|---|---|---|---|---|---|---|---|---|
| (1, 2) | 10 / 20 | 10 | 62 / 73 | 58 % / 37 % | 26 / 26 | 1.00 | 0.82 | 0.89 |
| (1, 3) | 10 / 29 | 10 | 62 / 85 | 58 % / 34 % | 26 / 27 | 1.00 | 0.74 | 0.83 |
| (1, 4) | 10 / 39 | 10 | 62 / 107 | 58 % / 40 % | 26 / 26 | 0.80 | 0.73 | 0.88 |
| (1, 5) | 10 / 48 | 10 | 62 / 104 | 58 % / 34 % | 26 / 29 | 0.79 | 0.64 | 0.81 |
| (2, 3) | 20 / 29 | 10 | 73 / 85 | 37 % / 34 % | 26 / 27 | 0.89 | 0.68 | 0.81 |
| (2, 4) | 20 / 39 | 20 | 73 / 107 | 37 % / 40 % | 46 / 51 | 0.80 | 0.65 | 0.79 |
| (2, 5) | 20 / 48 | 10 | 73 / 104 | 37 % / 34 % | 26 / 29 | 0.92 | 0.65 | 0.81 |
| (3, 4) | 29 / 39 | 10 | 85 / 107 | 34 % / 40 % | 27 / 26 | 0.71 | 0.62 | 0.81 |
| (3, 5) | 29 / 48 | 10 | 85 / 104 | 34 % / 34 % | 27 / 29 | 0.75 | 0.67 | 0.86 |
| (4, 5) | 39 / 48 | 10 | 107 / 104 | 40 % / 34 % | 26 / 29 | 0.69 | 0.63 | 0.81 |

### Observations

- Overlapping windows become robust: score 0.62–0.82 (before: 0.31–0.45 with the best
  threshold pair per comparison), median matched Jaccard 0.69–1.00, ARI 0.79–0.89.
- Cumulative stays robust with one θ: score 0.74–0.88, median matched Jaccard 0.92–1.00,
  ARI 0.79–0.98; flat over θ = 0.10–0.50.
- Agreement decreases slightly as the resolutions differ more (overlap k = 1 vs 2: 0.82,
  k = 1 vs 5: 0.64); the number of groups still grows with S at fixed θ (62 → 104–107)
  through short-lived groups between the common time points.
- Interval can only be run at one resolution with a fixed W (k = 1), since its window
  width equals its stride.
- The earlier non-robustness of interval and overlap is a sensitivity to the window
  width, not to the number of snapshots.

## Decisions

Choices made by the author during the analysis.

- Matching criterion: absolute Jaccard only (not the adaptive Jaccard, not stability).
- Reference levels for the number of groups: cumulative 70, interval 200,
  overlap 110.
- Interval and overlap have no number of groups reached by all five snapshot
  counts; the analysis uses only the snapshot counts that reach the reference
  level (interval: 20 to 50, overlap: 10 to 40).
- Thresholds: the exact interpolated θ* is used (matching re-run at θ*), not the
  nearest grid value.
- Group descriptors at θ*: lifespan (days between the first and last window end)
  and maximum size.
- Community comparison across snapshot counts, overlapping windows: the window ends
  of different snapshot counts do not coincide, so each time point of the
  configuration with fewer snapshots is paired with the nearest window end of the
  other configuration (window ends, not window centres, for consistency with
  cumulative and interval).
- Community comparison across snapshot counts, missing time points: a common time
  point at which only one of the two groups exists counts as Jaccard 0 in the mean.
- Presentation: the group lifespans are shown as bars (groups observed in one snapshot
  only vs groups living ≥ 100 days), not as a lifespan/size scatter.
- Presentation: the cross tables are reported as tables (CSV files and excerpts above),
  not plotted; no box plots of the matched values.
- Presentation: cells of the cross tables with Jaccard 0 are left empty.
- Presentation: the cross tables are illustrated by one small annotated excerpt per
  approach (S = 20 vs S = 40, 5 groups around the median matched rank plus their
  strongest other partners), not by heatmaps of the full table or a bipartite graph.
- Joint threshold search: both thresholds varied over 0.10–0.90; only groups present at
  ≥ 2 common time points are compared (dynamic groups with a history); score = sum of
  matched mean Jaccard / max(n_i, n_j); at least 10 compared groups on both sides.
- Algorithm comparison: greedy modularity maximisation (networkx
  `greedy_modularity_communities`, Clauset–Newman–Moore) vs Louvain, S = 20, same
  settings (weighted, resolution 1, min. community size 3); static communities compared
  per snapshot.
- Fixed window width: W = 50 days for every snapshot count, stride Δ = W/k with
  k = 1…5 (S = 10, 20, 29, 39, 48); cumulative [0, t] and sliding [t − W, t] on the same
  grid of window ends; interval = the k = 1 sliding run (not run separately).
- Fixed window width: one Jaccard threshold θ for all snapshot counts (no θ*
  calibration), chosen per approach by the highest mean score over all pairs
  (cumulative θ = 0.30, overlapping θ = 0.35).
