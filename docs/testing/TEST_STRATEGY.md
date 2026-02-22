# SkillForge Test Strategy

## Goals

- Catch spec and generation errors early.
- Keep local and CI runs deterministic.
- Make integration quality the default for generated skills.

## Test Tiers

## Quick

- Scope: parser/schema/semantic validation.
- External calls: none.
- Runtime target: under 60 seconds.
- Runs on every PR.

## Smoke

- Scope: generated workflow execution through fixture-backed connectors.
- External calls: none.
- Runtime target: under 3 minutes.
- Runs on every PR.

## Live (optional)

- Scope: selected real integrations (sandbox or approved environments).
- External calls: allowed.
- Runs on schedule or manual trigger.

## Coverage Expectations

- Positive and negative tests for each validation rule.
- Golden output tests for generators.
- Regression test for every production defect.

## Determinism Rules

- Freeze fixture inputs.
- Avoid clock/random/network dependence in default tests.
- Use stable ordering in generated files.

