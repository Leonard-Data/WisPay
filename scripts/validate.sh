#!/usr/bin/env bash
# Pre-validation gate for the WisPay app.
# Runs: ruff lint, ruff format check, mypy, pytest. Exits non-zero on any failure.
#
# Usage:
#   bash scripts/validate.sh          # check only
#   bash scripts/validate.sh --fix    # apply ruff fixes, then re-check
set -euo pipefail

cd "$(dirname "$0")/.."

# Prefer `uv run` so tools resolve from the project venv; fall back to PATH.
if command -v uv >/dev/null 2>&1; then
  PREFIX=(uv run)
else
  PREFIX=()
fi

FIX=0
[[ "${1:-}" == "--fix" ]] && FIX=1

echo "==> Ruff lint"
if [[ "$FIX" -eq 1 ]]; then
  "${PREFIX[@]}" ruff check --fix .
else
  "${PREFIX[@]}" ruff check .
fi

echo "==> Ruff format"
if [[ "$FIX" -eq 1 ]]; then
  "${PREFIX[@]}" ruff format .
else
  "${PREFIX[@]}" ruff format --check .
fi

echo "==> Mypy type check"
"${PREFIX[@]}" mypy WisPay

echo "==> Pytest"
"${PREFIX[@]}" pytest

echo "==> OK: all validation checks passed"
