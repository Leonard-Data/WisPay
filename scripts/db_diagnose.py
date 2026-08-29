#!/usr/bin/env python
"""Diagnose the WisPay Azure SQL path: drivers, env, schema bootstrap.

Single command for the next person debugging *"I configured the AZURE_SQL_*
keys but cannot connect / cannot see the tables"* — the exact symptom the
user reported. Reports each step and exits non-zero on the first failure so
the output reads top-to-bottom as a triage checklist.

What it does, in order:

1. Lists every ``pyodbc``-visible ODBC driver (so "Driver 18 not installed"
   becomes obvious).
2. Reads ``.env`` and reports which ``AZURE_SQL_*`` keys are present /
   missing, without echoing the password.
3. Builds the production connection string (same builder as runtime) and
   redacts the ``Pwd=...`` segment before printing it.
4. Opens a real ``pyodbc`` connection, runs ``SELECT 1`` to prove the link
   works, then invokes ``WisPay.services.db.ensure_schema`` to create any
   missing ``dbo.wispay_*`` tables.
5. Lists the resulting ``wispay_*`` tables and the active workflow-rule
   version (proving seeding also succeeded).

Exit codes:
  0 — every step passed; tables are present and seeded.
  1 — one or more steps failed (details printed to stderr).

Usage:
  uv run python scripts/db_diagnose.py
  uv run python python scripts/db_diagnose.py   # when `uv` is not on PATH
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# .env loader — same convention as scripts/test_connections.py
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DOT_ENV = _PROJECT_ROOT / ".env"

# Make ``import WisPay`` work even when the script is run from a different
# cwd (e.g. ``python scripts/db_diagnose.py`` instead of
# ``uv run python scripts/db_diagnose.py``).
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if _DOT_ENV.exists():
    from dotenv import load_dotenv

    load_dotenv(_DOT_ENV, override=False)


# ---------------------------------------------------------------------------
# Pretty printers
# ---------------------------------------------------------------------------
def _ok(label: str, detail: str = "") -> None:
    msg = f"  [OK]   {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)


def _warn(label: str, detail: str) -> None:
    print(f"  [WARN] {label}: {detail}", file=sys.stderr)


def _fail(label: str, detail: str) -> None:
    print(f"  [FAIL] {label}: {detail}", file=sys.stderr)


def _section(title: str) -> None:
    bar = "-" * 60
    print()
    print(bar)
    print(f" {title}")
    print(bar)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------
def list_odbc_drivers() -> list[str]:
    """Return every ODBC driver ``pyodbc`` can see on this machine."""

    import pyodbc

    drivers = list(pyodbc.drivers())
    if not drivers:
        _fail("ODBC drivers", "pyodbc.drivers() returned an empty list")
    else:
        for driver in drivers:
            _ok("ODBC driver installed", driver)
        if not any("SQL Server" in d for d in drivers):
            _warn(
                "ODBC drivers",
                "no SQL Server driver installed; install "
                "'ODBC Driver 18 for SQL Server' from "
                "https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server",
            )
    return drivers


def report_env() -> list[str]:
    """Show which ``AZURE_SQL_*`` keys are populated (never the password)."""

    required = (
        "AZURE_SQL_SERVER",
        "AZURE_SQL_DATABASE",
        "AZURE_SQL_USERNAME",
        "AZURE_SQL_PASSWORD",
    )
    optional = (
        "AZURE_SQL_DRIVER",
        "AZURE_SQL_ENCRYPT",
        "AZURE_SQL_TRUST_SERVER_CERTIFICATE",
    )
    missing: list[str] = []
    for name in required:
        value = os.getenv(name, "")
        if name == "AZURE_SQL_PASSWORD":
            shown = "(set)" if value else "(missing)"
        else:
            shown = value or "(missing)"
        if not value:
            missing.append(name)
        _ok("env (required)", f"{name}={shown}")
    for name in optional:
        value = os.getenv(name, "")
        shown = value or "(default)"
        _ok("env (optional)", f"{name}={shown}")
    if missing:
        _fail(
            "env",
            f"missing required keys: {', '.join(missing)}. "
            "Copy .env.example to .env and fill the AZURE_SQL_* values.",
        )
    return missing


def show_connection_string() -> str:
    """Print the production connection string with the password redacted."""

    from WisPay.services.db import connection_string

    try:
        raw = connection_string()
    except RuntimeError as exc:
        _fail("connection_string()", str(exc))
        raise SystemExit(1) from exc
    redacted = re.sub(r"(Pwd=)[^;]*", r"\1***", raw)
    _ok("connection_string()", redacted)
    return raw


def bootstrap_and_list_tables() -> bool:
    """Open a real connection, run ``ensure_schema``, list ``wispay_*`` tables."""

    from WisPay.services.db import connect, ensure_schema

    try:
        conn = connect()
    except Exception as exc:
        msg = str(exc).splitlines()[0]
        if "IM002" in msg or "Data source name not found" in msg:
            msg += (
                "\n    Hint: install 'ODBC Driver 18 for SQL Server' "
                "(or set AZURE_SQL_DRIVER to an installed driver)."
            )
        elif "08001" in msg or "handshake" in msg.lower():
            msg += (
                "\n    Hint: add this machine's public IP to the Azure SQL "
                "server's networking/firewall allow-list."
            )
        _fail("pyodbc.connect", msg)
        return False

    try:
        cursor = conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("SELECT 1")
        cursor.fetchall()  # drain the result so subsequent statements can run
        _ok("SELECT 1", "link is live")
        cursor.close()

        ensure_schema(conn)
        _ok("ensure_schema", "ddl statements executed")

        cursor = conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("SELECT name FROM sys.tables WHERE name LIKE 'wispay_%' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        if not tables:
            _fail("tables", "no wispay_* tables exist after ensure_schema")
            return False
        for table in tables:
            _ok("table", f"dbo.{table}")
        return True
    except Exception as exc:
        _fail("bootstrap", f"{type(exc).__name__}: {exc}")
        return False
    finally:
        with __import__("contextlib").suppress(Exception):
            conn.close()  # type: ignore[attr-defined]


def show_active_rule_version() -> None:
    """Prove the rule seed worked by printing the active workflow-rule version."""

    from WisPay.services.runtime import stores

    try:
        bundle = stores()
    except Exception as exc:
        _fail("runtime.stores()", f"{type(exc).__name__}: {exc}")
        return
    try:
        version = bundle.rules.active_version()
    except Exception as exc:
        _fail("active_version()", f"{type(exc).__name__}: {exc}")
        return
    _ok("active rule version", version)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--skip-drivers",
        action="store_true",
        help="Skip the ODBC driver listing step.",
    )
    parser.add_argument(
        "--skip-env",
        action="store_true",
        help="Skip the .env / AZURE_SQL_* reporting step.",
    )
    args = parser.parse_args()

    print("WisPay - Azure SQL diagnostic")
    print(f"  Project root: {_PROJECT_ROOT}")
    print(f"  .env loaded:  {_DOT_ENV.exists()}")

    failures: list[str] = []

    if not args.skip_drivers:
        _section("Step 1 - ODBC drivers visible to pyodbc")
        if not list_odbc_drivers():
            failures.append("odbc-drivers")

    if not args.skip_env:
        _section("Step 2 - AZURE_SQL_* environment")
        missing = report_env()
        if missing:
            failures.append("env-missing")
            # Missing env -> every later step would fail; stop early.
            return 1
        _section("Step 3 - production connection_string()")
        show_connection_string()

    _section("Step 4 - connect + ensure_schema + table list")
    if not bootstrap_and_list_tables():
        failures.append("bootstrap")

    if "bootstrap" not in failures:
        _section("Step 5 - active workflow rule version")
        show_active_rule_version()

    _section("Summary")
    if failures:
        print(
            f"  Result: {len(failures)} step(s) FAILED: {', '.join(failures)}",
            file=sys.stderr,
        )
        return 1
    print("  Result: ALL OK — schema is live and seeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
