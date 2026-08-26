"""End-to-end coverage for the /approvals tracking surface.

Requires a running Reflex server (see AGENTS.md UI validation) with Azure SQL
reachable — decisions persist and read back through real stores.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect


def _submit_vendor_request(page: Page, base_url: str, tmp_path) -> str:
    """Walk the create wizard and return the generated request number."""
    invoice = tmp_path / "INV-APPROVE-1.pdf"
    invoice.write_bytes(b"%PDF-1.4\ntrailer<<>>\n%%EOF\n")

    page.goto(f"{base_url}/requests/new", wait_until="domcontentloaded")
    page.get_by_role("button", name="Vendor payment").click()
    page.get_by_role("button", name="Continue").click()
    page.fill("#fld-title", "Approval flow e2e payment")
    page.fill("#fld-vendor_name", "Acme Supplies JSC")
    page.fill("#fld-invoice_number", "INV-APPROVE-1")
    page.fill("#fld-invoice_date", "2026-08-01")
    page.fill("#fld-due_date", "2026-08-31")
    page.select_option("#fld-payment_terms_code", index=1)
    page.select_option("#fld-payment_method_code", index=1)
    page.select_option("#fld-legal_entity", index=1)
    page.select_option("#fld-cost_center", index=1)
    page.select_option("#fld-expense_category", index=1)
    page.fill("#fld-net_text", "150000000")
    page.fill("#fld-vat_text", "0")
    page.fill("#fld-purpose", "Hardware delivery payable through approval flow.")
    page.get_by_role("button", name="Continue").click()
    first_row = page.locator(".wispay-new-doc-row").first
    first_row.locator("input[type=file]").set_input_files(invoice)
    first_row.get_by_role("button", name="Attach").click()
    expect(first_row).to_have_class(re.compile(r"is-met"))
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="Submit for approval").click()
    number_locator = page.locator(".wispay-new-request-number")
    expect(number_locator).to_contain_text("WPR-")
    return number_locator.inner_text().strip()


@pytest.mark.e2e
def test_approvals_route_decide_and_timeline(
    page: Page,
    base_url: str,
    browser_errors: list[str],
    tmp_path,
) -> None:
    """Route a submitted request, approve it as Line Manager, see timeline."""
    number = _submit_vendor_request(page, base_url, tmp_path)

    page.goto(f"{base_url}/approvals", wait_until="domcontentloaded")
    expect(page).to_have_title("Approvals · WisPay")
    expect(page.locator(".wispay-request-empty")).to_be_visible()

    page.fill(".wispay-appr-route-input", number)
    page.get_by_role("button", name="Generate approval route").click()

    row = page.locator("tbody tr").first
    expect(row).to_contain_text(number)
    expect(row).to_contain_text("Line Manager")

    row.get_by_role("button", name="Review & decide").click()
    expect(page.locator(".wispay-appr-decision")).to_be_visible()

    # Guard surfaces through the banner: returning without a reason is blocked.
    page.get_by_role("button", name="Return for correction").click()
    expect(page.locator(".wispay-appr-status")).to_contain_text("reason is required")

    timeline_steps = page.locator(".wispay-appr-step")
    expect(timeline_steps).to_have_count(2)

    page.get_by_role("button", name="Approve").click()
    expect(page.locator(".wispay-appr-status")).to_contain_text("Decision recorded")

    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
    assert not browser_errors, "Browser errors detected:\n" + "\n".join(browser_errors)


@pytest.mark.e2e
def test_approvals_mobile_layout(browser, base_url: str) -> None:
    """The approvals page renders without horizontal scroll at 390x844."""
    context = browser.new_context(viewport={"width": 390, "height": 844})
    mobile_page = context.new_page()
    try:
        mobile_page.goto(f"{base_url}/approvals", wait_until="domcontentloaded")
        expect(mobile_page.get_by_role("heading", name="Approvals")).to_be_visible()
        assert mobile_page.evaluate(
            "() => document.documentElement.scrollWidth <= window.innerWidth"
        )
    finally:
        context.close()
