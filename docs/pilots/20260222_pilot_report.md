# SkillForge Pilot Report (2026-02-22)

## Scope

Pilot migration of three representative skills into SkillSpec:

1. `examples/migrations/browser-automation/skill.spec.yaml`
2. `examples/migrations/polymarket-trader/skill.spec.yaml`
3. `examples/migrations/job-seeker/skill.spec.yaml`

Validation flow executed for each:

- `skillforge validate`
- `skillforge generate`
- `skillforge test --mode smoke`

## Baseline vs Pilot Framing

Baseline (from current manual process stated by project owner):

- Typical skill shipping time: `1-2 hours` per skill
- Integration testing coverage: low (only a small subset of skills tested)

Pilot measurement here focuses on **toolchain time-to-green** for fixed specs, not full human authoring time.

## Measured Results

Command timing method: `/usr/bin/time -p` on local dev machine (Python 3.11 virtualenv, warm dependency cache).

| Skill | Validate (s) | Generate (s) | Smoke (s) | Time-to-Green (s) | Retries to Green |
| --- | ---: | ---: | ---: | ---: | ---: |
| browser-automation | 1.03 | 1.16 | 1.04 | 3.23 | 0 |
| polymarket-trader | 1.01 | 1.07 | 1.01 | 3.09 | 0 |
| job-seeker | 1.04 | 1.05 | 1.01 | 3.10 | 0 |

Aggregate:

- Mean time-to-green: `3.14s`
- Median time-to-green: `3.10s`
- Quick + smoke pass rate: `3/3` skills

## Quality Checks

- All three migration specs pass `quick` and `smoke` harness checks.
- Risk-policy regression test added: removing `policies` from trader spec fails validation (`missing_policies`).

## Recommendation

Pass pilot gate and proceed.

Rationale:

- Deterministic local pass/fail loop is now seconds, not minutes.
- Migration specs are expressive enough for representative automation, trading, and productivity workflows.
- CI now has drift gates (`generate --check`) to prevent silent regressions.

