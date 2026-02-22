# 0002 - Publish Workflow

## Purpose

Define how SkillForge syncs generated artifacts into a local `seren-skills` clone with safe defaults.

## Scope

The `publish` command handles:

- copying generated artifacts from a source directory into `target/<org>/<name>`
- preventing accidental overwrite unless `--force` is set
- optional pull request creation through `gh`

## Default Safety Rules

- Source must look like generated output (`SKILL.md`, `scripts/agent.py`, `tests/test_smoke.py`).
- Target must be a local git clone (contains `.git`).
- Existing destination directories are rejected unless `--force` is explicitly provided.
- No network calls are required unless `--create-pr` is enabled.

## PR Creation Flow

When `--create-pr` is enabled:

1. verify `gh` is available
2. create or checkout a publish branch
3. stage `org/name` changes
4. commit staged changes
5. open PR with `gh pr create`

Failures from git/gh commands are surfaced with actionable error text.

### Conventional Format Guardrail

The generated commit message and PR title must satisfy `seren-skills/.github/workflows/pr-title.yml`.

- Allowed conventional types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`
- Default type in SkillForge publish flow: `feat`
- Optional scope can be supplied with `--scope`

Defaults:

- Commit: `<type>(<scope>)?: publish skill <org>/<name> via SkillForge`
- PR title: `<type>(<scope>)?: publish skill <org>/<name>`

Examples:

- `feat: publish skill curve/gauge-reward-screener`
- `docs(curve): publish skill curve/gauge-reward-screener`

## Non-Goals

- remote repository setup
- branch protection enforcement
- reviewer assignment automation
