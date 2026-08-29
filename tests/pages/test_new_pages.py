"""Smoke tests for the new product surfaces built in t4.

Each page must render to a Reflex ``Component`` node and expose the
design-system surface class plus the persona/section markers documented
in ``DESIGN.md``.
"""

from __future__ import annotations

from WisPay.pages import (
    admin_page,
    audit_page,
    dashboard_page,
    finance_review_page,
    payments_page,
    reports_page,
)


def test_dashboard_renders() -> None:
    """The dashboard renders the dashboard shell + sample banner."""

    node = dashboard_page()
    html = str(node.render())
    assert "wispay-dashboard-shell" in html
    assert "Workspace" in html
    assert "Sample configuration" in html


def test_finance_review_renders_all_buckets() -> None:
    """Finance Review surfaces all four buckets in deterministic order."""

    node = finance_review_page()
    html = str(node.render())
    assert "wispay-finrev-shell" in html
    for label in ("Budget Review", "Compliance Review", "Evidence Validation", "Approval Pending"):
        assert label in html


def test_payments_renders_records_not_movement_copy() -> None:
    """The payments page keeps the records-not-movement copy loud."""

    node = payments_page()
    html = str(node.render())
    assert "wispay-payments-shell" in html
    assert "Records, not movement" in html
    # No copy that implies WisPay initiates money movement.
    for forbidden in ("transfer funds", "debit", "send money"):
        assert forbidden not in html.lower()


def test_admin_renders_sample_configuration_warning() -> None:
    """Admin surfaces the sample-configuration-not-policy banner."""

    node = admin_page()
    html = str(node.render())
    assert "wispay-admin-shell" in html
    assert "Sample configuration" in html


def test_audit_renders_stream() -> None:
    """Audit surfaces the append-only banner and stream rows."""

    node = audit_page()
    html = str(node.render())
    assert "wispay-audit-shell" in html
    assert "Append-only" in html
    assert "Submitted" in html


def test_reports_renders_export_center() -> None:
    """Reports surface the export center rows."""

    node = reports_page()
    html = str(node.render())
    assert "wispay-reports-shell" in html
    assert "Spend by cost center" in html
    assert "Export center" in html
