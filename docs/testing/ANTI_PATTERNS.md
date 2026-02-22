# SkillForge Test Anti-Patterns

## 1. Testing Implementation Details

Bad:

- asserting private helper call order
- asserting internal data shape that is not user-visible

Good:

- asserting user-facing outputs, errors, and generated files

## 2. Network-Coupled Default Tests

Bad:

- tests that call real APIs in normal `pytest` runs

Good:

- fixture-driven offline tests in `quick` and `smoke`

## 3. Overloaded Tests

Bad:

- one test that validates five unrelated behaviors

Good:

- one behavior per test

## 4. Snapshot Noise

Bad:

- golden files with unstable timestamps/random IDs

Good:

- deterministic sorted output and normalized fields

## 5. Missing Negative Cases

Bad:

- only happy-path parser/validator tests

Good:

- explicit failing fixtures with expected diagnostics

