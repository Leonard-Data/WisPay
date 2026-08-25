"""Footer for the WisPay application shell."""

from __future__ import annotations

import reflex as rx


def footer() -> rx.Component:
    """Render concise product and payment-recording context."""
    return rx.el.footer(
        rx.text("WisPay · Internal payment-request portal", class_name="wispay-footer-copy"),
        rx.text(
            "Records external payment completion; it does not move funds.",
            class_name="wispay-footer-note",
        ),
        class_name="wispay-footer",
    )
