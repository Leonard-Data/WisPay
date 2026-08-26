#!/usr/bin/env python
"""Test connections to Azure SQL Database and Azure Document Intelligence.

Validates that:
1. AZURE_SQL_* env vars are present and a connection can be established.
2. AZURE_DOCUMENT_INTELLIGENCE_* env vars are present and the endpoint
   responds to a capabilities ping.

Exit codes:
  0 – all connections OK
  1 – one or more connections failed (details printed to stderr)

Usage:
  uv run python scripts/test_connections.py
  uv run python scripts/test_connections.py --db-only
  uv run python scripts/test_connections.py --di-only
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env from the project root (two levels up from this script)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DOT_ENV = _PROJECT_ROOT / ".env"

if _DOT_ENV.exists():
    from dotenv import load_dotenv

    load_dotenv(_DOT_ENV, override=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ok(label: str, detail: str = "") -> None:
    msg = f"  [OK] {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)


def _fail(label: str, reason: str) -> None:
    print(f"  [FAIL] {label}: {reason}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Azure SQL
# ---------------------------------------------------------------------------
def test_azure_sql() -> bool:
    """Try to connect to Azure SQL and run SELECT 1."""
    required = {
        "AZURE_SQL_SERVER": os.getenv("AZURE_SQL_SERVER"),
        "AZURE_SQL_DATABASE": os.getenv("AZURE_SQL_DATABASE"),
        "AZURE_SQL_USERNAME": os.getenv("AZURE_SQL_USERNAME"),
        "AZURE_SQL_PASSWORD": os.getenv("AZURE_SQL_PASSWORD"),
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        _fail("Azure SQL", f"missing env vars: {', '.join(missing)}")
        return False

    server = required["AZURE_SQL_SERVER"] or ""
    server = server.removeprefix("tcp:")
    database = required["AZURE_SQL_DATABASE"]
    username = required["AZURE_SQL_USERNAME"]
    password = required["AZURE_SQL_PASSWORD"]
    driver = os.getenv("AZURE_SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    encrypt = os.getenv("AZURE_SQL_ENCRYPT", "yes")
    trust_cert = os.getenv("AZURE_SQL_TRUST_SERVER_CERTIFICATE", "no")

    import pyodbc

    # Resolve the driver name to an installed one if the configured driver
    # is not found.
    available = pyodbc.drivers()
    if driver not in available:
        # Fall back to the first SQL Server driver available
        fallbacks = [d for d in available if "SQL Server" in d]
        if not fallbacks:
            _fail(
                "Azure SQL",
                f"configured driver {driver!r} not found and no SQL Server "
                f"ODBC driver is installed",
            )
            return False
        driver = fallbacks[0]
        print(f"    (using fallback driver: {driver})", file=sys.stderr)

    # Build connection string — newer drivers (ODBC Driver 17/18) support
    # Encrypt/TrustServerCertificate; the legacy "SQL Server" driver does not.
    is_legacy_driver = driver.lower().startswith("sql server") and "odbc" not in driver.lower()

    parts = [
        f"Driver={{{driver}}}",
        f"Server=tcp:{server},1433",
        f"Database={database}",
        f"Uid={username}",
        f"Pwd={password}",
        "Connection Timeout=15",
    ]
    if not is_legacy_driver:
        parts.append(f"Encrypt={encrypt}")
        parts.append(f"TrustServerCertificate={trust_cert}")

    conn_str = ";".join(parts) + ";"

    try:
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS ok")
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row and row[0] == 1:
            _ok("Azure SQL", f"connected to {server}/{database}")
            return True
        _fail("Azure SQL", "SELECT 1 returned unexpected result")
        return False
    except Exception as exc:
        msg = str(exc).split("\n")[0]
        # Surface known Azure SQL network errors with actionable hints
        if "Deny Public Network Access" in msg:
            msg += (
                "\n    (Hint: The server has Deny Public Network Access = Yes. "
                "Connect via a VPN, Azure Bastion, or enable public access in "
                "the Azure SQL Server networking blade.)"
            )
        elif "Cannot open server" in msg or "could not open database" in msg.lower():
            msg += (
                "\n    (Hint: Check that the database name is correct and the "
                "server allows connections from this IP.)"
            )
        _fail("Azure SQL", msg)
        return False


# ---------------------------------------------------------------------------
# Azure Document Intelligence
# ---------------------------------------------------------------------------
def test_azure_document_intelligence() -> bool:
    """Ping the Document Intelligence endpoint with a resource details call."""
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

    if not endpoint:
        _fail("Azure Document Intelligence", "missing AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        return False
    if not key:
        _fail("Azure Document Intelligence", "missing AZURE_DOCUMENT_INTELLIGENCE_KEY")
        return False

    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
        from azure.core.exceptions import HttpResponseError

        client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key),
        )

        # Ping the endpoint by attempting to analyze a minimal PDF.
        # A 400 (Invalid request / unsupported content) means auth succeeded
        # and the endpoint is alive. A 401/403 means the key is wrong.
        minimal_pdf = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
            b"xref\n0 3\n0000000000 65535 f \n"
            b"0000000009 00000 n \n0000000058 00000 n \n"
            b"trailer<</Size 3/Root 1 0 R>>\nstartxref\n109\n%%EOF"
        )
        try:
            # Use IO[bytes] via a BytesIO wrapper for type compatibility
            import io

            poller = client.begin_analyze_document(
                model_id="prebuilt-read",
                body=io.BytesIO(minimal_pdf),
                content_type="application/pdf",
            )
            poller.result(timeout=30)
            _ok("Azure Document Intelligence", f"endpoint: {endpoint} (read OK)")
            return True
        except HttpResponseError as exc:
            if exc.status_code in (400, 422):
                # Auth succeeded, content was rejected — endpoint is alive
                _ok("Azure Document Intelligence", "endpoint reachable (auth OK)")
                return True
            if exc.status_code in (401, 403):
                _fail(
                    "Azure Document Intelligence", f"authentication failed (HTTP {exc.status_code})"
                )
                return False
            raise

    except Exception as exc:
        msg = str(exc).split("\n")[0]
        if "connect" in msg.lower() or "connection" in msg.lower():
            msg += "\n    (Hint: Verify AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is correct and the service is running.)"
        _fail("Azure Document Intelligence", msg)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Test Azure connections for WisPay.")
    parser.add_argument("--db-only", action="store_true", help="Test Azure SQL only")
    parser.add_argument("--di-only", action="store_true", help="Test Document Intelligence only")
    args = parser.parse_args()

    print("WisPay - Azure Connection Tests")
    print(f"  Project root: {_PROJECT_ROOT}")
    print()

    sep = "-" * 50
    results: list[tuple[str, bool]] = []

    if not args.di_only:
        print(sep)
        print(" Azure SQL Database")
        print(sep)
        ok = test_azure_sql()
        results.append(("Azure SQL", ok))
        print()

    if not args.db_only:
        print(sep)
        print(" Azure Document Intelligence")
        print(sep)
        ok = test_azure_document_intelligence()
        results.append(("Azure Document Intelligence", ok))
        print()

    # Summary
    print(sep)
    all_ok = all(ok for _, ok in results)
    if all_ok:
        print(" Result: ALL CONNECTIONS OK")
    else:
        failed = [name for name, ok in results if not ok]
        print(f" Result: {len(failed)} connection(s) FAILED: {', '.join(failed)}", file=sys.stderr)

    print(sep)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
