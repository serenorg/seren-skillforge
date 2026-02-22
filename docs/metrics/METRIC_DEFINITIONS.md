# SkillForge Metric Definitions

## Primary Outcomes

## `time_to_green_minutes`

- Definition: time from `skillforge init` to passing `validate + generate + quick + smoke`.
- Target: <= 20 minutes median in v1, with 15-minute p50 for archetype-aligned skills.

## `retries_to_green`

- Definition: number of correction cycles before first full green run.
- Goal: downward trend across pilots.

## LLM Density Metrics

## `density.generated_to_authored_loc`

- Definition: generated LOC divided by manually authored LOC (`skill.spec.yaml` + optional custom hooks).
- Target: >= 8.

## `density.manual_files_touched`

- Definition: manually edited files for a standard new skill.
- Target: <= 2.

## Integration Quality Metrics

## `integration.quick_pass_rate`

- Definition: pass rate for quick checks in CI.
- Target: >= 95%.

## `integration.smoke_pass_rate`

- Definition: pass rate for smoke checks in CI.
- Target: >= 90%.

## `integration.skill_coverage`

- Definition: percent of SkillForge-authored skills with generated smoke tests.
- Target: 100%.

