# Sensitivity analysis

## Setting

- Three snapshot-construction approaches: **cumulative**, **interval** and
  **overlapping** windows.
- Number of snapshots $S \in \{10, 20, 30, 40, 50\}$ over the same lifespan.
- Static communities in each snapshot are detected with Louvain.
- Dynamic groups are built by matching communities of consecutive snapshots with
  the Jaccard index

$$
J(A, B) = \frac{|A \cap B|}{|A \cup B|}
$$

  A community $C_t$ in snapshot $t$ continues the dynamic group of community
  $C_{t-1}$ in snapshot $t-1$ when $J(C_{t-1}, C_t) \ge \theta$; otherwise it
  starts a new dynamic group.
- Jaccard threshold $\theta \in \{0.10, 0.15, \ldots, 0.90\}$.
- For each configuration $(a, S, \theta)$, with $a$ the approach, we record the
  number of dynamic groups $N(a, S, \theta)$.

## Number of groups as a function of the Jaccard threshold

### Method

For each approach $a$ we plot $N(a, S, \theta)$ against $\theta$, one curve per
$S$. A horizontal reference level $N^*$ (number of groups) is chosen, and for each
$S$ we look for the threshold $\theta^*_S$ at which the curve reaches it:

$$
N(a, S, \theta^*_S) = N^*
$$

$\theta^*_S$ is obtained by linear interpolation between the two neighbouring
grid points. The goal is a value $N^*$ that is reached by all five
snapshot configurations. That gives a set of pairs $(S_i, \theta^*_{S_i})$ that
produce the same number of dynamic groups.

### Results

Range of $N(a, S, \theta)$ over $\theta \in [0.10, 0.90]$:

| approach   | S = 10   | S = 20   | S = 30    | S = 40    | S = 50    |
|------------|----------|----------|-----------|-----------|-----------|
| cumulative | 25 – 83  | 31 – 144 | 38 – 191  | 46 – 222  | 59 – 286  |
| interval   | 33 – 143 | 66 – 299 | 109 – 458 | 156 – 618 | 198 – 803 |
| overlap    | 31 – 127 | 48 – 276 | 85 – 432  | 103 – 563 | 128 – 734 |

Chosen reference levels and the corresponding thresholds $\theta^*_S$:

| approach   | $N^*$ | curves reached | S = 10 | S = 20 | S = 30 | S = 40 | S = 50 |
|------------|-------|----------------|--------|--------|--------|--------|--------|
| cumulative | 70    | 5 / 5          | 0.87   | 0.75   | 0.56   | 0.52   | 0.43   |
| interval   | 200   | 4 / 5          | –      | 0.52   | 0.32   | 0.22   | 0.11   |
| overlap    | 110   | 4 / 5          | 0.79   | 0.46   | 0.32   | 0.23   | –      |

### Analysis

- $N(a, S, \theta)$ increases monotonically with $\theta$ for every approach and
  every $S$: a stricter threshold breaks more continuation links between
  consecutive snapshots, so more distinct dynamic groups are produced.
- $N(a, S, \theta)$ also increases with $S$ at a fixed $\theta$, and the curves
  never cross. More snapshots mean more matching steps, and each step is a chance
  for a chain to break.
- Cumulative is the least sensitive approach (25 to 286 groups over the whole
  grid); interval is the most sensitive (33 to 803).
- Only the cumulative approach has a common number of groups reached by all
  five snapshot configurations (any $N^* \in [59, 83]$). For interval and overlap
  the maximum of the $S = 10$ curve lies below or at the minimum of the $S = 50$
  curve, so no common level exists within $\theta \in [0.10, 0.90]$.
- To keep the same number of groups as $S$ grows, $\theta$ has to decrease
  substantially (cumulative: from 0.87 at $S = 10$ to 0.43 at $S = 50$). The
  Jaccard threshold and the number of snapshots are therefore not independent
  parameters. A "well-defined" threshold has to be chosen jointly with $S$.

## Dynamic groups at matched group counts

### Method

For each approach $a$ and each snapshot count $S$ whose curve reaches the reference
level $N^*$, the dynamic groups are recomputed with the matching threshold set to
exactly $\theta^*_S$. Configurations that never reach $N^*$ are excluded (interval
$S = 10$, overlap $S = 50$). The time point of a snapshot is the end of its window,
$t$. For a dynamic group $D$ observed at the time points $t_{\text{first}}, \ldots,
t_{\text{last}}$ with member sets $U(D, t)$ we record

$$
\ell(D) = t_{\text{last}} - t_{\text{first}} \quad \text{(lifespan, days)}, \qquad
m(D) = \max_t |U(D, t)| \quad \text{(maximum size)}
$$

A group observed in a single snapshot has $\ell(D) = 0$.

### Results

| approach   | $S$ | $\theta^*_S$ | groups | median $\ell$ (days) | median $m$ | single-snapshot groups | groups with $\ell \ge 100$ days |
|------------|-----|--------------|--------|----------------------|------------|------------------------|---------------------------------|
| cumulative | 10  | 0.867        | 66     | 0.0                  | 58.0       | 46                     | 16                              |
| cumulative | 20  | 0.753        | 71     | 0.0                  | 51.0       | 39                     | 16                              |
| cumulative | 30  | 0.564        | 72     | 17.5                 | 46.0       | 29                     | 17                              |
| cumulative | 40  | 0.523        | 70     | 13.2                 | 33.5       | 30                     | 15                              |
| cumulative | 50  | 0.433        | 70     | 10.5                 | 27.5       | 28                     | 15                              |
| interval   | 20  | 0.517        | 205    | 0.0                  | 46.0       | 163                    | 7                               |
| interval   | 30  | 0.321        | 199    | 0.0                  | 40.0       | 134                    | 14                              |
| interval   | 40  | 0.221        | 196    | 0.0                  | 29.5       | 108                    | 13                              |
| interval   | 50  | 0.106        | 199    | 0.0                  | 26.0       | 107                    | 21                              |
| overlap    | 10  | 0.793        | 110    | 0.0                  | 54.5       | 93                     | 2                               |
| overlap    | 20  | 0.463        | 112    | 25.0                 | 54.0       | 54                     | 13                              |
| overlap    | 30  | 0.316        | 109    | 17.0                 | 33.0       | 40                     | 16                              |
| overlap    | 40  | 0.228        | 109    | 12.8                 | 32.0       | 43                     | 18                              |

### Analysis

- Matching the threshold to the number of snapshots reproduces the target number of
  groups closely (deviation at most 6 groups), confirming that $\theta^*_S$ is a
  meaningful calibration.
- For the cumulative approach the number of long-lived groups ($\ell \ge 100$ days)
  is nearly invariant in $S$ (15 to 17). This is a first indication that the
  persistent structure is preserved across snapshot counts once $\theta$ is
  calibrated.
- The median maximum size decreases with $S$ for all approaches. With more snapshots,
  each window covers less activity (interval, overlap) or more of the windows end early
  in the period (cumulative). Louvain then finds smaller static communities, so small,
  short-lived groups make up a larger share of a fixed group count.
- The interval approach is dominated by groups observed in a single snapshot (more
  than half in every configuration), so an equal group count does not imply an equal
  persistent structure.
- The overlap approach at $S = 10$ is an outlier: 85 % of its groups are
  single-snapshot and only 2 reach 100 days, against 13 to 18 for $S = 20$ to $40$.
- The distributions of $(\ell, m)$ look similar across $S$ for cumulative, and for
  $S \ge 20$ in interval and overlap. Whether the groups are the *same* groups is
  tested at member level in the next section.

## Robustness of the dynamic groups to the number of snapshots

### Hypothesis

> **H.** For a well-chosen Jaccard threshold, the number of snapshots does not
> affect the identified dynamic groups.

The thresholds $\theta^*_S$ of the previous sections equalise the *number* of
groups across snapshot counts. Here we test whether they also produce the *same*
groups, i.e. groups with the same members at the same points in time. The test is
carried out separately for each approach (cumulative, interval, overlapping).

### Notation

For an approach $a$ and a snapshot count $S_i$ whose curve reaches $N^*$, let

$$
T_{S_i} = \{t_1, t_2, \ldots, t_{S_i}\}
$$

be the time points of the configuration, where $t_k$ is the end of the $k$-th
snapshot window. Matching the static communities with threshold
$\theta^*_{S_i}$ yields the set of dynamic groups

$$
\mathbb{D}_{S_i} = \{ D_1, D_2, \ldots, D_{n_i} \}.
$$

Each dynamic group $D_k$ is characterised by its set of members at every time point,

$$
U(D_k, t) \subseteq V, \qquad t \in T_{S_i},
$$

with $U(D_k, t) = \emptyset$ when $D_k$ is not observed at $t$ (if $D_k$ holds
several communities at $t$, $U(D_k, t)$ is their union). The sequence of member
sets over time is the *chronicle* of $D_k$:

$$
M(D_k) = \big( U(D_k, t_1), U(D_k, t_2), \ldots \big).
$$

### Common time points

Two configurations $S_i < S_j$ can only be compared at time points they share.
For the cumulative and interval approaches, the window ends of $S_i$ and $S_j$
lie on the grids $526/S_i$ and $526/S_j$ days, and the comparison uses their
intersection

$$
T_{ij} = T_{S_i} \cap T_{S_j},
$$

e.g. for $S_i = 10$, $S_j = 20$ and a lifespan of 526 days, $T_{ij}$ contains the
10 window ends of $S_i$. Every pair has $|T_{ij}| = 10$, except $(20, 40)$ with
$|T_{ij}| = 20$.

For the overlapping approach the window width depends on the number of snapshots,
$W = 1052 / (S + 1)$ days with stride $W/2$, so the window ends lie on the grid
$526 / (S + 1)$ and two configurations share almost no exact time point. Each time
point of the configuration with fewer snapshots is therefore paired with the
nearest window end of the other configuration:

$$
P_{ij} = \big\{ (t, \tau(t)) \;:\; t \in T_{S_i} \big\}, \qquad
\tau(t) = \arg\min_{t' \in T_{S_j}} |t - t'|,
$$

which places the two time points of each pair at most half a stride apart. For
the cumulative and interval approaches $P_{ij} = \{(t, t) : t \in T_{ij}\}$.

### Similarity of two dynamic groups

For $D \in \mathbb{D}_{S_i}$ and $D' \in \mathbb{D}_{S_j}$, let

$$
P_{ij}(D, D') = \{ (t, t') \in P_{ij} \;:\; U(D, t) \neq \emptyset \;\lor\; U(D', t') \neq \emptyset \}
$$

be the common time points at which at least one of the two groups exists. Their
similarity is the mean Jaccard index of their member sets over these time points,

$$
\bar{J}(D, D') = \frac{1}{|P_{ij}(D, D')|} \sum_{(t, t') \in P_{ij}(D, D')} J\big(U(D, t), U(D', t')\big),
$$

where a time point at which only one of the two groups exists contributes
$J = 0$. Two groups therefore score high only if they have the same members
**and** exist over the same period. Groups that never exist at a common time point
cannot be compared and are excluded; their number is reported.

### Cross table and one-to-one matching

The similarities of all pairs form the cross table

$$
\mathbf{M}^{(ij)} \in [0, 1]^{n_i \times n_j}, \qquad
\mathbf{M}^{(ij)}_{kl} = \bar{J}(D_k, D'_l).
$$

A one-to-one correspondence between the two group sets is obtained by the
linear sum assignment

$$
\pi^* = \arg\max_{\pi} \sum_{k} \mathbf{M}^{(ij)}_{k, \pi(k)},
$$

where $\pi$ ranges over the injective maps between the smaller and the larger
set (Hungarian algorithm). This gives $\min(n_i, n_j)$ matched pairs and the list
of their similarities

$$
\mathcal{J}_{ij} = \big\{ \mathbf{M}^{(ij)}_{k, \pi^*(k)} \big\}_k,
$$

which is the main outcome: values close to 1 mean that a group of $S_i$ has a
counterpart in $S_j$ with the same chronicle.

### Global agreement: Adjusted Rand Index

As a complementary, matching-free measure, the two configurations are compared as
partitions of node–time elements. Each element $(u, p)$, with $p \in P_{ij}$ and
$u$ a member of some group in both configurations at $p$, is labelled by its group
in $S_i$ and its group in $S_j$. The contingency table of the two labellings is

$$
n_{kl} = \sum_{(t, t') \in P_{ij}} \big| U(D_k, t) \cap U(D'_l, t') \big|,
$$

with row sums $a_k$, column sums $b_l$ and total $n$, and

$$
\mathrm{ARI}_{ij} = \frac{\sum_{kl} \binom{n_{kl}}{2} - \Big[\sum_k \binom{a_k}{2} \sum_l \binom{b_l}{2}\Big] \big/ \binom{n}{2}}
{\tfrac{1}{2}\Big[\sum_k \binom{a_k}{2} + \sum_l \binom{b_l}{2}\Big] - \Big[\sum_k \binom{a_k}{2} \sum_l \binom{b_l}{2}\Big] \big/ \binom{n}{2}}.
$$

$\mathrm{ARI} = 1$ when the two configurations assign every node at every common
time point to corresponding groups, and $\mathrm{ARI} \approx 0$ for chance
agreement. Because it counts node–time elements, the ARI is dominated by large,
long-lived groups, whereas $\mathcal{J}_{ij}$ weights every group equally.

### Evaluation

The comparison is run for every pair $S_i < S_j$ of configurations that reach
$N^*$: 10 pairs for the cumulative approach, 6 each for interval and overlapping.
The hypothesis is supported for an approach when the matched similarities
$\mathcal{J}_{ij}$ are high for most groups and the ARI is high, i.e. the
assignment is close to a 1:1 correspondence between the group sets. Based on the
previous sections, this is expected at least for the cumulative approach.

### Results

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

Share of matched pairs whose chronicles are identical on the common time points
($\mathbf{M}_{k\pi^*(k)} \ge 0.99$), pooled over all pairs of configurations:
cumulative 65 %, interval 3.6 %, overlapping 1.8 %.

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

### Analysis

The experiment tests the hypothesis at member level: for every pair of
configurations, every dynamic group is compared with every dynamic group of the
other configuration over the common time points. The thresholds used are the
equal-count thresholds $\theta^*_S$, so the verdicts below hold **for this choice of
threshold**.

- **Cumulative: hypothesis supported.** In every one of the 10 pairs the median
  matched similarity is 1.0, i.e. more than half of the comparable groups have an
  exact counterpart with the same members at every common time point, and the cross
  tables show a clean 1:1 diagonal. The mean matched similarity is 0.78 to 0.90 and
  the ARI 0.60 to 0.91; agreement is lowest when $S = 10$ is involved
  (ARI 0.60 to 0.68) and highest among the larger snapshot counts (e.g. 0.90 for
  $40$–$50$, 0.91 for $20$–$50$).
- This result is partly structural. A cumulative snapshot at time $t$ always covers
  $[0, t]$, so at a common time point two configurations analyse the *same* graph,
  and Louvain with a fixed seed returns identical static communities (verified for
  all common time points). The only source of disagreement is the temporal
  matching: whether the communities are chained into the same dynamic groups. Values
  below 1 therefore reflect groups whose chain is broken at a different time
  in one configuration, which the $J = 0$ rule for missing time points penalises.
- **Interval: hypothesis not supported at $\theta^*$.** Median matched similarities are
  0.33 to 0.53 and the ARI 0.44 to 0.57; only 3.6 % of the matched groups are identical.
  The diagonal of the cross tables is visible but fades quickly. Here the windows
  of different configurations have different lengths (e.g. 26 vs 10.5 days), so the
  static communities themselves differ, and the equal-count thresholds $\theta^*$ do
  not compensate for that.
- **Overlapping: hypothesis not supported at $\theta^*$.** Median matched similarities
  are 0.22 to 0.40 and the ARI 0.27 to 0.58. Agreement is weakest for pairs involving
  $S = 10$ (ARI 0.27 to 0.41) and best for $30$–$40$ (ARI 0.58). Besides the
  different window widths, time points are paired by nearest window end, so the
  compared windows are additionally shifted by up to half a stride.
- **Structure of the cross tables.** The cross tables are sparse, and their sparsity
  pattern separates the approaches. Counting, for each group $D_k$, the groups $D'_l$
  with $\mathbf{M}^{(ij)}_{kl} > 0$ (its *partners*): in the cumulative approach a group
  has on average 1.00 to 1.11 partners, i.e. its members reappear in exactly one group of
  the other configuration, which is a 1:1 correspondence. In the interval approach a
  group has 4.1 to 5.0 partners and in the overlapping approach 4.3 to 6.9: its members
  are spread over several groups of the other configuration. For a typical group
  (around the median matched rank, $S = 20$ vs $S = 40$) the cumulative cross table is
  a pure diagonal of 1.00, whereas the interval approach gives matched values of about
  0.35 and the overlapping approach about 0.22, each with additional small overlaps
  with other groups.
- A large part of the groups cannot be compared at all: they exist only between
  common time points (e.g. 36 of the 70 groups of $S = 50$ against $S = 10$ in the
  cumulative approach). The comparison is therefore informative about the groups
  that are present at the coarse time resolution, which include all long-lived groups.
- **Conclusion.** With the equal-count Jaccard thresholds $\theta^*_S$, the cumulative
  approach is robust to the number of snapshots: the same dynamic groups are recovered,
  close to a 1:1 correspondence. For interval and overlapping windows these thresholds
  give equal group counts but not the same groups. Since the hypothesis only requires
  *some* well-chosen threshold, all threshold combinations are searched below.
- **Limits of the evidence for the cumulative approach.** The hypothesis is supported
  rather than proven: (i) part of the agreement is structural, since at common time
  points both configurations analyse the same graph and only the temporal chaining is
  tested; (ii) groups that exist only between common time points (up to 36 of 70) are
  not compared; (iii) the correspondence is not perfect: 24 % to 43 % of the matched
  groups differ in lifespan (mean $\mathcal{J}_{ij}$ 0.78 to 0.90), and 18 of 397
  matched pairs share no members ($\bar{J} = 0$).

### Joint search for the best-matching thresholds

The equal-count thresholds $\theta^*_S$ are one particular choice. To test the
hypothesis for *any* choice of threshold, both thresholds are varied jointly over
$\theta_{S_i}, \theta_{S_j} \in \{0.10, 0.15, \ldots, 0.90\}$ (17 × 17 combinations per
pair of configurations). For each combination the dynamic groups of both
configurations are recomputed, the cross table is built and the groups are matched by
linear sum assignment.

**Only dynamic groups with a history are compared.** A high threshold links almost no
communities across snapshots, so every community becomes a group observed at a single
time point. Such groups have no chronicle to compare, yet they are easy to match one by
one at the common time points, so including them rewards thresholds that switch the
temporal matching off. The comparison is therefore restricted to groups that exist at
two or more common time points,

$$
\mathbb{D}^{\,\ge 2}_{S_i} = \{ D \in \mathbb{D}_{S_i} : |\{(t, t') \in P_{ij} : U(D, t) \neq \emptyset\}| \ge 2 \},
$$

and analogously for $S_j$, with $n_i = |\mathbb{D}^{\,\ge 2}_{S_i}|$ and
$n_j = |\mathbb{D}^{\,\ge 2}_{S_j}|$.

**Agreement score.** A group left without a partner counts as 0:

$$
\mathrm{score}_{ij}(\theta_i, \theta_j) = \frac{1}{\max(n_i, n_j)} \sum_{k} \mathbf{M}^{(ij)}_{k, \pi^*(k)},
$$

so that a threshold producing far fewer groups in one configuration cannot reach a
high score by matching only its best groups. A combination is eligible only if
$n_i \ge 10$ and $n_j \ge 10$; otherwise a single well-matched group would decide the
result (the best scores are identical for any minimum between 5 and 15). The
best-matching thresholds are

$$
(\hat{\theta}_{S_i}, \hat{\theta}_{S_j}) = \arg\max_{\theta_i, \theta_j \,:\, n_i, n_j \ge 10} \; \mathrm{score}_{ij}(\theta_i, \theta_j).
$$

#### Results

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

Single-snapshot groups: share of all dynamic groups of the configuration observed in
one snapshot only (shown to confirm that the optimum still contains tracked groups).

#### Analysis

- **Cumulative: hypothesis supported for a broad range of thresholds.** The best scores
  are 0.76–0.94, the median matched similarity is 1.0 (0.95 for $10$–$50$) and the ARI
  0.74–0.99, comparing 16–23 groups with a history per configuration. The score is
  flat around the optimum: for most pairs 22–90 of the 289 combinations lie within 0.05
  of the best score, spanning thresholds from 0.10 to about 0.80. The exact threshold
  therefore matters little; the cumulative approach reproduces the same dynamic groups
  across snapshot counts for most reasonable thresholds.
- **Interval: hypothesis not supported.** Even the best combination reaches only
  0.31–0.57 (median matched similarity 0.36–0.77, ARI 0.54–0.69). No pair of thresholds
  makes the dynamic groups of different snapshot counts agree.
- **Overlapping: hypothesis not supported.** The best scores are 0.31–0.45 (median
  matched similarity 0.31–0.55, ARI 0.46–0.65).
- **Interpretation.** In the interval and overlapping approaches the window length
  changes with the number of snapshots, so the static communities themselves differ,
  and no choice of matching threshold compensates for this. In the cumulative approach
  the snapshot at a common time point covers the same data regardless of the number of
  snapshots, and the threshold only affects how communities are chained; with any
  reasonable threshold the chains agree.
- **Conclusion.** With a careful choice of the Jaccard threshold, the cumulative
  approach is robust to the number of snapshots. The interval and overlapping
  approaches are not: their dynamic groups depend on the snapshot resolution for every
  threshold in $[0.10, 0.90]$.

## Robustness to the number of snapshots at a fixed window width

### Motivation

In the previous experiment the number of snapshots $S$ also set the window width
($W = 526/S$ days for interval windows, $W = 1052/(S+1)$ days for overlapping windows).
At a common time point the two configurations therefore detected communities on
different graphs, and the comparison mixed two effects: the temporal resolution
(how often the network is observed) and the aggregation scale (how much interaction
one snapshot contains). Only the cumulative approach, whose graph at $t$ is always
$[0, t]$, was free of the second effect, and only the cumulative approach was robust.
This experiment separates the two effects by fixing the window width and varying only
the temporal resolution.

### Hypothesis

For a fixed window width $W$ and a fixed Jaccard threshold $\theta$, the number of
snapshots does not affect the dynamic groups.

### Configuration

The window width is fixed to $W = 50$ days and the stride is $\Delta_k = W/k$,
$k = 1, \dots, 5$. The window ends are

$$t_j^{(k)} = W + j\,\Delta_k, \qquad j = 0, 1, \dots, \qquad t_j^{(k)} \le 526,$$

and the window ending at $t$ is $[0, t]$ (cumulative) or $[t - W, t]$ (sliding,
overlapping by $1 - 1/k$). For $k = 1$ consecutive sliding windows do not overlap, so
this configuration is also the interval approach with 50-day windows; the interval
approach is therefore the $k = 1$ member of the sliding family and is not treated
separately.

| $k$ | stride $\Delta$ (days) | window ends $t$ (days) | $S$ |
|---|---|---|---|
| 1 | 50 | 50, 100, …, 500 | 10 |
| 2 | 25 | 50, 75, …, 525 | 20 |
| 3 | 16.7 | 50, 66.7, …, 516.7 | 29 |
| 4 | 12.5 | 50, 62.5, …, 525 | 39 |
| 5 | 10 | 50, 60, …, 520 | 48 |

Properties of this configuration:

- Every window has the same width, so the snapshot graph at a time point $t$ is the
  same for every $k$.
- The common time points are exact: $T_{ij} = T_{S_i} \cap T_{S_j}$ contains at least
  the multiples of $W$ ($t = 50, 100, \dots, 500$, i.e. 10 points), and 20 points for
  $(k_i, k_j) = (2, 4)$. No pairing of nearest window ends is needed.
- The same threshold $\theta$ is used for both configurations of a comparison, so the
  rule that links communities over time is the same for all $S$.

### Evaluation

The dynamic groups of $(k_i, \theta)$ and $(k_j, \theta)$ are compared exactly as in the
joint search: only groups present at two or more common time points are compared, the
cross table holds the mean Jaccard $\bar{J}(D, D')$ over the common time points at which
at least one of the two groups exists, groups are matched one-to-one by linear sum
assignment, and

$$\text{score}_{ij}(\theta) = \frac{\sum_k \mathbf{M}^{(ij)}_{k\pi^*(k)}}{\max(n_i, n_j)}.$$

$\theta$ is varied over $0.10, 0.15, \dots, 0.90$; a value is eligible for a pair if both
configurations have at least 10 compared groups. A single threshold for all snapshot
counts is chosen per approach as the value with the highest mean score over the 10
pairs $(k_i, k_j)$.

### Results

Mean (minimum) score and mean ARI over the 10 pairs, per threshold (– : not eligible
for every pair):

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

The highest mean score is reached at $\theta = 0.30$ for the cumulative approach (0.81,
with 0.80 at $\theta = 0.50$) and at $\theta = 0.35$ for overlapping windows (0.68, minimum
0.62).

Cumulative, $\theta = 0.30$:

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

Overlapping (sliding) windows, $\theta = 0.35$ ($k = 1$ is the interval approach):

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

Comparison with the previous configuration (window width depending on $S$, best
thresholds per pair):

| approach | window width depends on $S$: best score | fixed $W$, one $\theta$: score | fixed $W$, one $\theta$: median $\mathcal{J}_{ij}$ | fixed $W$, one $\theta$: ARI |
|---|---|---|---|---|
| cumulative | 0.76–0.94 | 0.74–0.88 | 0.92–1.00 | 0.79–0.98 |
| interval | 0.31–0.57 | (= overlapping, $k = 1$) | | |
| overlapping | 0.31–0.45 | 0.62–0.82 | 0.69–1.00 | 0.79–0.89 |

### Analysis

- **Fixing the window width makes overlapping windows robust to the number of
  snapshots.** With a single threshold for all five resolutions, the score rises from
  0.31–0.45 (best threshold pair per comparison, window width depending on $S$) to
  0.62–0.82, the median matched Jaccard from 0.31–0.55 to 0.69–1.00 and the ARI from
  0.46–0.65 to 0.79–0.89. Most matched groups are identical on the common time points.
- **The window width, not the number of snapshots, caused the earlier failure.** Once
  the graph at a time point no longer depends on $S$, the remaining differences come
  only from how communities are linked between the time points, and these differences
  are small. This confirms the explanation given for the previous experiment.
- **Cumulative remains robust with one threshold.** The scores (0.74–0.88) are close to
  the best scores of the joint search (0.76–0.94), which used a different pair of
  thresholds for every comparison. The cumulative approach is insensitive to $\theta$ over
  a wide range (mean score 0.77–0.81 for $\theta = 0.10$–$0.50$).
- **A single threshold works for all resolutions.** No calibration of $\theta$ per
  snapshot count is needed once $W$ is fixed; for overlapping windows the mean score is
  stable around 0.64–0.68 for $\theta = 0.35$–$0.60$, with the lowest pair scores at the
  largest differences in resolution ($k = 1$ vs 5: 0.64).
- **Agreement decreases slightly with the difference in resolution.** For overlapping
  windows the pairs with $k_i = 1$ score 0.82 against $k = 2$ and 0.64 against $k = 5$:
  between two common time points a finer resolution observes more intermediate windows,
  at which a group can split or end. The total number of groups therefore still grows
  with $S$ at a fixed $\theta$ (62 for $S = 10$, 104–107 for $S = 39$–$48$); the additional
  groups are mostly short-lived groups between the common time points.
- **Caveats.** Only groups present at two or more common time points are compared (26–51
  of 62–107 groups for overlapping windows, 16–23 for cumulative). The interval approach
  can only be tested at one resolution, because its window width equals its stride:
  for interval windows the number of snapshots is the aggregation scale, and its effect
  is the sensitivity to the window width, not to the temporal resolution.
- **Conclusion.** With a fixed window width and a single Jaccard threshold, the
  hypothesis holds for both the cumulative and the sliding-window construction: the
  number of snapshots changes the temporal resolution but not the dynamic groups that
  are observed at the common time points. The sensitivity found in the previous
  experiment is a sensitivity to the window width.

## Robustness to the community detection algorithm

### Question

Do the snapshot communities depend on the community detection algorithm? The
pipeline uses Louvain; here it is compared with greedy modularity maximisation
(Clauset–Newman–Moore). This analysis is independent of the matching threshold: no
dynamic groups are built, only the static communities of each snapshot are compared.

### Method

The number of snapshots is fixed at $S = 20$ for all three approaches. For every
snapshot $t \in T_{S}$ the weighted snapshot graph $G_t$ is partitioned by both
algorithms with the same settings (edge weights = number of e-mails, resolution 1,
communities with fewer than 3 members discarded):

$$
\mathcal{C}^{A_1}_t = \{C_1, \ldots, C_{m}\} \quad \text{(Louvain)}, \qquad
\mathcal{C}^{A_2}_t = \{C'_1, \ldots, C'_{m'}\} \quad \text{(greedy modularity)}.
$$

At each snapshot the two community sets form a cross table of Jaccard indices,

$$
\mathbf{A}^{(t)} \in [0, 1]^{m \times m'}, \qquad \mathbf{A}^{(t)}_{kl} = J(C_k, C'_l),
$$

and the communities are matched one-to-one by linear sum assignment,

$$
\pi^*_t = \arg\max_{\pi} \sum_k \mathbf{A}^{(t)}_{k, \pi(k)},
$$

giving $\min(m, m')$ matched pairs per snapshot and the list of their Jaccard values
$\{\mathbf{A}^{(t)}_{k, \pi^*_t(k)}\}$. These lists are pooled over the 20 snapshots of
each approach. A high correspondence (values close to 1, a 1:1 mapping) means the
approach is robust to the choice of algorithm. As before, the number of *partners* of
a community $C_k$ is the number of communities $C'_l$ with $\mathbf{A}^{(t)}_{kl} > 0$.

### Results

| approach | communities Louvain / greedy | matched pairs | mean $J$ | median $J$ | $J \ge 0.5$ | identical ($J \ge 0.99$) | partners per community | mean $J$ per snapshot (min–max) | mean $J$, size ≥ 20 / < 20 |
|---|---|---|---|---|---|---|---|---|---|
| cumulative | 267 / 269 | 258 | 0.71 | 0.79 | 78 % | 14 % | 2.68 | 0.55–0.83 | 0.69 / 0.83 |
| interval | 301 / 300 | 287 | 0.75 | 0.83 | 83 % | 17 % | 2.53 | 0.62–0.88 | 0.72 / 0.94 |
| overlap | 289 / 285 | 280 | 0.72 | 0.78 | 79 % | 16 % | 2.55 | 0.54–0.87 | 0.70 / 0.85 |

### Analysis

- **Both algorithms find almost the same number of communities** (267 vs 269, 301 vs
  300, 289 vs 285 over the 20 snapshots), and nearly every community has a matched
  counterpart.
- **The correspondence is clear but not exact.** The median matched Jaccard is
  0.78–0.83 and 78–83 % of the matched pairs have $J \ge 0.5$, but only 14–17 % are
  identical. Each Louvain community shares members with 2.5–2.7 greedy communities on
  average: the core of a community is found by both algorithms, while members at the
  boundary are assigned differently.
- **Large communities differ more.** Communities with at least 20 members reach a mean
  matched Jaccard of 0.69–0.72, smaller ones 0.83–0.94. The algorithms agree on small,
  well-separated communities and draw the boundaries of large communities differently.
- **The three approaches are affected equally.** The mean matched Jaccard is 0.71
  (cumulative), 0.75 (interval) and 0.72 (overlapping), with similar ranges over time
  (0.54–0.88 per snapshot). The choice of algorithm does not favour one snapshot
  construction over another.
- **Conclusion.** The communities correspond largely 1:1 between Louvain and greedy
  modularity, so the identified community structure is broadly robust to the
  algorithm. The boundaries of large communities, however, depend on the algorithm
  (about 30 % of their members differ), so results that rely on exact memberships
  should be read with this variability in mind.
