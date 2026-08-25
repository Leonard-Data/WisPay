"""Dashboard landing page used to demonstrate the shared shell."""

from __future__ import annotations

import reflex as rx

from WisPay.layout.shell import shell


def dashboard_page() -> rx.Component:
    """Render the initial workspace dashboard."""
    return shell(
        rx.el.section(
            rx.text("Workspace", class_name="wispay-eyebrow"),
            rx.heading("A clear place to start", class_name="wispay-page-title"),
            rx.text(
                "Use the navigation to submit, review, approve, and record payment completion.",
                class_name="wispay-page-lede",
            ),
            rx.box(
                rx.box(
                    rx.icon("sparkles", size=20),
                    rx.text("Workspace shell ready", class_name="wispay-card-kicker"),
                    class_name="wispay-card-heading",
                ),
                rx.text(
                    "This page is intentionally free of fabricated request metrics. Real queues and status summaries will be connected to domain state in the next feature slice.",
                    class_name="wispay-card-copy",
                ),
                rx.link(
                    rx.text("Start a new Payment Request"),
                    rx.icon("arrow-right", size=16),
                    href="/requests/new",
                    class_name="wispay-button wispay-button-primary",
                ),
                class_name="wispay-card wispay-dashboard-intro",
            ),
            rx.box(
                rx.box(
                    rx.text("Request-to-Pay lifecycle", class_name="wispay-card-kicker"),
                    rx.text(
                        "The shell keeps the controlled flow visible without implying that WisPay moves funds.",
                        class_name="wispay-card-copy",
                    ),
                    class_name="wispay-card wispay-card-inset",
                ),
                rx.box(
                    rx.text("Next action", class_name="wispay-card-kicker"),
                    rx.text(
                        "Connect the dashboard to Payment Request data and role-aware queues.",
                        class_name="wispay-card-copy",
                    ),
                    class_name="wispay-card wispay-card-warm",
                ),
                class_name="wispay-dashboard-grid",
            ),
            class_name="wispay-page",
        )
    )
