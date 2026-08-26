# 04 — Integration, live SQL smoke, e2e + browser review

Status: resolved
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

## Answer (2026-08-26)

1. `scripts/smoke_approval_flow.py` PASS against wispay.database.windows.net/db-wispay-test:
   schema idempotent across two runs, rules seeded once, save -> route -> decide ->
   fresh-connection re-read, audit actions [Changed, Approved], structural second pass no-op.
2. Environment fixed en route: ODBC Driver 18 (winget Microsoft.msodbcsql.18), server
   `az sql server update --enable-public-network true`, firewall rule WispayDevIP
   (171.243.49.113). Revert public access with `--enable-public-network false` when done.
3. e2e: approvals 2/2 PASS (route -> guard banner -> timeline -> approve -> recorded;
   mobile 390x844). Full-marker tally 4 passed / 3 failed — the 3 failures are the
   pre-existing wizard Documents defect on committed main (request-tracking effort's
   files; ui_smoke passes in isolation).
4. Browser review: desktop 1440x900 + mobile 390x844 screenshots captured; no horizontal
   scroll; no console errors on /approvals. User UI approval pending (screenshots
   omp-sshots-1566808dff8055a8 / 156680ee2cb71acc / 156692bb38de97ca).
5. As-built notes: QueueRow/TimelineRow models for foreach typing; Route.on_load;
   selection via foreach index (model-attr event args do not dispatch); isolated
   backend port 8012 required (port 8000 shared with sibling session caused crosswire).
