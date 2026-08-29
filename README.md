# WisPay

WisPay is the internal portal for Vendor and Employee Payment Requests: submission,
review, approval, and Finance's recording of external payment completion. This
repository holds the working Reflex application (WisPay 0.9.8, Python 3.14). The
canonical domain glossary, delivery plan, ADRs, and product design live in the
sibling `WisPay-doc` repository.

## Stack

- **Python 3.14**, managed with [`uv`](https://github.com/astral-sh/uv).
- **Reflex 0.9.8** (Radix Themes + Tailwind v4, accent `red`).
- **Pydantic v2** for domain models and request validation.
- **SQLite** for dev (BE-1 default) and **Azure SQL** for production.
- **Microsoft Entra ID** SSO for the authz boundary (ADR-0007).

## Quick start (developer laptop)

```bash
# 1. Install runtime + dev tooling.
uv sync --group dev

# 2. Pre-commit hooks (one-time).
uv run pre-commit install

# 3. Start the dev server with the SQLite + demo seed default.
WISPAY_DEMO_MODE=1 uv run reflex run --frontend-port 3000 --backend-port 8000 --backend-host 127.0.0.1
```

Open http://127.0.0.1:3000/ to land on the dashboard. `WISPAY_DEMO_MODE=1` loads
S01–S16 demo fixtures covering every canonical lifecycle state (Draft,
Submitted, Budget Review, Compliance Review, Evidence Validation, Approval Pending,
Approved, Payment in Process, Paid, Closed, Returned for Correction, Rejected,
Cancelled, Adjustment Process).

## Validation gate

```bash
bash scripts/validate.sh
```

Runs ruff lint, ruff format check, mypy, and the pytest suite (246 tests, 9 e2e
deselected by default). The pre-push hook invokes this script automatically;
CI re-runs it on every PR. Add `--fix` to apply auto-fixes first.

## Driver selection

Driver dispatch lives in `rxconfig.py`; the precedence is:

| Knob                       | Result                                        |
| -------------------------- | --------------------------------------------- |
| `WS_DB_URL=sqlite:///...`  | Dev path; SQLite file-backed, ping-free.       |
| `AZURE_SQL_*` env set      | Azure SQL via ODBC Driver 18 (production).    |
| neither                    | Defaults to `sqlite:///wispay.db` for dev.    |

Connection-string assembly is exercised in `tests/services/test_db.py` and
`tests/services/test_db_sqlite.py`; the reconnect probe is in
`tests/services/test_runtime.py`. The smoke gates never assume a live Azure SQL
server — they only verify the assembly.

## Production deploy

The application ships as a single container artifact:

```bash
docker build -t wispay:latest .
docker run --rm -p 8000:8000 \
  -e WISPAY_DEMO_MODE=1 \
  -e WS_DB_URL=sqlite:///./wispay.db \
  wispay:latest
```

For Azure, use the `azure-deploy.bicep` template:

```bash
az deployment group create \
  --resource-group wispay-prod \
  --template-file azure-deploy.bicep \
  --parameters @azure-deploy.parameters.json
```

See `DEPLOYMENT-READINESS.md` for the full deployability report (canonical-domain
invariants, validation gates, route coverage, and embedded brand mark).

## Repository layout

```
WisPay/                Reflex app package (components, pages, layouts, models, services)
states/                Reflex state adapters (thin UI-layer only; read services through Stores)
tests/                 pytest suite (services, models, components, pages, states, e2e)
scripts/               validate.sh, serve.py, sql/, db_diagnose.py, smoke tests
assets/                brand-mark.svg, design-tokens.css, layout.css, globals.css
azure-deploy.bicep     Azure Container Apps + Azure SQL scaffold
Dockerfile             Single-image production build
docs/                  product doc snapshots mirrored from WisPay-doc/
.scratch/wispay-deploy-build/implementation-tracker.md
                       BS-1 + t2/t3/t4/t5/t6 build log (single source of truth)
```

## Security & audit invariants (CONTEXT.md)

Non-negotiable for any payment-related change:

1. The requester cannot approve their own request (approval_workflow.decide).
2. Only an approved request can enter payment processing (payment_recording.start_payment).
3. Only authorized Finance / Payment Operator roles can record payment completion.
4. Every consequential action emits a hash-chained audit event
   (audit_trail.InMemoryAuditTrail + sql_repositories.DurableAuditTrail).
5. Submitted financial records and audit events are never hard-deleted (CONTEXT
   invariant 10; PaymentRecordStore has no `delete` method).
6. Records ≠ money movement — UI copy is enforced through `WisPay.styles`.
7. Secrets live in `.env` only; never in code or commits.

See `desination: wispay` deployment report for the full test evidence map.
