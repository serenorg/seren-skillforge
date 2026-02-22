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
```

## CLI Quickstart

```bash
python -m skillforge --help
skillforge --help
```
