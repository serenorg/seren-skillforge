# SkillForge Implementation Plan (Detailed)

- Date: 2026-02-22
- Status: Execution Plan
- Primary design input: `docs/20260221_SkillForge_Proposal.md`
- Audience: Engineers with strong coding ability and low domain/tool context

## 1. Why This Exists

This plan converts the design proposal into executable, bite-sized tasks.

Non-negotiable outcomes:
- Ship standard skills in 15 minutes (p50 target, after v1 stabilization)
- Raise integration test coverage from ad hoc to default
- Keep one source of truth (`skill.spec.yaml`) and generate downstream artifacts

This document is intentionally operational. It tells you exactly what to build, where to build it, and how to test it.

## 2. Read This First (Required Context)

Before writing code, read these in order:

1. `docs/20260221_SkillForge_Proposal.md`
2. `README.md` (create in SF-01)
3. External context:
- `https://github.com/serenorg/seren-skills`
- `https://github.com/serenorg/seren-skills/blob/main/README.md`
- `https://github.com/serenorg/seren-skills/blob/main/CONTRIBUTING.md`

## 3. Guardrails (Must Follow)

### 3.1 DRY
- Never duplicate validation or generation logic in multiple commands.
- Put shared logic in dedicated modules (`parser`, `validator`, `codegen`, `testing`).

### 3.2 YAGNI
- Build only Python runtime generation in v1.
- Do not add TypeScript/Rust backends in this phase.
- Do not build a GUI.

### 3.3 TDD
- Every new behavior starts with a failing test.
- Red -> Green -> Refactor for each behavior slice.
- Keep tests deterministic and offline by default.

### 3.4 Frequent Commits
- Commit every small, coherent change.
- Ideal cadence: 2-4 commits per task.
- Do not batch multiple SF tasks into one commit.

## 4. How We Define Success

### 4.1 LLM Density Metrics

1. `density.generated_to_authored_loc`
- Formula: generated LOC / authored LOC (`skill.spec.yaml` + custom hooks)
- Target (archetype-aligned skills): `>= 8x`

2. `density.manual_files_touched`
- Manual files required for a new standard skill
- Target: `<= 2` (`skill.spec.yaml` and optional fixture override)

3. `density.retries_to_green`
- Number of regeneration/test retries before passing quick+smoke
- Target: downward trend across pilot tasks

### 4.2 Integration Testing Metrics

1. `integration.quick_pass_rate`
- Generated quick checks pass in CI
- Target: `>= 95%`

2. `integration.smoke_pass_rate`
- Fixture-driven smoke tests pass in CI
- Target: `>= 90%`

3. `integration.skill_coverage`
- SkillForge-authored skills with generated smoke tests
- Target: `100%`

## 5. Target Repository Layout (End State)

```text
seren-skillforge/
├── README.md
├── pyproject.toml
├── Makefile
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml
├── skillforge/
│   ├── __init__.py
│   ├── cli.py
│   ├── models.py
│   ├── parser.py
│   ├── ir.py
│   ├── validator.py
│   ├── schema/
│   │   └── skillspec_v0.json
│   ├── commands/
│   │   ├── init.py
│   │   ├── validate.py
│   │   ├── generate.py
│   │   ├── test.py
│   │   └── publish.py
│   ├── codegen/
│   │   ├── skill_md.py
│   │   ├── runtime_python.py
│   │   ├── config_files.py
│   │   └── generated_tests.py
│   └── testing/
│       ├── harness.py
│       └── connector_mocks.py
├── archetypes/
│   ├── guide/
│   │   └── skill.spec.yaml
│   ├── api-worker/
│   │   └── skill.spec.yaml
│   ├── trader/
│   │   └── skill.spec.yaml
│   └── browser-automation/
│       └── skill.spec.yaml
├── examples/
│   ├── minimal/skill.spec.yaml
│   ├── browser-automation/skill.spec.yaml
│   └── polymarket-trader/skill.spec.yaml
├── tests/
│   ├── parser/
│   ├── validator/
│   ├── codegen/
│   ├── cli/
│   ├── integration/
│   └── golden/
├── scripts/
│   └── metrics/
│       └── collect_metrics.py
└── docs/
    ├── 20260221_SkillForge_Proposal.md
    ├── architecture/
    ├── testing/
    ├── metrics/
    └── plans/
        └── 20260222_SkillForge_Implementation_Plan.md
```

## 6. Engineering Workflow for Every Task

Use this loop for all SF tasks:

1. Write/adjust tests first (`tests/...`)
2. Run only affected tests locally
3. Implement minimum code to pass
4. Refactor without changing behavior
5. Run full test set
6. Update docs for any behavior surface change
7. Commit

Command baseline (after SF-01):

```bash
make format
make lint
make test
```

## 7. Test Design Rules (Because Bad Tests Are a Real Risk)

1. Test one behavior per test.
2. Include both positive and negative validator tests.
3. Assert user-facing outputs and errors, not internal implementation details.
4. Use fixtures for deterministic inputs.
5. Add regression tests for every production bug.
6. No live network in default test suite.
7. Golden tests must be stable and diff-friendly.

## 8. Task Backlog (Bite-Sized)

## SF-01 - Bootstrap Tooling and Project Skeleton

- Goal: Create minimal, maintainable Python foundation for SkillForge.
- Depends on: none.

Files to add/touch:
- `README.md`
- `pyproject.toml`
- `Makefile`
- `.gitignore`
- `skillforge/__init__.py`
- `skillforge/cli.py`
- `tests/smoke/test_imports.py`

Implementation notes:
- Use Python 3.12+
- Keep deps minimal: `typer`, `pydantic`, `pyyaml`, `jsonschema`, `pytest`, `ruff`
- Expose CLI entrypoint: `skillforge`

TDD checklist:
- Red: `tests/smoke/test_imports.py` ensures package import and CLI app object exists
- Green: add package/CLI skeleton
- Refactor: tidy `pyproject.toml` scripts and optional dev deps

How to test:

```bash
python -m pytest tests/smoke/test_imports.py
python -m skillforge --help
```

Commit slices:
1. `chore: bootstrap python project and tooling`
2. `test: add smoke import checks`

Done when:
- CLI runs with `--help`
- Smoke tests pass
- README has setup and command quickstart

---

## SF-02 - Add Domain Onboarding and Quality Guardrail Docs

- Goal: Remove ambiguity for engineers new to SkillForge and skills domain.
- Depends on: SF-01.

Files to add/touch:
- `docs/architecture/0001_skillforge_context.md`
- `docs/testing/TEST_STRATEGY.md`
- `docs/testing/ANTI_PATTERNS.md`
- `docs/metrics/METRIC_DEFINITIONS.md`
- `README.md`

Implementation notes:
- Explain terms: skill, archetype, connector, quick test, smoke test, live test
- Include DRY/YAGNI/TDD rules and examples

TDD checklist:
- Red: add doc lint/link check test (if lightweight) or markdown path check script
- Green: author docs
- Refactor: unify duplicated definitions

How to test:

```bash
python -m pytest tests/smoke/test_docs_links.py
```

Commit slices:
1. `docs: add architecture and testing guardrails`
2. `test: add docs link checks`

Done when:
- New engineer can explain system boundary and testing modes without oral handoff

---

## SF-03 - Define SkillSpec v0 Schema and Canonical Examples

- Goal: Lock initial language contract before parser implementation.
- Depends on: SF-01.

Files to add/touch:
- `skillforge/schema/skillspec_v0.json`
- `examples/minimal/skill.spec.yaml`
- `examples/browser-automation/skill.spec.yaml`
- `examples/polymarket-trader/skill.spec.yaml`
- `tests/schema/test_schema_examples.py`

Implementation notes:
- Enforce required sections and key types
- Explicitly disallow unknown top-level keys in v0
- Include policy section requirements for high-risk archetypes

TDD checklist:
- Red: failing tests for valid and invalid example specs
- Green: schema and example specs adjusted until tests pass
- Refactor: reduce schema duplication via `$defs`

How to test:

```bash
python -m pytest tests/schema/test_schema_examples.py
```

Commit slices:
1. `test: add schema validation tests`
2. `feat: add skillspec v0 schema and examples`

Done when:
- All examples validate
- Invalid fixtures fail with clear messages

---

## SF-04 - Implement Parser and Normalized IR

- Goal: Parse YAML into strongly typed internal representation.
- Depends on: SF-03.

Files to add/touch:
- `skillforge/models.py`
- `skillforge/parser.py`
- `skillforge/ir.py`
- `tests/parser/test_parser_success.py`
- `tests/parser/test_parser_errors.py`

Implementation notes:
- Parse YAML -> validate against schema -> map to typed models -> normalize IR
- Normalize defaults in one place (not across commands)

TDD checklist:
- Red: parse valid spec into expected IR
- Red: malformed YAML and bad schema produce clear error types
- Green: implement parser + model mapping
- Refactor: isolate normalization helpers

How to test:

```bash
python -m pytest tests/parser
```

Commit slices:
1. `test: add parser behavior coverage`
2. `feat: implement parser and normalized IR`

Done when:
- Parser outputs stable IR object for all canonical examples

---

## SF-05 - Implement Semantic Validator

- Goal: Enforce cross-field and workflow semantic rules not handled by JSON schema.
- Depends on: SF-04.

Files to add/touch:
- `skillforge/validator.py`
- `tests/validator/test_semantic_rules.py`
- `tests/validator/fixtures/*.yaml`

Implementation notes:
- Validate connector references, step ordering, missing symbols, policy completeness
- Emit actionable errors with path and fix hint

TDD checklist:
- Red: invalid references should fail with exact diagnostic
- Red: risky archetype without required policies should fail
- Green: implement semantic checks
- Refactor: error object structure shared across validator checks

How to test:

```bash
python -m pytest tests/validator
```

Commit slices:
1. `test: add semantic validator fixtures`
2. `feat: implement semantic validation`

Done when:
- Semantic diagnostics are deterministic and human-readable

---

## SF-06 - Implement CLI Foundation and `init` Command

- Goal: Scaffold new skills from archetypes in one command.
- Depends on: SF-04.

Files to add/touch:
- `skillforge/cli.py`
- `skillforge/commands/init.py`
- `archetypes/guide/skill.spec.yaml`
- `archetypes/api-worker/skill.spec.yaml`
- `archetypes/trader/skill.spec.yaml`
- `archetypes/browser-automation/skill.spec.yaml`
- `tests/cli/test_init_command.py`

Implementation notes:
- `skillforge init --archetype <name> --org <org> --name <skill-name>`
- Output folder: `<target>/<org>/<skill-name>/skill.spec.yaml`
- Fail safely on existing path unless `--force`

TDD checklist:
- Red: CLI creates expected directory and spec file from archetype
- Red: invalid archetype fails with clear help text
- Green: implement command
- Refactor: move file IO helpers to shared utility module

How to test:

```bash
python -m pytest tests/cli/test_init_command.py
python -m skillforge init --help
```

Commit slices:
1. `test: add init command CLI tests`
2. `feat: add archetypes and init command`

Done when:
- New skill skeleton can be created in <10 seconds

---

## SF-07 - Implement SKILL.md Generation

- Goal: Generate compliant and concise `SKILL.md` from `SkillSpec`.
- Depends on: SF-05.

Files to add/touch:
- `skillforge/codegen/skill_md.py`
- `skillforge/codegen/templates/skill_md.j2` (or equivalent template file)
- `tests/codegen/test_skill_md_generation.py`
- `tests/golden/skill_md/*`

Implementation notes:
- Must generate valid frontmatter for Agent Skills spec constraints
- Must include trigger-oriented description and concise body
- Keep deterministic ordering and formatting

TDD checklist:
- Red: generated markdown matches golden output
- Red: output includes required frontmatter keys
- Green: implement generator
- Refactor: remove repeated template fragments

How to test:

```bash
python -m pytest tests/codegen/test_skill_md_generation.py
```

Commit slices:
1. `test: add golden tests for SKILL.md generation`
2. `feat: implement SKILL.md generator`

Done when:
- Running generation twice produces no diff

---

## SF-08 - Implement Runtime and Config Artifact Generation

- Goal: Generate runtime skeleton and config/env templates.
- Depends on: SF-05.

Files to add/touch:
- `skillforge/codegen/runtime_python.py`
- `skillforge/codegen/config_files.py`
- `skillforge/codegen/templates/agent.py.j2`
- `skillforge/codegen/templates/env.example.j2`
- `skillforge/codegen/templates/config.example.json.j2`
- `tests/codegen/test_runtime_generation.py`
- `tests/golden/runtime/*`

Implementation notes:
- Default mode must be dry-run
- Generated runtime should call connectors through a stable abstraction
- Avoid embedding secret values in output

TDD checklist:
- Red: generated files exist and match golden fixtures
- Red: generated runtime enforces dry-run default behavior
- Green: implement generators
- Refactor: centralize file write and path logic

How to test:

```bash
python -m pytest tests/codegen/test_runtime_generation.py
```

Commit slices:
1. `test: add runtime/config generation tests`
2. `feat: generate runtime and config artifacts`

Done when:
- Minimal generated skill can run without manual code edits

---

## SF-09 - Implement Generated Test Scaffolding Output

- Goal: Generate tests and fixtures with each skill so integration validation is default.
- Depends on: SF-08.

Files to add/touch:
- `skillforge/codegen/generated_tests.py`
- `skillforge/codegen/templates/test_smoke.py.j2`
- `skillforge/codegen/templates/fixtures/*.json`
- `tests/codegen/test_generated_tests_output.py`

Implementation notes:
- Generate at least:
  - happy-path smoke test
  - connector failure test
  - policy violation test
  - dry-run no-side-effects test

TDD checklist:
- Red: generated tests fail when fixtures violate contract
- Green: implement test generation
- Refactor: reduce duplicate fixture builders

How to test:

```bash
python -m pytest tests/codegen/test_generated_tests_output.py
```

Commit slices:
1. `test: define expected generated test artifacts`
2. `feat: generate smoke test scaffolding`

Done when:
- Every generated skill includes runnable tests by default

---

## SF-10 - Implement Fixture-Driven Test Harness (`quick` and `smoke`)

- Goal: Provide consistent test execution modes for generated skills.
- Depends on: SF-09.

Files to add/touch:
- `skillforge/testing/harness.py`
- `skillforge/testing/connector_mocks.py`
- `skillforge/commands/test.py`
- `tests/integration/test_harness_modes.py`

Implementation notes:
- `quick`: parser + schema + semantic checks
- `smoke`: run generated tests against fixture connectors
- No external network required by default

TDD checklist:
- Red: quick mode fails for invalid spec
- Red: smoke mode fails for broken connector fixture
- Green: implement harness and command
- Refactor: isolate mode registry

How to test:

```bash
python -m pytest tests/integration/test_harness_modes.py
python -m skillforge test --mode quick --spec examples/minimal/skill.spec.yaml
```

Commit slices:
1. `test: add harness mode tests`
2. `feat: implement quick and smoke test harness`

Done when:
- Test command yields deterministic pass/fail locally

---

## SF-11 - Implement CLI `validate` and `generate` End-to-End

- Goal: Make core authoring workflow operational from CLI.
- Depends on: SF-07, SF-08, SF-09, SF-10.

Files to add/touch:
- `skillforge/commands/validate.py`
- `skillforge/commands/generate.py`
- `skillforge/cli.py`
- `tests/cli/test_validate_command.py`
- `tests/cli/test_generate_command.py`

Implementation notes:
- `validate` should run schema + semantic validation
- `generate` should emit all artifacts and support `--check` mode for idempotency

TDD checklist:
- Red: validate command returns non-zero on known bad specs
- Red: generate `--check` fails when outputs are stale
- Green: implement commands
- Refactor: ensure commands call shared services, not duplicate logic

How to test:

```bash
python -m pytest tests/cli/test_validate_command.py tests/cli/test_generate_command.py
python -m skillforge validate --spec examples/minimal/skill.spec.yaml
python -m skillforge generate --spec examples/minimal/skill.spec.yaml --out /tmp/skillforge-out
```

Commit slices:
1. `test: add validate and generate CLI tests`
2. `feat: implement validate and generate commands`

Done when:
- `init -> validate -> generate -> test` workflow works locally end-to-end

---

## SF-12 - Implement `publish` Command (Local Sync + Optional PR)

- Goal: Move generated skill output into target repo and optionally open a GitHub PR.
- Depends on: SF-11.

Files to add/touch:
- `skillforge/commands/publish.py`
- `tests/cli/test_publish_command.py`
- `docs/architecture/0002_publish_workflow.md`

Implementation notes:
- `publish --target <path-to-seren-skills>` copies/updates skill directory
- Optional `--create-pr` uses `gh` CLI if available
- Must be safe: no destructive overwrite unless `--force`

TDD checklist:
- Red: publish to temp git repo creates expected file tree
- Red: create-pr mode fails clearly when `gh` missing/auth absent
- Green: implement publish behavior
- Refactor: isolate git/gh shell integration behind adapter

How to test:

```bash
python -m pytest tests/cli/test_publish_command.py
python -m skillforge publish --help
```

Commit slices:
1. `test: add publish command tests`
2. `feat: implement publish workflow`

Done when:
- Generated skill can be published into a local `seren-skills` clone with one command

---

## SF-13 - Add CI Pipeline and Determinism Gates

- Goal: Prevent drift and regressions automatically.
- Depends on: SF-11.

Files to add/touch:
- `.github/workflows/ci.yml`
- `scripts/ci/check_generated.sh`
- `Makefile`
- `README.md`

Implementation notes:
- CI stages:
  - lint
  - unit/integration tests
  - golden tests
  - generation idempotency check (`generate --check`)

TDD checklist:
- Red: intentionally stale golden fixture causes CI check failure locally
- Green: implement CI scripts and workflow
- Refactor: keep CI script output concise and actionable

How to test:

```bash
make lint
make test
bash scripts/ci/check_generated.sh
```

Commit slices:
1. `test: add CI generation drift checks`
2. `ci: add workflow with lint/test/golden gates`

Done when:
- CI fails on stale generated outputs or validator regressions

---

## SF-14 - Pilot Migration: 3 Skills + Benchmark Report

- Goal: Prove speed and reliability gains using real skills.
- Depends on: SF-12 and SF-13.

Files to add/touch:
- `examples/migrations/browser-automation/skill.spec.yaml`
- `examples/migrations/polymarket-trader/skill.spec.yaml`
- `examples/migrations/job-seeker/skill.spec.yaml`
- `docs/pilots/202602xx_pilot_report.md`

Implementation notes:
- Migrate selected skills from `seren-skills` into SkillSpec form
- Run full `validate -> generate -> test` for each
- Record time-to-green and retry counts

TDD checklist:
- Red: migration spec that intentionally misses required policy should fail
- Green: complete working migration specs and generated artifacts
- Refactor: extract repeated migration helper snippets

How to test:

```bash
python -m skillforge validate --spec examples/migrations/browser-automation/skill.spec.yaml
python -m skillforge generate --spec examples/migrations/browser-automation/skill.spec.yaml --out /tmp/pilot-browser
python -m skillforge test --mode smoke --spec examples/migrations/browser-automation/skill.spec.yaml
```

Commit slices:
1. `test: add migration validation fixtures`
2. `feat: add pilot migration specs`
3. `docs: add pilot benchmark report`

Done when:
- Pilot report includes baseline vs SkillForge metrics and pass/fail recommendation

---

## SF-15 - Metrics Collection for LLM Density and Integration Success

- Goal: Instrument measurement so success is observable and repeatable.
- Depends on: SF-14.

Files to add/touch:
- `scripts/metrics/collect_metrics.py`
- `tests/integration/test_metrics_collection.py`
- `docs/metrics/BASELINE_AND_TARGETS.md`

Implementation notes:
- Capture:
  - generated/authored LOC ratio
  - retries to green
  - quick/smoke pass rates
  - manual files touched per skill
- Output machine-readable JSON for longitudinal tracking

TDD checklist:
- Red: metrics script tested against fixed fixture data
- Green: implement script
- Refactor: split collectors for density and test metrics

How to test:

```bash
python -m pytest tests/integration/test_metrics_collection.py
python scripts/metrics/collect_metrics.py --input-dir examples/migrations --out /tmp/skillforge-metrics.json
```

Commit slices:
1. `test: add metrics collection tests`
2. `feat: add density and integration metrics collector`
3. `docs: define baseline and targets`

Done when:
- Metrics can be generated in CI and compared over time

## 9. Definition of Done for the Program

The program is complete when all are true:

1. SF-01 through SF-15 are merged.
2. A new archetype-aligned skill can be shipped via:
- `init -> validate -> generate -> test -> publish`
3. Pilot shows measurable improvement:
- at least 2x faster time-to-green vs baseline
- consistent generated smoke tests for migrated skills
4. CI enforces no-generation-drift and test pass gates.

## 10. Anti-Goals Checklist (Reject PRs That Do These)

1. Adds non-essential backends (TS/Rust) before v1 proves value.
2. Adds live network requirements to default tests.
3. Introduces duplicated logic between CLI commands.
4. Adds hidden side effects without test coverage.
5. Increases manual per-skill file authoring burden.

## 11. Suggested Branch and Commit Convention

Branch naming:
- `sf-01-bootstrap`
- `sf-07-skill-md-codegen`
- `sf-14-pilot-migration`

Commit naming:
- `test(sf-05): add invalid connector reference diagnostics`
- `feat(sf-05): implement semantic validator for workflow references`
- `docs(sf-05): add validator error catalog`

## 12. Execution Order Summary

Execute in strict order:

1. SF-01
2. SF-02
3. SF-03
4. SF-04
5. SF-05
6. SF-06
7. SF-07
8. SF-08
9. SF-09
10. SF-10
11. SF-11
12. SF-12
13. SF-13
14. SF-14
15. SF-15

No parallelization until SF-01 through SF-05 stabilize interfaces.

## 13. GitHub Issue Index

- SF-01: `https://github.com/serenorg/seren-skillforge/issues/1`
- SF-02: `https://github.com/serenorg/seren-skillforge/issues/2`
- SF-03: `https://github.com/serenorg/seren-skillforge/issues/3`
- SF-04: `https://github.com/serenorg/seren-skillforge/issues/4`
- SF-05: `https://github.com/serenorg/seren-skillforge/issues/5`
- SF-06: `https://github.com/serenorg/seren-skillforge/issues/6`
- SF-07: `https://github.com/serenorg/seren-skillforge/issues/7`
- SF-08: `https://github.com/serenorg/seren-skillforge/issues/8`
- SF-09: `https://github.com/serenorg/seren-skillforge/issues/9`
- SF-10: `https://github.com/serenorg/seren-skillforge/issues/10`
- SF-11: `https://github.com/serenorg/seren-skillforge/issues/11`
- SF-12: `https://github.com/serenorg/seren-skillforge/issues/12`
- SF-13: `https://github.com/serenorg/seren-skillforge/issues/13`
- SF-14: `https://github.com/serenorg/seren-skillforge/issues/14`
- SF-15: `https://github.com/serenorg/seren-skillforge/issues/15`
