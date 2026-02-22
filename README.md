# SkillForge

SkillForge is a generator-driven toolchain for creating and publishing high-volume Seren skills from a typed `skill.spec.yaml`.

## Current Status

- Stage: bootstrap (`SF-01`)
- Design proposal: `docs/20260221_SkillForge_Proposal.md`
- Implementation plan: `docs/plans/20260222_SkillForge_Implementation_Plan.md`

## Start Here

Read these before making code changes:

1. `docs/architecture/0001_skillforge_context.md`
2. `docs/testing/TEST_STRATEGY.md`
3. `docs/testing/ANTI_PATTERNS.md`
4. `docs/metrics/METRIC_DEFINITIONS.md`

## Prerequisites

- Python 3.11+

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Development Commands

```bash
make format
make lint
make test
make check-generated
```

## CLI Quickstart

```bash
python -m skillforge --help
skillforge --help
python -m skillforge validate --spec examples/minimal/skill.spec.yaml
python -m skillforge validate --spec examples/polymarket-trader/skill.spec.yaml --online-publishers --require-api-key
python -m skillforge resolve-publishers --spec examples/polymarket-trader/skill.spec.yaml --check --require-api-key
python -m skillforge resolve-publishers --spec examples/polymarket-trader/skill.spec.yaml --write --require-api-key
python -m skillforge generate --spec examples/minimal/skill.spec.yaml --out /tmp/skillforge-out
python -m skillforge generate --spec examples/polymarket-trader/skill.spec.yaml --out /tmp/skillforge-out --resolve-publishers --require-api-key
python -m skillforge test --mode quick --spec examples/minimal/skill.spec.yaml
```

## Publisher Guardrails

- `validate` now blocks guessed RPC slugs like `rpc-ethereum` unless explicitly allowlisted via `--allow-guessed-publisher-slug`.
- `resolve-publishers` resolves connector publisher slugs from live gateway catalog (`GET /publishers`) and can rewrite stale slugs in `skill.spec.yaml`.
- CI runs online checks for all example specs and fails if publishers are unknown/inactive or unresolved.
