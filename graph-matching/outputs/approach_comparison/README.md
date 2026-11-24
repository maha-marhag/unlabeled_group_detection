# Comparison of cumulative, interval, and overlap approaches

## Scope and comparability

All outputs use the same 526-day dataset and 50-day windows whose ends are anchored at day 526, so every window is a full window. Cumulative uses 10 snapshots and interval 10 snapshots (one window end every 50 days); overlap uses 20 snapshots (one window end every 25 days). Raw totals therefore reflect both approach behavior and observation frequency. Normalized rates and proportions are the primary comparison measures.

Accepted lineage relations satisfy prospective stability >= 0.4 or retrospective stability >= 0.4. Every detected community at a snapshot is an observation node. Identity chains include final and intermediate/dead chains.

## Dimension A: dynamic-group and event information

| approach | snapshot_count | observation_group_count | all_identity_chain_count | final_group_count | mean_observation_group_size | split_event_count | merge_event_count | split_events_per_transition | merge_events_per_transition | mean_accepted_jaccard | mean_inherited_jaccard |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cumulative | 10 | 131 | 23 | 15 | 66.954 | 8 | 8 | 0.889 | 0.889 | 0.781 | 0.866 |
| interval | 10 | 146 | 46 | 17 | 51.322 | 22 | 20 | 2.444 | 2.222 | 0.430 | 0.554 |
| overlap | 20 | 286 | 62 | 17 | 52.206 | 40 | 39 | 2.105 | 2.053 | 0.529 | 0.655 |

![Dimension A comparison](dimension_a_comparison.png)

![Group size and Jaccard details](dimension_a_size_jaccard.png)

The full table is `dimension_a_summary.csv`. Final-group event involvement counts can count an event once for each participating final group, matching the earlier project table.

## Dimension B: complete lineage-network structure

| approach | observation_nodes | accepted_edges | weakly_connected_components | split_nodes | merge_nodes | start_snapshot_nodes | end_snapshot_nodes | max_depth_edges | mean_component_depth_edges | max_snapshot_breadth | mean_observation_size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cumulative | 131 | 124 | 9 | 8 | 8 | 14 | 15 | 9 | 8.000 | 15 | 66.954 |
| interval | 146 | 151 | 2 | 22 | 20 | 14 | 17 | 9 | 4.500 | 17 | 51.322 |
| overlap | 286 | 312 | 2 | 40 | 39 | 14 | 17 | 19 | 9.500 | 17 | 52.206 |

![Dimension B comparison](dimension_b_comparison.png)

Each approach has a complete PNG/PDF network. Node x is snapshot index and node y is a deterministic component/layer coordinate. Nodes show local internal IDs; terminal nodes append their final label or `dead`. Red edges touch a structural split or merge. Exact coordinates and attributes are in `network_nodes.csv` and `network_edges.csv`.

## Dimension C: classic versus event-based stages

| approach | method | analyzed_group_count | stage_count | mean_stages_per_group | mean_stage_length_snapshots | total_transition_duration |
| --- | --- | --- | --- | --- | --- | --- |
| cumulative | classic | 14 | 30 | 2.143 | 4.167 | 95 |
| cumulative | event_based | 14 | 26 | 1.857 | 4.654 | 95 |
| interval | classic | 13 | 51 | 3.923 | 2.608 | 82 |
| interval | event_based | 13 | 33 | 2.538 | 3.485 | 82 |
| overlap | classic | 16 | 62 | 3.875 | 3.161 | 134 |
| overlap | event_based | 16 | 44 | 2.750 | 4.045 | 134 |

| approach | groups_compared | stage_type_agreement_rate | classic_internal_boundary_count | event_internal_boundary_count | shared_boundary_count | boundary_jaccard |
| --- | --- | --- | --- | --- | --- | --- |
| cumulative | 14 | 0.811 | 16 | 12 | 8 | 0.400 |
| interval | 13 | 0.512 | 38 | 20 | 15 | 0.349 |
| overlap | 16 | 0.515 | 46 | 28 | 18 | 0.321 |

![Stage distributions](dimension_c_stage_distribution.png)

![Event-to-stage likelihoods](dimension_c_event_stage_likelihoods.png)

Stage count share and transition-duration share are separate. `count_duration_index` is their equal-weight descriptive average. Duration uses `t_end - t_start`, so shared boundary snapshots are not double-counted.

### Split/merge relationships with stages

| approach | method | event_type | event_group_involvement_count | internal_event_group_involvement_count | internal_stage_boundary_rate | post_stage_available_count | post_stage_likelihood | stage_type_change_rate | event_type_post_stage_cramers_v |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cumulative | classic | merge | 9 | 8 | 0.750 | 9 | 0.000 | 0.500 | 0.238 |
| cumulative | classic | split | 14 | 8 | 0.750 | 14 | 0.071 | 0.625 | 0.238 |
| cumulative | event_based | merge | 9 | 8 | 1.000 | 9 | 0.000 | 0.625 | 0.320 |
| cumulative | event_based | split | 14 | 8 | 1.000 | 14 | 0.071 | 0.750 | 0.320 |
| interval | classic | merge | 18 | 13 | 0.846 | 18 | 0.111 | 0.538 | 0.440 |
| interval | classic | split | 20 | 10 | 0.700 | 16 | 0.062 | 0.500 | 0.440 |
| interval | event_based | merge | 18 | 13 | 1.000 | 18 | 0.167 | 0.846 | 0.431 |
| interval | event_based | split | 20 | 10 | 1.000 | 16 | 0.000 | 0.800 | 0.431 |
| overlap | classic | merge | 24 | 19 | 0.632 | 23 | 0.130 | 0.579 | 0.132 |
| overlap | classic | split | 31 | 20 | 0.650 | 30 | 0.100 | 0.550 | 0.132 |
| overlap | event_based | merge | 24 | 19 | 1.000 | 23 | 0.130 | 0.842 | 0.310 |
| overlap | event_based | split | 31 | 20 | 1.000 | 30 | 0.067 | 0.950 | 0.310 |

`post_stage_likelihood` is the proportion of event/group involvements whose first valid transition after the event has the listed stage type. Final-snapshot cases have no post-event transition and are excluded from that denominator. `internal_stage_boundary_rate` considers only events with valid stages on both sides. Event-based segmentation uses every such internal split/merge as a boundary. The classic rate shows how often those same events coincide with independently detected size-based boundaries. Cramer's V measures association, not causation.

## Findings and recommendation

- **Cumulative gives the strongest apparent continuity but has the most historical inertia.** Its mean accepted Jaccard is 0.781, versus 0.430 for interval and 0.529 for overlap. It also has the largest mean observation group size and the fewest split/merge events per transition. Because every snapshot retains all previous edges, this stability partly reflects construction rather than only social persistence.
- **Interval is the most fragmented and volatile.** It produces 46 identity chains, has the lowest accepted and inherited Jaccard, and has the highest split and merge rates per transition. It responds to change but loses continuity at hard 50-day boundaries.
- **Overlap is the middle ground.** Its similarity and normalized split/merge rates fall between cumulative and interval. It retains the local 50-day horizon while reducing boundary discontinuity and provides 20 observation points. Its large component and 19-edge maximum depth show that it preserves long lineages without cumulative memory.
- Event-based stages are fewer and longer than classic stages for all approaches. Classic/event label agreement is 81.1% for cumulative, 51.2% for interval, and 51.5% for overlap. The lower overlap agreement means event boundaries capture different structure from size-only turning points; it is not a classifier mismatch.
- Split and merge events do not deterministically imply erosion. The erosion likelihoods are conditional descriptive rates and vary by approach/method. Event type alone has weak-to-moderate association with the following stage in the current sample, so events should remain boundary evidence rather than direct stage labels.

**Recommendation: continue with the overlap approach.** It offers the best balance of temporal continuity, sensitivity to change, and temporal resolution. Keep cumulative as a high-continuity reference and interval as a volatility reference. The robustness of the dynamic groups to the number of snapshots and to the matching threshold is examined separately in the sensitivity analysis (`outputs/sensitivity_analysis`), which uses the same fixed 50-day windows.

## Output guide

- `dimension_a_summary.csv`: group, event, size, lifespan, and similarity measures.
- `dimension_b_network_summary.csv`: lineage-network structure.
- `network_nodes.csv`: all node attributes and x/y coordinates.
- `network_edges.csv`: accepted lineage relations and structural edge types.
- `dimension_c_stage_method_summary.csv`: stage totals and lengths.
- `dimension_c_stage_type_distribution.csv`: count, duration, prevalence, and combined shares.
- `dimension_c_classic_event_comparison.csv`: boundary and label agreement.
- `dimension_c_event_stage_associations.csv`: event/group/method details.
- `dimension_c_event_stage_summary.csv`: event-to-stage likelihoods and Cramer's V.

## Interpretation rule

Use normalized rates and structural proportions when choosing an approach. Use raw totals to understand workload and graph scale. Do not rank the approaches solely by group or event totals because overlap currently has a finer temporal stride.
