# Sensitivity analysis

## Setting

- Three snapshot-construction approaches: **cumulative**, **interval** and
  **overlapping** windows, over the observation period $[0, T]$, $T = 526$ days.
- Static communities in each snapshot are detected with Louvain.
- Dynamic groups are built by matching communities of consecutive snapshots with
  the Jaccard index

$$
J(A, B) = \frac{|A \cap B|}{|A \cup B|}
$$

  Only pairs with $J(C_{t-1}, C_t) \ge \theta$ are candidates. A community $C_t$ with
  one candidate predecessor continues its dynamic group; with several candidates it
  continues the group of the predecessor with the highest Jaccard index. If the
  predecessor itself has several candidate successors (a split), only the successor
  with the highest Jaccard index continues the group. A community without an accepted
  predecessor starts a new dynamic group.
- The matching criterion of this analysis is the absolute Jaccard index; the stability
  criterion of the main pipeline is not varied here.
- Jaccard threshold $\theta \in \{0.10, 0.15, \ldots, 0.90\}$.

### Snapshot windows

The window width does not depend on the number of snapshots: interval and overlapping
windows have the width $W = 50$ days, cumulative windows start at the beginning of the
period. Only the stride changes, $\Delta_k = W / k$ with $k = 1, \dots, 5$, and the
window ends are anchored at the end of the observation period:

$$
t^{(k)}_j = T - j\,\Delta_k, \qquad j = 0, 1, \dots, \qquad t^{(k)}_j \ge W .
$$

The window ending at $t$ is

$$
w(t) = \begin{cases} [0, t] & \text{cumulative} \\ [t - W, t] & \text{interval, overlapping} \end{cases}
$$

so consecutive sliding windows overlap by a fraction $1 - 1/k$. The number of
snapshots follows from the stride,

$$
S_k = \left\lfloor \frac{T - W}{\Delta_k} \right\rfloor + 1 = \left\lfloor \frac{476\,k}{50} \right\rfloor + 1, \qquad S \in \{10, 20, 29, 39, 48\}.
$$

| $k$ | stride $\Delta_k$ (days) | window ends $t$ (days) | $S$ |
|---|---|---|---|
| 1 | 50 | 76, 126, …, 526 | 10 |
| 2 | 25 | 51, 76, …, 526 | 20 |
| 3 | 16.7 | 59.3, 76, …, 526 | 29 |
| 4 | 12.5 | 51, 63.5, …, 526 | 39 |
| 5 | 10 | 56, 66, …, 526 | 48 |

- The number of snapshots $S$ is therefore the **temporal resolution** (how often the
  network is observed); the window ending at a time point $t$, and hence its snapshot
  graph, is the same for all $S$.
- For the overlapping approach the overlap of consecutive windows changes with $S$:
  $1 - 1/k = 0\,\%, 50\,\%, 67\,\%, 75\,\%, 80\,\%$ for $S = 10, 20, 29, 39, 48$. A higher
  temporal resolution therefore also means more shared interaction between consecutive
  snapshots.
- Interval windows do not overlap, so their stride equals their width: they exist only
  for $k = 1$ ($S = 10$), where they coincide with the overlapping windows. All interval
  results below are therefore identical to the overlapping results for $S = 10$, and the
  interval approach cannot be compared across snapshot counts.
- Every configuration shares the last snapshot ($[476, 526]$, cumulative $[0, 526]$).
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
grid points. The goal is a value $N^*$ that is reached by all snapshot configurations of the
approach (five for cumulative and overlapping, one for interval). That gives a set of pairs $(S_i, \theta^*_{S_i})$ that
produce the same number of dynamic groups.

### Results

Range of $N(a, S, \theta)$ over $\theta \in [0.10, 0.90]$:

| approach   | S = 10 | S = 20 | S = 29 | S = 39 | S = 48 |
|---|---|---|---|---|---|
| cumulative | 20 – 79 | 31 – 139 | 39 – 165 | 44 – 205 | 57 – 262 |
| interval | 39 – 146 | – | – | – | – |
| overlap | 39 – 146 | 50 – 269 | 57 – 378 | 70 – 459 | 78 – 552 |

Chosen reference levels and the corresponding thresholds $\theta^*_S$:

| approach   | $N^*$ | curves reached | S = 10 | S = 20 | S = 29 | S = 39 | S = 48 |
|---|---|---|---|---|---|---|---|
| cumulative | 70 | 5 / 5 | 0.88 | 0.75 | 0.65 | 0.56 | 0.52 |
| interval | 110 | 1 / 1 | 0.64 | – | – | – | – |
| overlap | 110 | 5 / 5 | 0.64 | 0.48 | 0.42 | 0.40 | 0.37 |

### Analysis

- $N(a, S, \theta)$ increases monotonically with $\theta$ for every approach and
  every $S$: a stricter threshold breaks more continuation links between
  consecutive snapshots, so more distinct dynamic groups are produced.
- $N(a, S, \theta)$ also increases with $S$ at a fixed $\theta$: more snapshots mean
  more matching steps, and each step is a chance for a chain to break.
- Cumulative is the least sensitive approach (20 to 262 groups over the whole grid),
  overlapping the most sensitive (39 to 552).
- Both approaches have a common number of groups reached by all five snapshot counts
  (cumulative: any $N^* \in [57, 79]$; overlapping: any $N^* \in [78, 146]$).
- To keep the same number of groups as $S$ grows, $\theta$ still has to decrease
  (cumulative from 0.88 at $S = 10$ to 0.52 at $S = 48$, overlapping from 0.64 to
  0.37): the *number* of groups depends on both parameters jointly. Whether the groups
  themselves depend on them is tested below.

## Dynamic groups at matched group counts

### Method

For each approach $a$ and each snapshot count $S$ whose curve reaches the reference
level $N^*$, the dynamic groups are recomputed with the matching threshold set to
exactly $\theta^*_S$. The time point of a snapshot is the end of its window,
$t$. For a dynamic group $D$ observed at the time points $t_{\text{first}}, \ldots,
t_{\text{last}}$ with member sets $U(D, t)$ we record

$$
\ell(D) = t_{\text{last}} - t_{\text{first}} \quad \text{(lifespan, days)}, \qquad
m(D) = \max_t |U(D, t)| \quad \text{(maximum size)}
$$

A group observed in a single snapshot has $\ell(D) = 0$.

### Results

| approach   | $S$ | $\theta^*_S$ | groups | median $\ell$ (days) | median $m$ | single-snapshot groups | groups with $\ell \ge 100$ days |
|---|---|---|---|---|---|---|---|
| cumulative | 10 | 0.879 | 66 | 0.0 | 64.5 | 43 | 15 |
| cumulative | 20 | 0.753 | 71 | 25.0 | 59.0 | 34 | 14 |
| cumulative | 29 | 0.650 | 70 | 0.0 | 52.0 | 36 | 17 |
| cumulative | 39 | 0.559 | 70 | 12.5 | 45.0 | 27 | 19 |
| cumulative | 48 | 0.516 | 72 | 10.0 | 26.5 | 32 | 15 |
| interval | 10 | 0.637 | 110 | 0.0 | 50.0 | 93 | 11 |
| overlap | 10 | 0.637 | 110 | 0.0 | 50.0 | 93 | 11 |
| overlap | 20 | 0.480 | 110 | 25.0 | 50.5 | 50 | 11 |
| overlap | 29 | 0.423 | 111 | 16.7 | 54.0 | 47 | 11 |
| overlap | 39 | 0.401 | 112 | 12.5 | 49.0 | 45 | 15 |
| overlap | 48 | 0.373 | 108 | 20.0 | 42.0 | 35 | 19 |

### Analysis

- Matching the threshold to the number of snapshots reproduces the target number of
  groups closely (deviation at most 4 groups).
- The number of long-lived groups ($\ell \ge 100$ days) is similar across $S$
  (cumulative 14 to 19, overlapping 11 to 19).
- The overlapping (and interval) configuration with $S = 10$ is dominated by groups
  observed in a single snapshot (93 of 110): with a stride equal to the window width,
  consecutive windows share no interaction and fewer communities are continued.
- Whether the groups are the *same* groups is tested at member level in the next
  section.

## Robustness of the dynamic groups to the number of snapshots

### Hypothesis

> **H.** For a fixed window width $W$ and a well-chosen Jaccard threshold, the number
> of snapshots does not affect the identified dynamic groups.

The thresholds $\theta^*_S$ of the previous sections equalise the *number* of
groups across snapshot counts. Here we test whether they also produce the *same*
groups, i.e. groups with the same members at the same points in time. The test is
carried out separately for the cumulative and the overlapping approach; the interval
approach has a single snapshot count.

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

Two configurations $S_i < S_j$ can only be compared at time points they share. All
window ends lie on the grid $T - j\,\Delta_k$, so the comparison uses their exact
intersection

$$
T_{ij} = T_{S_i} \cap T_{S_j} \supseteq \{ T - m\,W : m = 0, \dots, 9 \} = \{76, 126, \dots, 526\},
$$

i.e. 10 common time points for every pair, and 20 for $(S_i, S_j) = (20, 39)$. Because
the window width is the same for all $S$, the snapshot graph at a common time point is
identical in both configurations, and the comparison isolates how the communities are
linked over time. In the following, $P_{ij} = \{(t, t) : t \in T_{ij}\}$ denotes the
pairs of common time points.

### Similarity of two dynamic groups

For $D \in \mathbb{D}_{S_i}$ and $D' \in \mathbb{D}_{S_j}$, let

$$
P_{ij}(D, D') = \{ (t, t') \in P_{ij} \;:\; J\big(U(D, t), U(D', t')\big) > 0 \}
$$

be the common time points at which the two groups share at least one member. Their
similarity is the mean Jaccard index of their member sets over these time points,

$$
\bar{J}(D, D') = \frac{1}{|P_{ij}(D, D')|} \sum_{(t, t') \in P_{ij}(D, D')} J\big(U(D, t), U(D', t')\big),
$$

and $\bar{J}(D, D') = 0$ if $P_{ij}(D, D') = \emptyset$. Time points with $J = 0$,
at which one of the two groups does not exist or the two share no member, are left out
of both the sum and the count: $\bar{J}$ measures how similar the member sets are where
the two groups overlap, not whether they exist over the same period. Groups that never
exist at a common time point cannot be compared and are excluded; their number is
reported.

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

Values close to 1 mean that a group of $S_i$ has a counterpart in $S_j$ with the same
members at the common time points where both exist.

### Evaluation

The comparison is run for every pair $S_i < S_j$ of configurations: 10 pairs each for
the cumulative and the overlapping approach. The interval approach has a single
snapshot count and cannot be compared across $S$. The hypothesis is supported for an
approach when the matched similarities $\mathcal{J}_{ij}$ are high for most groups and
the groups correspond one to one (maximum alignment, below).

Since the snapshot graph at a common time point is the same in both configurations, the
communities detected there are the same too. Two groups that share a member at a common
time point therefore hold the same community there, and $\bar J$ takes only the values
0 and 1 (as long as a group holds one community per time point). High matched
similarities follow from the fixed window width; the informative part of the test is
the correspondence: how many groups have a counterpart, and whether it is unique.

### Results at $\theta^*$

| approach | $(S_i, \theta^*_{S_i})$ | $(S_j, \theta^*_{S_j})$ | common time points | compared groups | median $\mathcal{J}_{ij}$ | mean $\mathcal{J}_{ij}$ | identical matched groups |
|---|---|---|---|---|---|---|---|
| cumulative | (10, 0.879) | (20, 0.753) | 10 | 66 / 48 | 1.00 | 0.94 | 94 % |
| cumulative | (10, 0.879) | (29, 0.650) | 10 | 66 / 39 | 1.00 | 1.00 | 100 % |
| cumulative | (10, 0.879) | (39, 0.559) | 10 | 66 / 39 | 1.00 | 0.97 | 97 % |
| cumulative | (10, 0.879) | (48, 0.516) | 10 | 66 / 37 | 1.00 | 0.97 | 97 % |
| cumulative | (20, 0.753) | (29, 0.650) | 10 | 48 / 39 | 1.00 | 0.92 | 92 % |
| cumulative | (20, 0.753) | (39, 0.559) | 20 | 71 / 59 | 1.00 | 0.85 | 85 % |
| cumulative | (20, 0.753) | (48, 0.516) | 10 | 48 / 37 | 1.00 | 0.92 | 92 % |
| cumulative | (29, 0.650) | (39, 0.559) | 10 | 39 / 39 | 1.00 | 0.87 | 87 % |
| cumulative | (29, 0.650) | (48, 0.516) | 10 | 39 / 37 | 1.00 | 0.86 | 86 % |
| cumulative | (39, 0.559) | (48, 0.516) | 10 | 39 / 37 | 1.00 | 0.97 | 97 % |
| overlap | (10, 0.637) | (20, 0.480) | 10 | 110 / 83 | 1.00 | 0.99 | 99 % |
| overlap | (10, 0.637) | (29, 0.423) | 10 | 110 / 75 | 1.00 | 0.96 | 96 % |
| overlap | (10, 0.637) | (39, 0.401) | 10 | 110 / 67 | 1.00 | 1.00 | 100 % |
| overlap | (10, 0.637) | (48, 0.373) | 10 | 110 / 67 | 1.00 | 0.97 | 97 % |
| overlap | (20, 0.480) | (29, 0.423) | 10 | 83 / 75 | 1.00 | 0.96 | 96 % |
| overlap | (20, 0.480) | (39, 0.401) | 20 | 110 / 90 | 1.00 | 0.94 | 94 % |
| overlap | (20, 0.480) | (48, 0.373) | 10 | 83 / 67 | 1.00 | 0.95 | 96 % |
| overlap | (29, 0.423) | (39, 0.401) | 10 | 75 / 67 | 1.00 | 0.94 | 94 % |
| overlap | (29, 0.423) | (48, 0.373) | 10 | 75 / 67 | 1.00 | 0.95 | 96 % |
| overlap | (39, 0.401) | (48, 0.373) | 10 | 67 / 67 | 1.00 | 0.88 | 88 % |

Share of matched pairs that are identical where they overlap ($\bar J \ge 0.99$),
pooled over all pairs: cumulative 92 % (380 of 411), overlapping 96 % (693 of 725).
Every matched pair is either identical or has no overlap at all ($\bar J = 0$; 31 and
32 pairs): since the window at a common time point is the same in both configurations,
the snapshot graphs, and hence the communities, are the same, so two groups that share
a member at a common time point hold the same community there.

### One threshold for all snapshot counts

Since the snapshot at a time point is the same for all $S$, the same threshold can be
used for all $S$. For each $\theta \in \{0.10, 0.15, \dots, 0.90\}$ both configurations
of a pair are matched with $\theta_i = \theta_j = \theta$.

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
\mathrm{score}_{ij}(\theta) = \frac{1}{\max(n_i, n_j)} \sum_{k} \mathbf{M}^{(ij)}_{k, \pi^*(k)},
$$

so that a threshold producing far fewer groups in one configuration cannot reach a
high score by matching only its best groups. A threshold is eligible only if
$n_i \ge 10$ and $n_j \ge 10$ for every pair; otherwise a single well-matched group
would decide the result. The threshold of an approach is the one with the highest mean
score over its 10 pairs,

$$
\hat{\theta} = \arg\max_{\theta} \frac{1}{|\mathcal{P}|} \sum_{(i, j) \in \mathcal{P}} \mathrm{score}_{ij}(\theta),
$$

where $\mathcal{P}$ is the set of compared pairs of snapshot counts.

#### Results

Mean (minimum) score over the 10 pairs, per threshold:

| $\theta$ | cumulative: mean score (min) | overlapping: mean score (min) |
|---|---|---|
| 0.10 | 0.84 (0.78) | 0.78 (0.68) |
| 0.15 | 0.84 (0.78) | 0.78 (0.68) |
| 0.20 | 0.84 (0.78) | 0.80 (0.71) |
| 0.25 | 0.84 (0.78) | 0.81 (0.69) |
| 0.30 | 0.83 (0.72) | 0.80 (0.71) |
| 0.35 | 0.86 (0.79) | 0.79 (0.69) |
| 0.40 | 0.84 (0.75) | 0.82 (0.70) |
| 0.45 | 0.83 (0.71) | 0.81 (0.73) |
| 0.50 | 0.84 (0.75) | 0.79 (0.69) |
| 0.55 | 0.82 (0.73) | 0.79 (0.70) |
| 0.60 | 0.82 (0.75) | 0.77 (0.62) |
| 0.65 | 0.80 (0.69) | 0.70 (0.55) |
| 0.70 | 0.80 (0.70) | 0.67 (0.50) |
| 0.75 | 0.81 (0.73) | – (not eligible) |
| 0.80 | 0.74 (0.57) | – (not eligible) |
| 0.85 | 0.76 (0.61) | – (not eligible) |
| 0.90 | 0.74 (0.60) | – (not eligible) |

For overlapping windows $\theta \ge 0.75$ is not eligible (fewer than 10 compared groups
in at least one pair).

The highest mean score is reached at $\theta = 0.35$ for the cumulative approach (0.86,
minimum 0.79) and at $\theta = 0.40$ for overlapping windows (0.82, minimum 0.70; 0.81 at
$\theta = 0.45$ with minimum 0.73). The maximum is flat: the mean score stays within
0.82–0.86 for $\theta \in [0.10, 0.60]$ (cumulative) and within 0.78–0.82 for
$\theta \in [0.10, 0.55]$ (overlapping), so $\hat\theta$ is a representative value of a
stable range, not a sharp optimum. The best threshold is only 0.01–0.03 above
its neighbours, too little to prefer one threshold over another.

Cumulative, $\theta = 0.35$:

| $(k_i, k_j)$ | $S_i$ / $S_j$ | common time points | groups $S_i$ / $S_j$ | compared groups $n_i$ / $n_j$ | median $\mathcal{J}_{ij}$ | score |
|---|---|---|---|---|---|---|
| (1, 2) | 10 / 20 | 10 | 21 / 35 | 17 / 17 | 1.00 | 0.94 |
| (1, 3) | 10 / 29 | 10 | 21 / 42 | 17 / 19 | 1.00 | 0.84 |
| (1, 4) | 10 / 39 | 10 | 21 / 49 | 17 / 17 | 1.00 | 0.88 |
| (1, 5) | 10 / 48 | 10 | 21 / 59 | 17 / 15 | 1.00 | 0.82 |
| (2, 3) | 20 / 29 | 10 | 35 / 42 | 17 / 19 | 1.00 | 0.84 |
| (2, 4) | 20 / 39 | 20 | 35 / 49 | 23 / 22 | 1.00 | 0.87 |
| (2, 5) | 20 / 48 | 10 | 35 / 59 | 17 / 15 | 1.00 | 0.88 |
| (3, 4) | 29 / 39 | 10 | 42 / 49 | 19 / 17 | 1.00 | 0.84 |
| (3, 5) | 29 / 48 | 10 | 42 / 59 | 19 / 15 | 1.00 | 0.79 |
| (4, 5) | 39 / 48 | 10 | 49 / 59 | 17 / 15 | 1.00 | 0.88 |

Overlapping windows, $\theta = 0.40$:

| $(k_i, k_j)$ | $S_i$ / $S_j$ | common time points | groups $S_i$ / $S_j$ | compared groups $n_i$ / $n_j$ | median $\mathcal{J}_{ij}$ | score |
|---|---|---|---|---|---|---|
| (1, 2) | 10 / 20 | 10 | 64 / 85 | 25 / 29 | 1.00 | 0.83 |
| (1, 3) | 10 / 29 | 10 | 64 / 100 | 25 / 27 | 1.00 | 0.81 |
| (1, 4) | 10 / 39 | 10 | 64 / 109 | 25 / 30 | 1.00 | 0.70 |
| (1, 5) | 10 / 48 | 10 | 64 / 123 | 25 / 26 | 1.00 | 0.85 |
| (2, 3) | 20 / 29 | 10 | 85 / 100 | 29 / 27 | 1.00 | 0.86 |
| (2, 4) | 20 / 39 | 20 | 85 / 109 | 54 / 47 | 1.00 | 0.83 |
| (2, 5) | 20 / 48 | 10 | 85 / 123 | 29 / 26 | 1.00 | 0.79 |
| (3, 4) | 29 / 39 | 10 | 100 / 109 | 27 / 30 | 1.00 | 0.83 |
| (3, 5) | 29 / 48 | 10 | 100 / 123 | 27 / 26 | 1.00 | 0.85 |
| (4, 5) | 39 / 48 | 10 | 109 / 123 | 30 / 26 | 1.00 | 0.83 |

### One-to-one correspondence

**Linear sum assignment.** The groups are matched one to one by the linear sum assignment
on $\mathbf{M}^{(ij)}$ (Hungarian algorithm); with $I_{ij}$ the number of assigned pairs
with $\bar J \ge 0.99$, the share of identical pairs measures whether matched groups have
the same members. The assignment always returns a one-to-one matching, however, so it
cannot show whether the correspondence *is* one-to-one.

**Maximum alignment.** Every group chooses its best partner without this constraint,

$$
b_i(k) = \arg\max_l \mathbf{M}^{(ij)}_{kl}, \qquad b_j(l) = \arg\max_k \mathbf{M}^{(ij)}_{kl}.
$$

$(k, l)$ is a mutual best match if $l$ is the only best partner of $k$ and $k$ the only
best partner of $l$, with $\mathbf{M}^{(ij)}_{kl} > 0$. Every group is classified as

- **1:1:** part of a mutual best match;
- **split / merge:** several best partners with the same $\bar J$ (a tie), or a best
  partner that chooses another group, i.e. the group corresponds to several groups of
  the other configuration;
- **no partner:** its row (column) of $\mathbf{M}^{(ij)}$ is zero.

Since $\bar J$ is computed where both groups exist, a group that the other configuration
cuts into consecutive pieces has $\bar J = 1$ with every piece; such groups are split /
merge, not 1:1.

**Shares.** For the configuration with fewer compared groups ($\min(n_i, n_j)$) and the
one with more ($\max(n_i, n_j)$),

$$
p_{ij} = \frac{|\{\text{groups of the class}\}|}{\min(n_i, n_j)} \;\text{ or }\; \frac{|\{\text{groups of the class}\}|}{\max(n_i, n_j)}, \qquad
\bar p = \frac{1}{|\mathcal P|} \sum_{(i,j) \in \mathcal P} p_{ij},
$$

and analogously $I_{ij} / \min(n_i, n_j)$ and $I_{ij} / \max(n_i, n_j)$ for the
assignment. At $\theta^*$ all groups present at a common time point are compared, at
$\hat\theta$ the groups present at two or more common time points.

#### Results

Configuration with fewer compared groups, mean (minimum–maximum) over the 10 pairs:

| approach | threshold | Hungarian: identical pairs | 1:1 (mutual best match) | split / merge | no partner |
|---|---|---|---|---|---|
| cumulative | $\theta^*$ | 93 % (85–100 %) | 58 % (49–76 %) | 42 % (24–51 %) | 0 % |
| overlap | $\theta^*$ | 96 % (88–100 %) | 66 % (57–79 %) | 34 % (21–43 %) | 0 % |
| cumulative | $\hat\theta = 0.35$ | 95 % (88–100 %) | 80 % (71–93 %) | 17 % (6–29 %) | 3 % (0–12 %) |
| overlap | $\hat\theta = 0.40$ | 91 % (84–96 %) | 68 % (48–81 %) | 25 % (15–40 %) | 7 % (2–12 %) |

Configuration with more compared groups:

| approach | threshold | Hungarian: identical pairs | 1:1 (mutual best match) | split / merge | no partner |
|---|---|---|---|---|---|
| cumulative | $\theta^*$ | 72 % (55–92 %) | 46 % (29–72 %) | 54 % (28–71 %) | 0 % |
| overlap | $\theta^*$ | 76 % (59–88 %) | 53 % (34–71 %) | 47 % (29–66 %) | 0 % |
| cumulative | $\hat\theta = 0.35$ | 86 % (79–94 %) | 73 % (63–88 %) | 22 % (12–37 %) | 6 % (0–13 %) |
| overlap | $\hat\theta = 0.40$ | 82 % (70–86 %) | 61 % (40–70 %) | 31 % (17–50 %) | 8 % (3–13 %) |

Summed over the 10 pairs:

| approach | threshold | Hungarian pairs (identical) | mutual best matches | split / merge (smaller / larger configuration) | no partner (smaller / larger) |
|---|---|---|---|---|---|
| cumulative | $\theta^*$ | 411 (380) | 237 | 174 / 311 | 0 / 0 |
| overlap | $\theta^*$ | 725 (693) | 476 | 249 / 457 | 0 / 0 |
| cumulative | $\hat\theta$ | 167 (158) | 133 | 29 / 40 | 5 / 11 |
| overlap | $\hat\theta$ | 279 (255) | 190 | 70 / 97 | 19 / 24 |

- **Matched groups have the same members.** 91–96 % of the assigned pairs are
  identical where both groups exist; this follows from the identical snapshot graphs
  at the common time points and is not evidence of a one-to-one correspondence.
- **Every mutual best match is identical and is a pair of the assignment.** The two
  methods agree wherever the best partner is unambiguous.
- **The assignment overstates the one-to-one correspondence.** The share of identical
  assigned pairs exceeds the share of 1:1 groups by 15–35 percentage points (cumulative
  93 % vs 58 % at $\theta^*$, 95 % vs 80 % at $\hat\theta$; overlapping 96 % vs 66 % and
  91 % vs 68 %): these groups are paired with one of several identical partners.
- **The correspondence is one-to-one for 58–80 % of the groups** of the smaller
  configuration (46–73 % of the larger). Almost all others are split / merge: they are
  identical to several groups of the other configuration, i.e. the same members are
  cut into different pieces in time. Groups without any partner are rare (0–7 %).
- **One threshold for all $S$ is closer to one-to-one** (cumulative 80 %, overlapping
  68 %) than the equal-count thresholds $\theta^*$ (58 %, 66 %), where the configuration
  with $S = 10$ contains many groups observed at a single time point.

### Analysis

- **The members of matched groups are the same by construction.** The snapshot graph
  at a common time point does not depend on $S$, so the same communities are detected
  there and $\bar J$ is either 1 or 0. The median matched Jaccard of 1.00 and the
  85–100 % identical matched groups at $\theta^*$ (cumulative and overlapping) confirm
  this; they do not depend on the threshold.
- **What the number of snapshots changes is how communities are linked over time.**
  All disagreement comes from groups without a counterpart (unmatched, or matched with
  $\bar J = 0$) and from groups that correspond to several groups of the other
  configuration.
- **The correspondence is one-to-one for 58–80 % of the groups** of the configuration
  with fewer compared groups (46–73 % of the one with more). Most others are split or
  merged differently in time; on average 0–8 % have no partner.
- **Score below 1 reflects groups without a counterpart.** With $\bar J \in \{0, 1\}$
  the score is the share of groups of the larger set that have an identical
  counterpart (0.70–0.94 at $\hat\theta$).
- **No calibration of the threshold per snapshot count is needed.** With one $\theta$
  for all $S$ the mean score is 0.86 (cumulative, $\theta = 0.35$) and 0.82
  (overlapping, $\theta = 0.40$), and it is stable over $0.10$–$0.60$ (cumulative,
  0.82–0.86) and $0.10$–$0.55$ (overlapping, 0.78–0.82). The one-to-one share is higher
  than at the equal-count thresholds $\theta^*$ (cumulative 80 % vs 58 %, overlapping
  68 % vs 66 %), which force the configuration with $S = 10$ to a high threshold and
  many single-snapshot groups. Equal group counts are therefore not required for
  comparable groups; the number of groups at a fixed $\theta$ still grows with $S$
  through short-lived groups between the common time points.
- **Caveats.** Groups that exist only between common time points cannot be compared
  (up to 45 of 112 groups at $\theta^*$). $\bar J$ ignores how long two groups coexist,
  so lifetimes enter only through the split / merge and no-partner shares. For
  overlapping windows the overlap of consecutive windows grows with $S$, so the effect
  of the temporal resolution cannot be separated from the effect of the overlap. The
  interval approach can only be observed at one resolution, since its window width
  equals its stride. All results use one window width ($W = 50$ days) and one Louvain
  run per snapshot.
- **Conclusion.** With a fixed window width the hypothesis is partly supported for the
  cumulative and the overlapping construction. The first criterion holds by
  construction: groups matched at the common time points have the same members. The
  second holds for 58–80 % of the groups: they correspond one to one, while the others
  are cut into different pieces in time. The number of snapshots therefore affects the
  lifetimes of the dynamic groups, not their members.

## Motivation for the fixed window width

In a first version of the analysis the number of snapshots also set the window width:
the windows were stretched to cover the whole period,

$$
W_{\text{interval}}(S) = \frac{T}{S}, \qquad
W_{\text{overlap}}(S) = \frac{T}{1 + (S - 1)(1 - f)} = \frac{2T}{S + 1} \quad (f = 0.5),
$$

so that at a common time point two configurations detected communities on different
graphs (e.g. $W \approx 96$ days for $S = 10$ and $W \approx 26$ days for $S = 40$ with
overlapping windows), and window ends of overlapping windows had to be paired with the
nearest window end of the other configuration. The comparison then mixed the temporal
resolution with the aggregation scale: only the cumulative approach, whose window
$[0, t]$ does not depend on $S$, produced matching groups, while the matched groups of
the interval and the overlapping approach had different members. The window width was
therefore fixed, so that the number of snapshots changes the temporal resolution only.

## Robustness to the community detection algorithm

### Question

Do the snapshot communities depend on the community detection algorithm? The
pipeline uses Louvain; here it is compared with greedy modularity maximisation
(Clauset–Newman–Moore). This analysis is independent of the matching threshold: no
dynamic groups are built, only the static communities of each snapshot are compared.

### Method

The snapshots are the fixed 50-day windows defined above with stride
$\Delta = 25$ days ($k = 2$, $S = 20$) for the cumulative and overlapping approaches and
$\Delta = 50$ days ($k = 1$, $S = 10$) for the interval approach, whose stride equals its
width. For every snapshot $t \in T_{S}$ the weighted snapshot graph $G_t$ is partitioned by both
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
$\{\mathbf{A}^{(t)}_{k, \pi^*_t(k)}\}$. These lists are pooled over the snapshots of
each approach. A high correspondence (values close to 1, a 1:1 mapping) means the
approach is robust to the choice of algorithm. As before, the number of *partners* of
a community $C_k$ is the number of communities $C'_l$ with $\mathbf{A}^{(t)}_{kl} > 0$.

### Results

| approach | snapshots | communities Louvain / greedy | matched pairs | mean $J$ | median $J$ | $J \ge 0.5$ | identical ($J \ge 0.99$) | partners per community | mean $J$ per snapshot (min–max) | mean $J$, size ≥ 20 / < 20 |
|---|---|---|---|---|---|---|---|---|---|---|
| cumulative | 20 | 263 / 265 | 254 | 0.71 | 0.80 | 76 % | 13 % | 2.61 | 0.55–0.85 | 0.69 / 0.85 |
| interval | 10 | 146 / 144 | 139 | 0.72 | 0.78 | 79 % | 16 % | 2.53 | 0.61–0.82 | 0.71 / 0.80 |
| overlap | 20 | 286 / 287 | 276 | 0.74 | 0.81 | 81 % | 16 % | 2.54 | 0.61–0.87 | 0.72 / 0.85 |

### Analysis

- **Both algorithms find almost the same number of communities** (263 vs 265, 146 vs
  144, 286 vs 287), and nearly every community has a matched counterpart.
- **The correspondence is clear but not exact.** The median matched Jaccard is
  0.78–0.81 and 76–81 % of the matched pairs have $J \ge 0.5$, i.e. the two communities
  share the majority of their members, but only 13–16 % are identical. Each Louvain community shares members with 2.5–2.6 greedy communities on
  average: the core of a community is found by both algorithms, while members at the
  boundary are assigned differently.
- **Large communities differ more.** Communities with at least 20 members reach a mean
  matched Jaccard of 0.69–0.72, smaller ones 0.80–0.85. The algorithms agree on small,
  well-separated communities and draw the boundaries of large communities differently.
- **The three approaches are affected equally.** The mean matched Jaccard is 0.71
  (cumulative), 0.72 (interval) and 0.74 (overlapping), with similar ranges over time
  (0.55–0.87 per snapshot). The choice of algorithm does not favour one snapshot
  construction over another.
- **Caveats.** Louvain is a randomised algorithm and is run once per snapshot; how much
  two Louvain runs differ from each other was not measured, so the values have no
  reference level. The comparison uses one snapshot count per approach and the default
  resolution.
- **Conclusion.** Most communities (76–81 %) have a clear counterpart under the other
  algorithm, so the identified community structure is broadly robust to the algorithm.
  The boundaries of large communities, however, depend on the algorithm (mean matched
  Jaccard 0.69–0.72 for communities with at least 20 members), so results that rely on
  exact memberships should be read with this variability in mind.
