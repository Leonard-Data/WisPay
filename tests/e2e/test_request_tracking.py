"""Browser flows for the request-tracking surfaces (queue and detail)."""

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from pathlib import Path


pytestmark = pytest.mark.e2e

_WPR = re.compile(r"WPR-\d{4}-\d{4}")


def _submit_vendor_request(page: Page, base_url: str, tmp_path: Path) -> str:
    """Walk the wizard's happy path and return the generated request number."""

    invoice = tmp_path / "INV-E2E-1.pdf"
    invoice.write_bytes(b"%PDF-1.4\ntrailer<<>>\n%%EOF\n")

    page.goto(f"{base_url}/requests/new", wait_until="domcontentloaded")
    page.get_by_role("button", name="Vendor payment").click()
    page.get_by_role("button", name="Continue").click()

    page.fill("#fld-title", "E2E tracking invoice")
    page.fill("#fld-vendor_name", "Acme E2E Supplies")
    page.fill("#fld-invoice_number", "INV-E2E-1")
    page.fill("#fld-invoice_date", "2026-08-01")
    page.fill("#fld-due_date", "2026-08-31")
    page.select_option("#fld-payment_terms_code", index=1)
    page.select_option("#fld-payment_method_code", index=1)
    page.select_option("#fld-legal_entity", index=1)
    page.select_option("#fld-cost_center", index=1)
    page.select_option("#fld-expense_category", index=1)
    page.fill("#fld-net_text", "10000000")
    page.fill("#fld-vat_text", "1000000")
    page.fill("#fld-purpose", "Pay supplier invoice for August delivery.")
    page.get_by_role("button", name="Continue").click()

    first_row = page.locator(".wispay-new-doc-row").first
    first_row.locator("input[type=file]").set_input_files(str(invoice))
    first_row.get_by_role("button", name="Attach").click()
    expect(first_row).to_have_class(re.compile(r"is-met"))
    page.get_by_role("button", name="Continue").click()

    page.get_by_role("button", name="Submit for approval").click()
    number = page.locator(".wispay-new-request-number").inner_text().strip()
    match = _WPR.search(number)
    assert match, f"unexpected request number {number!r}"
    return match.group(0)


@pytest.mark.e2e
def test_queue_lists_submitted_request_with_filters_and_pills(
    page: Page,
    base_url: str,
    browser_errors: list[str],
    tmp_path: Path,
) -> None:
    """Submit once; the queue must surface it with pill, count, and filter."""
    number = _submit_vendor_request(page, base_url, tmp_path)

    page.goto(f"{base_url}/requests", wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="Requests")).to_be_visible()

    row = page.locator("tr", has_text=number).first
    expect(row).to_be_visible()
    expect(row.locator(".wispay-pill")).to_have_text(re.compile("Submitted"))
    expect(row.locator(".wispay-queue-amt")).to_contain_text("VND")
    expect(page.locator(".wispay-queue-count")).to_contain_text("1")

    page.locator("#q-search").fill("no-such-needle")
    expect(page.get_by_text("No requests match your filters")).to_be_visible()
    page.get_by_role("button", name="Clear all filters").click()
    expect(row).to_be_visible()

    page.locator("#q-status").select_option("Rejected")
    expect(page.get_by_text("No requests match your filters")).to_be_visible()
    page.get_by_role("button", name="Reset filters").click()
    expect(row).to_be_visible()

    row.locator(".wispay-queue-id").click()
    page.wait_for_url(f"**/requests/{number}")
    expect(page.get_by_role("heading", name="Acme E2E Supplies")).to_be_visible()

    assert not browser_errors


@pytest.mark.e2e
def test_detail_renders_header_stepper_audit_and_not_found(
    page: Page,
    base_url: str,
    browser_errors: list[str],
    tmp_path: Path,
) -> None:
    """Detail anatomy per spec decisions 10-12 plus the not-found path."""
    number = _submit_vendor_request(page, base_url, tmp_path)

    page.goto(f"{base_url}/requests/{number}", wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="Acme E2E Supplies")).to_be_visible()
    expect(page.get_by_text(f"Request {number}")).to_be_visible()
    expect(page.get_by_text("Gross request")).to_be_visible()
    expect(page.get_by_text("WisPay records approvals and payment references")).to_be_visible()
    steps = page.locator(".wispay-detail-step")
    expect(steps).to_have_count(7)
    expect(steps.nth(1)).to_have_class(re.compile(r"is-active"))

    page.get_by_role("tab", name="Audit").click()
    audit = page.locator(".wispay-detail-audit-row")
    expect(audit.first).to_contain_text("Submitted")
    expect(page.get_by_text("Chain verified")).to_be_visible()

    page.goto(f"{base_url}/requests/WPR-1999-9999", wait_until="domcontentloaded")
    expect(page.get_by_text("Request not found")).to_be_visible()

    for width, height in ((1440, 900), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        page.reload(wait_until="domcontentloaded")
        expect(page.get_by_text("Request not found")).to_be_visible()
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")

    assert not browser_errors, "Browser errors detected:\n" + "\n".join(browser_errors)
