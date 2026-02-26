# Ledger Signing HITL Tests

Use this checklist before merge to `seren-skills`. Mark each case `PASS` or `FAIL` and attach evidence (photo/screenshot + command output).

## Preconditions

- Ledger device connected and unlocked.
- Ledger Live open and device firmware up to date.
- Target app installed and opened on device (default: Ethereum).
- SkillForge checks already pass:
  - `./.venv/bin/python -m skillforge validate --spec examples/ledger-signing/skill.spec.yaml`
  - `./.venv/bin/python -m skillforge generate --spec examples/ledger-signing/skill.spec.yaml --out /tmp/ledger-signing-runtime`
- Ledger HID dependencies installed:
  - `pip install ledgerblue hidapi`

## Cases

### HITL-01 Clear-sign transaction executes over USB/HID

- Configure runtime:
  - `cp /tmp/ledger-signing-runtime/config.example.json /tmp/ledger-signing-runtime/config.json`
  - Set:
    - `"dry_run": false`
    - `"inputs.payload_kind": "transaction"`
    - `"inputs.derivation_path": "44'/60'/0'/0/0"`
    - `"inputs.payload_hex": "<unsigned_tx_hex>"`
- Run:
  - `python /tmp/ledger-signing-runtime/scripts/agent.py --config /tmp/ledger-signing-runtime/config.json --execute`
- Expected:
  - Command returns JSON with `"status":"signed"` and a `signature` object.
  - Device shows human-readable fields before approval.
  - Reviewer can reject and rerun to validate safety behavior.

Result: `PASS | FAIL`
Evidence link/path:

### HITL-02 Message signing executes over USB/HID

- Configure runtime:
  - `cp /tmp/ledger-signing-runtime/config.example.json /tmp/ledger-signing-runtime/config.json`
  - Set:
    - `"dry_run": false`
    - `"inputs.payload_kind": "message"`
    - `"inputs.derivation_path": "44'/60'/0'/0/0"`
    - `"inputs.payload_hex": "<utf8_message_hex>"`
- Run:
  - `python /tmp/ledger-signing-runtime/scripts/agent.py --config /tmp/ledger-signing-runtime/config.json --execute`
- Expected:
  - Device prompts for message signing.
  - Command returns signature fields (`r`, `s`, `v`, `signature_hex`).

Result: `PASS | FAIL`
Evidence link/path:

### HITL-03 Execute gate refuses signing when dry-run is enabled

- Run:
  - `python /tmp/ledger-signing-runtime/scripts/agent.py --config /tmp/ledger-signing-runtime/config.example.json --execute`
- Expected:
  - Runtime exits with an error.
  - Error states that signing is blocked while `dry_run=true`.

Result: `PASS | FAIL`
Evidence link/path:

## Merge Gate

Merge only if all are true:

- `HITL-01` = PASS
- `HITL-02` = PASS
- `HITL-03` = PASS
- No unresolved safety concerns in reviewer notes
