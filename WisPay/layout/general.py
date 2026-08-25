"""General-purpose layouts shared by non-workflow pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import reflex as rx


@dataclass(frozen=True, slots=True)
class ErrorPageContent:
    """Copy and presentation details for one operational error state."""

    code: str
    title: str
    message: str
    icon: str


ERROR_PAGE_CONTENT: dict[int, ErrorPageContent] = {
    404: ErrorPageContent(
        code="404",
        title="Page not found",
        message="The page you requested does not exist or may have moved.",
        icon="search-x",
    ),
    500: ErrorPageContent(
        code="500",
        title="Something went wrong",
        message="WisPay could not complete that request. Please try again or return to the dashboard.",
        icon="triangle-alert",
    ),
    503: ErrorPageContent(
        code="503",
        title="WisPay is temporarily unavailable",
        message="The workspace is taking a short break. Please try again in a moment.",
        icon="cloud-off",
    ),
}


def general_error_page(status_code: int) -> rx.Component:
    """Render the shared, standalone page for a known HTTP error state."""
    try:
        content = ERROR_PAGE_CONTENT[status_code]
    except KeyError as exc:
        raise ValueError(f"Unsupported error page status: {status_code}") from exc

    return cast(
        "rx.Component",
        rx.box(
            rx.el.header(
                rx.link(
                    rx.image(
                        src="/brand-mark.svg", alt="WisPay mark", class_name="wispay-brand-mark"
                    ),
                    rx.text("WisPay", class_name="wispay-brand-wordmark"),
                    href="/",
                    aria_label="WisPay home",
                    class_name="wispay-error-brand",
                ),
                class_name="wispay-error-header",
            ),
            rx.el.main(
                rx.box(
                    rx.icon(
                        content.icon, size=22, aria_hidden="true", class_name="wispay-error-icon"
                    ),
                    rx.text(content.code, class_name="wispay-error-code"),
                    class_name="wispay-error-mark",
                ),
                rx.heading(content.title, class_name="wispay-error-title"),
                rx.text(content.message, class_name="wispay-error-copy"),
                rx.link(
                    rx.icon("arrow-left", size=16),
                    rx.text("Return to dashboard"),
                    href="/",
                    class_name="wispay-button wispay-button-primary",
                ),
                align="center",
                aria_live="polite",
                class_name="wispay-error-main",
            ),
            align="center",
            justify="center",
            class_name="wispay-error-page",
        ),
    )


__all__ = ["ERROR_PAGE_CONTENT", "ErrorPageContent", "general_error_page"]
