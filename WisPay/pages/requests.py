"""Payment Request queue screen."""

from __future__ import annotations

import reflex as rx

from WisPay.layout.shell import shell


def _filter_field(label: str, control: rx.Component) -> rx.Component:
    """Render a labelled queue filter without coupling it to request state."""
    return rx.el.label(
        rx.el.span(label, class_name="wispay-filter-label"),
        control,
        class_name="wispay-filter-field",
    )


def _request_filters() -> rx.Component:
    """Render the queue filter surface for the upcoming request data feed."""
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.el.span("Queue filters", class_name="wispay-card-kicker"),
                rx.el.span(
                    "Filters will apply when Payment Request data is connected.",
                    class_name="wispay-filter-note",
                ),
                class_name="wispay-filter-heading",
            ),
            rx.el.div(
                _filter_field(
                    "Search",
                    rx.input(
                        placeholder="ID, title, or beneficiary",
                        type="search",
                        aria_label="Search Payment Requests",
                        class_name="wispay-filter-control",
                        disabled=True,
                    ),
                ),
                _filter_field(
                    "Status",
                    rx.el.select(
                        rx.el.option("All statuses", value="all"),
                        rx.el.option("Approval Pending", value="approval-pending"),
                        rx.el.option("Approved", value="approved"),
                        rx.el.option("Paid", value="paid"),
                        aria_label="Filter by status",
                        class_name="wispay-filter-control",
                        disabled=True,
                    ),
                ),
                _filter_field(
                    "Request type",
                    rx.el.select(
                        rx.el.option("All request types", value="all"),
                        rx.el.option("Vendor Payment Request", value="vendor"),
                        rx.el.option("Employee Payment Request", value="employee"),
                        aria_label="Filter by request type",
                        class_name="wispay-filter-control",
                        disabled=True,
                    ),
                ),
                _filter_field(
                    "Sort by",
                    rx.el.select(
                        rx.el.option("Recently submitted", value="submitted"),
                        rx.el.option("Due date", value="due"),
                        rx.el.option("Amount", value="amount"),
                        aria_label="Sort Payment Requests",
                        class_name="wispay-filter-control",
                        disabled=True,
                    ),
                ),
                class_name="wispay-filter-grid",
            ),
            class_name="wispay-requests-filters wispay-card",
        ),
        aria_label="Payment Request queue filters",
        class_name="wispay-requests-filter-section",
    )


def _empty_request_queue() -> rx.Component:
    """Render the honest empty state until request data is wired to the page."""
    return rx.el.section(
        rx.icon("inbox", size=28),
        rx.el.h2("No Payment Requests yet", class_name="wispay-empty-title"),
        rx.el.p(
            "Submitted Payment Requests will appear here with their status, beneficiary, "
            "amount, and next action.",
            class_name="wispay-empty-copy",
        ),
        rx.link(
            rx.icon("plus", size=16),
            rx.el.span("Create a Payment Request"),
            href="/requests/new",
            class_name="wispay-button wispay-button-primary",
        ),
        aria_label="Empty Payment Request queue",
        class_name="wispay-request-empty",
    )


def requests_page() -> rx.Component:
    """Render the Payment Request queue shell and its empty state."""
    return shell(
        rx.el.section(
            rx.el.div(
                rx.el.div(
                    rx.el.span("Payment Request queue", class_name="wispay-eyebrow"),
                    rx.el.h1("Requests", class_name="wispay-page-title"),
                    rx.el.p(
                        "Track Vendor and Employee Payment Requests from submission through "
                        "approval and Finance payment recording.",
                        class_name="wispay-page-lede",
                    ),
                    class_name="wispay-request-heading",
                ),
                rx.link(
                    rx.icon("plus", size=16),
                    rx.el.span("New Payment Request"),
                    href="/requests/new",
                    class_name="wispay-button wispay-button-primary",
                ),
                class_name="wispay-request-toolbar",
            ),
            _request_filters(),
            _empty_request_queue(),
            class_name="wispay-page wispay-requests-page",
        )
    )
