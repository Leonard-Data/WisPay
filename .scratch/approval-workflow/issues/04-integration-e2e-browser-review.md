# 04 — Integration, live SQL smoke, e2e + browser review

Status: needs-triage
Feature: `.scratch/approval-workflow/spec.md`

Blocked by: 01, 02, 03

## Target

No new feature files. Runs the integrated branch; owns fixes across seams if integration
fails; records evidence.

## Change

1. `bash scripts/validate.sh` (fix-forward lint/type/test fallout at seams).
2. Live Azure SQL smoke once credentials are fixed (see map.md blocker):
   `ensure_schema` idempotency (run twice), scripted round trip save→route→decide→re-read
   over a fresh connection, second-run structural no-op, audit rows spot-check.
3. Start Reflex (`uv run reflex run --frontend-port 3000 --backend-port 8000
   --backend-host 127.0.0.1`), run `uv run pytest -m e2e`.
4. Browser review per AGENTS.md: Playwright MCP, desktop 1440×900 + mobile 390×844,
   accessibility snapshot + screenshot + console + network failures for `/approvals`,
   compare against `docs/product/DESIGN.md`; ≤3 fix iterations.
5. Present rendered route + screenshots to the user for UI approval (explicit gate —
   automated passes are not design approval).

## Acceptance

Spec acceptance criteria 1–5 all evidenced; screenshots attached to this ticket's Answer;
map.md updated.
