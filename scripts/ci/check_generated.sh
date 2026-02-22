#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON:-python3.11}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python executable not found: ${PYTHON_BIN}" >&2
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

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

echo "Checking generated output determinism for ${#SPECS[@]} example specs..."
for spec in "${SPECS[@]}"; do
  rel_spec="${spec#${ROOT_DIR}/examples/}"
  example_name="${rel_spec%/skill.spec.yaml}"
  out_dir="${TMP_DIR}/${example_name}"

  "${PYTHON_BIN}" -m skillforge generate --spec "${spec}" --out "${out_dir}" >/dev/null
  "${PYTHON_BIN}" -m skillforge generate --spec "${spec}" --out "${out_dir}" --check >/dev/null
done

echo "Verifying stale output detection..."
stale_out="${TMP_DIR}/stale-check"
first_spec="${SPECS[0]}"
"${PYTHON_BIN}" -m skillforge generate --spec "${first_spec}" --out "${stale_out}" >/dev/null
echo "# stale check" >"${stale_out}/SKILL.md"

if "${PYTHON_BIN}" -m skillforge generate --spec "${first_spec}" --out "${stale_out}" --check >/dev/null 2>&1; then
  echo "Expected stale output check to fail, but it passed." >&2
  exit 1
fi

echo "Generation drift checks passed."
