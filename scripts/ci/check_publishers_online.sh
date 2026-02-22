#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON:-python3.11}"
GATEWAY_URL="${SEREN_GATEWAY_URL:-https://api.serendb.com}"
API_KEY_ENV="${SEREN_API_KEY_ENV:-SEREN_API_KEY}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python executable not found: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ -z "${!API_KEY_ENV:-}" ]]; then
  echo "Missing required API key env var: ${API_KEY_ENV}" >&2
  exit 1
fi

SPECS=()
while IFS= read -r spec; do
  SPECS+=("${spec}")
done < <(find "${ROOT_DIR}/examples" -type f -name "skill.spec.yaml" | sort)

if [[ "${#SPECS[@]}" -eq 0 ]]; then
  echo "No example specs found under ${ROOT_DIR}/examples" >&2
  exit 1
fi

echo "Online publisher validation for ${#SPECS[@]} specs via ${GATEWAY_URL}"
for spec in "${SPECS[@]}"; do
  echo "  -> ${spec#${ROOT_DIR}/}"
  "${PYTHON_BIN}" -m skillforge resolve-publishers \
    --spec "${spec}" \
    --check \
    --gateway-url "${GATEWAY_URL}" \
    --api-key-env "${API_KEY_ENV}" \
    --require-api-key >/dev/null

  "${PYTHON_BIN}" -m skillforge validate \
    --spec "${spec}" \
    --online-publishers \
    --gateway-url "${GATEWAY_URL}" \
    --api-key-env "${API_KEY_ENV}" \
    --require-api-key >/dev/null
done

echo "Online publisher checks passed."
