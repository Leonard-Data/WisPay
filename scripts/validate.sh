#!/usr/bin/env bash
# Pre-validation gate for the WisPay app.
# Runs: ruff lint, ruff format check, mypy, pytest. Exits non-zero on any failure.
#
# Usage:
#   bash scripts/validate.sh          # check only
#   bash scripts/validate.sh --fix    # apply ruff fixes, then re-check
#
# Driver selection (BE-1):
# - WS_DB_URL is honored when set. The default below pins tests to a local
#   SQLite file so the gate runs without Azure credentials.
# - Set WS_DRIVER=azure (and unexport WS_DB_URL) to validate the Azure SQL
#   connection-string assembly path; the Azure code paths still need a real
#   server to fully exercise (the gate covers connection-string assembly and
#   parameter builders, not live round trips).
set -euo pipefail

cd "$(dirname "$0")/.."

# Prefer `uv run` so tools resolve from the project venv; fall back to the
# project-local `.venv` interpreter when `uv` is unavailable (CI containers
# and minimal dev images). PATH is the last-resort fallback.
if command -v uv >/dev/null 2>&1; then
  PREFIX=(uv run)
elif [ -x ".venv/Scripts/python.exe" ]; then
  PREFIX=(.venv/Scripts/python.exe -m)
elif [ -x ".venv/bin/python" ]; then
  PREFIX=(.venv/bin/python -m)
else
  PREFIX=()
fi

FIX=0
[[ "${1:-}" == "--fix" ]] && FIX=1

# Default the dev driver to a per-run SQLite file unless the caller already
# picked one (CI may set WS_DB_URL to a shared ephemeral DB).
: "${WS_DB_URL:=sqlite:///./.wispay-validate.db}"
export WS_DB_URL

cleanup_db() {
  local dbfile
  case "$WS_DB_URL" in
    sqlite:///*)
      dbfile="${WS_DB_URL#sqlite:///}"
      rm -f "$dbfile" "${dbfile}-wal" "${dbfile}-shm"
      ;;
  esac
}
trap cleanup_db EXIT

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
