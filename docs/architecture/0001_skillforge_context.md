# 0001 - SkillForge Context

## Purpose

SkillForge exists to reduce skill shipping time from hours to minutes by generating consistent skill artifacts from one typed source file: `skill.spec.yaml`.

## Problem Domain

`seren-skills` skills currently mix:

- Markdown (`SKILL.md`)
- runtime scripts (mostly Python)
- API integration details
- optional local persistence

This flexibility increases manual work and causes integration testing gaps.

## System Boundary

SkillForge is responsible for:

- parsing and validating `skill.spec.yaml`
- generating skill artifacts
- generating and running deterministic tests
- publishing generated output to a target skills repository

SkillForge is not responsible for:

- external API provider policy enforcement
- external service uptime or API correctness
- wallet custody or private key management

## Core Terms

- SkillSpec: Typed skill definition file (`skill.spec.yaml`).
- IR: Internal normalized representation built from SkillSpec.
- Archetype: Starter template for a class of skills.
- Quick tests: Schema + semantic checks, no external network.
- Smoke tests: Fixture-driven integration checks, no external network.
- Live tests: Optional real integration checks against non-production or approved environments.

## Engineering Rules

- DRY: no duplicated validator/generator logic across commands.
- YAGNI: do not add runtimes/backends not required by current milestones.
- TDD: each behavior change starts with a failing test.
- Frequent commits: small coherent commits per behavior slice.

