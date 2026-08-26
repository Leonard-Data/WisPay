"""End-to-end coverage for the /approvals tracking surface.

Requires a running Reflex server (see AGENTS.md UI validation) with Azure SQL
reachable — decisions persist and read back through real stores.

The request under approval is seeded through the service layer rather than the
create wizard: the committed wizard's Documents step renders no rows (pre-existing
defect owned by the request-tracking effort's in-flight work), and this suite
covers the approval slice, not request capture.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import Page, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from WisPay.models import (  # noqa: E402
    AccountingDimension,
    BeneficiaryReference,
    LifecycleState,
    Money,
    PaymentRequest,
    RequestType,
    UserSnapshot,
    VendorPaymentDetails,
)
from WisPay.models.enums import (  # noqa: E402
    AccessClassification,
    BeneficiaryType,
    OpexCapexClassification,
)
from WisPay.services.runtime import stores  # noqa: E402

_NOW = datetime.now(UTC)


def _seed_submitted_request(purpose: str, gross: str) -> PaymentRequest:
    """Persist one Submitted vendor request and return it."""
    bundle = stores()
    request = PaymentRequest(
        request_id=uuid4(),
        request_number=f"WPR-E2E-{uuid4().hex[:10]}",
        request_type=RequestType.VENDOR,
        requester=UserSnapshot(
            external_identity_id="e2e-requester",
            display_name="E2E Requester",
            email="e2e-requester@wispay.example",
            captured_at=_NOW,
        ),
        beneficiary=BeneficiaryReference(
            beneficiary_type=BeneficiaryType.VENDOR,
            display_name="E2E Vendor",
            captured_at=_NOW,
            access_classification=AccessClassification.CONFIDENTIAL,
        ),
        accounting_dimension=AccountingDimension(
            legal_entity_code="LE-01",
            legal_entity_name="WisPay Co",
            department_code="CC-01",
            department_name="Operations",
            cost_center_code="C-01",
            cost_center_name="Shared",
            expense_category_code="E-01",
            expense_category_name="Services",
            classification=OpexCapexClassification.OPEX,
            budget_period="2026-08",
            captured_at=_NOW,
        ),
        purpose=purpose,
        total_amount=Money(amount=Decimal(gross), currency_code="VND", decimal_scale=0),
        accounting_period="2026-08",
        lifecycle_state=LifecycleState.SUBMITTED,
        lifecycle_version="v1",
        submitted_version=1,
        details=VendorPaymentDetails(
            invoice_date=_NOW.date(),
            due_date=_NOW.date(),
            invoice_net_amount=Money(amount=Decimal(gross), currency_code="VND", decimal_scale=0),
            vat_amount=Money(amount=Decimal("0"), currency_code="VND", decimal_scale=0),
            invoice_gross_amount=Money(amount=Decimal(gross), currency_code="VND", decimal_scale=0),
            payment_terms="Net 30",
            proposed_payment_method="Bank transfer",
            duplicate_warning_key=f"e2e|{uuid4().hex}|{gross}",
            invoice_number=f"INV-{uuid4().hex[:8]}",
        ),
        created_at=_NOW,
        updated_at=_NOW,
    )
    bundle.requests.save(request)
    return request


@pytest.mark.e2e
def test_approvals_route_decide_and_timeline(page: Page, base_url: str) -> None:
    """Route a seeded request, approve it as Executive, see the timeline."""
    request = _seed_submitted_request("Approval e2e hardware delivery", "150000000")

    page.goto(f"{base_url}/approvals", wait_until="domcontentloaded")
    expect(page).to_have_title("Approvals · WisPay")
    expect(page.get_by_role("heading", name="Approvals", exact=True)).to_be_visible()

    # Route generation from rule set v1 (Line Manager + Executive above 100M VND).
    number = request.request_number or ""
    page.fill(".wispay-appr-route-input", number)
    expect(page.locator(".wispay-appr-route-input")).to_have_value(number, timeout=20_000)
    page.get_by_role("button", name="Generate approval route").click()
    expect(page.locator(".wispay-appr-status")).to_contain_text(
        "generated with 2 step", timeout=20_000
    )

    # The Line Manager step must appear for the Line Manager sample actor.
    row = page.locator("tbody tr").filter(has_text=number)
    expect(row).to_contain_text("Line Manager")
    row.get_by_role("button", name="Review & decide").click()
    expect(page.locator(".wispay-appr-decision")).to_be_visible()

    # Guard surfaces through the banner: returning without a reason is blocked.
    page.get_by_role("button", name="Return for correction").click()
    expect(page.locator(".wispay-appr-status")).to_contain_text("reason is required")

    expect(page.locator(".wispay-appr-step")).to_have_count(2)

    page.get_by_role("button", name="Approve", exact=True).click()
    expect(page.locator(".wispay-appr-status")).to_contain_text("Decision recorded", timeout=20_000)

    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.e2e
def test_approvals_mobile_layout(browser, base_url: str) -> None:
    """The approvals page renders without horizontal scroll at 390x844."""
    _seed_submitted_request("Approval e2e mobile seed", "120000000")
    context = browser.new_context(viewport={"width": 390, "height": 844})
    mobile_page = context.new_page()
    try:
        mobile_page.goto(f"{base_url}/approvals", wait_until="domcontentloaded")
        expect(mobile_page.get_by_role("heading", name="Approvals", exact=True)).to_be_visible()
        assert mobile_page.evaluate(
            "() => document.documentElement.scrollWidth <= window.innerWidth"
        )
    finally:
        context.close()
