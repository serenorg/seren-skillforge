# SkillForge Baseline and Targets

## Source of Baseline

Baseline values are from:

- pilot migration set: `examples/migrations`
- collector output: `scripts/metrics/collect_metrics.py --input-dir examples/migrations`
- snapshot date: 2026-02-22

## Baseline Snapshot

| Metric | Baseline |
| --- | ---: |
| `summary.skill_count` | 3 |
| `summary.density.authored_total_loc` | 190 |
| `summary.density.generated_total_loc` | 561 |
| `summary.density.generated_authored_loc_ratio` | 2.9526 |
| `summary.density.mean_manual_files_touched` | 1.0 |
| `summary.integration.quick_pass_rate` | 1.0 |
| `summary.integration.smoke_pass_rate` | 1.0 |
| `summary.integration.mean_retries_to_green` | 0.0 |

## Targets

Targets are set for ongoing skill publishing quality, not one-time pilot outcomes.

| Metric | Target |
| --- | --- |
| `generated_authored_loc_ratio` | `>= 2.5` |
| `mean_manual_files_touched` | `<= 2.0` |
| `quick_pass_rate` | `>= 0.95` |
| `smoke_pass_rate` | `>= 0.90` |
| `mean_retries_to_green` | `<= 1.0` |

## Review Cadence

- Recompute metrics on every release candidate.
- Track trend deltas week over week.
- Treat sustained regressions (2+ runs below target) as release blockers.

