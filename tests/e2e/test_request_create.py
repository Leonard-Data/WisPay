"""End-to-end coverage for the create-payment-request wizard."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


@pytest.mark.e2e
def test_wizard_happy_path_submits_vendor_request(
    page: Page,
    base_url: str,
    browser_errors: list[str],
    tmp_path,
) -> None:
    """Type → Details → Documents → Review → Submit yields a request number."""
    invoice = tmp_path / "INV-1001.pdf"
    invoice.write_bytes(b"%PDF-1.4\ntrailer<<>>\n%%EOF\n")

    page.goto(f"{base_url}/requests/new", wait_until="networkidle")
    expect(page).to_have_title("New Payment Request · WisPay")
    expect(page.get_by_role("heading", name="Create payment request")).to_be_visible()

    # Hydration race under full-battery load: the first select/Continue pair
    # can land before React attaches handlers. Retry until step 2 renders.
    details_heading = page.get_by_role("heading", name="Vendor payment details")
    for _ in range(3):
        page.get_by_role("button", name="Vendor payment").click()
        page.get_by_role("button", name="Continue").click()
        try:
            details_heading.wait_for(timeout=3000)
            break
        except PlaywrightTimeoutError:
            continue
    else:
        pytest.fail("wizard did not advance past the type step")
    expect(details_heading).to_be_visible()

    page.fill("#fld-title", "Vendor invoice INV-1001 payment")
    page.fill("#fld-vendor_name", "Acme Supplies JSC")
    page.fill("#fld-invoice_number", "INV-1001")
    page.fill("#fld-invoice_date", "2026-08-01")
    page.fill("#fld-due_date", "2026-08-31")
    page.select_option("#fld-payment_terms_code", index=1)
    page.select_option("#fld-payment_method_code", index=1)
    page.select_option("#fld-legal_entity", index=1)
    page.select_option("#fld-cost_center", index=1)
    page.select_option("#fld-expense_category", index=1)
    page.fill("#fld-net_text", "10000000")
    page.fill("#fld-vat_text", "1000000")
    expect(page.locator(".wispay-new-gross-value")).to_have_text("11,000,000 VND")
    page.fill(
        "#fld-purpose",
        "Pay supplier invoice INV-1001 for August hardware delivery.",
    )

    page.get_by_role("button", name="Continue").click()
    expect(page.get_by_role("heading", name="Supporting documents")).to_be_visible()

    first_row = page.locator(".wispay-new-doc-row").first
    expect(first_row).to_contain_text("Invoice")
    first_row.locator("input[type=file]").set_input_files(invoice)
    first_row.get_by_role("button", name="Attach").click()
    expect(first_row).to_have_class(__import__("re").compile(r"is-met"))

    page.get_by_role("button", name="Continue").click()
    expect(page.get_by_role("heading", name="Review before submitting")).to_be_visible()
    summary = page.locator(".wispay-new-review-summary")
    expect(summary).to_contain_text("11,000,000 VND")

    page.get_by_role("button", name="Submit for approval").click()
    expect(page.get_by_role("heading", name="Payment Request submitted")).to_be_visible()
    expect(page.locator(".wispay-new-request-number")).to_contain_text("WPR-")
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
    assert not browser_errors, "Browser errors detected:\n" + "\n".join(browser_errors)


@pytest.mark.e2e
def test_wizard_blocks_empty_details_with_field_errors(
    page: Page,
    base_url: str,
    browser_errors: list[str],
) -> None:
    """Continue without type or with empty details shows visible reasons."""
    page.goto(f"{base_url}/requests/new", wait_until="domcontentloaded")

    page.get_by_role("button", name="Continue").click()
    expect(page.locator(".wispay-new-live-status")).to_have_text("Select a request type first.")

    page.get_by_role("button", name="Reimbursement").click()
    page.get_by_role("button", name="Continue").click()
    expect(page.get_by_role("heading", name="Reimbursement details")).to_be_visible()

    page.get_by_role("button", name="Continue").click()
    errors = page.locator(".wispay-new-field-error")
    expect(errors.first).to_be_visible()
    assert errors.count() >= 5, "expected visible field errors on empty details"
    assert not browser_errors, "Browser errors detected:\n" + "\n".join(browser_errors)


@pytest.mark.e2e
def test_wizard_responsive_at_mobile_width(
    page: Page,
    base_url: str,
    browser_errors: list[str],
) -> None:
    """The wizard renders without horizontal scroll at 390×844."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{base_url}/requests/new", wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="Create payment request")).to_be_visible()
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
    steps = page.locator(".wispay-new-steps")
    columns = steps.evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length")
    assert columns == 2, f"step bar should collapse to two columns, got {columns}"
    assert not browser_errors, "Browser errors detected:\n" + "\n".join(browser_errors)
