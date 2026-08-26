"""Application route configuration and registration for the WisPay portal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from WisPay.pages import (
    approvals_page,
    dashboard_page,
    request_new_page,
    requests_page,
    server_error_page,
    unavailable_page,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    import reflex as rx


@dataclass(frozen=True, slots=True)
class Route:
    """Configuration for one page registered with the Reflex application."""

    page: Callable[[], rx.Component]
    route: str
    title: str
    description: str


ROUTES: tuple[Route, ...] = (
    Route(
        page=dashboard_page,
        route="/",
        title="Dashboard · WisPay",
        description="WisPay internal payment-request workspace.",
    ),
    Route(
        page=requests_page,
        route="/requests",
        title="Payment Requests · WisPay",
        description="Review and track Payment Requests in WisPay.",
    ),
    Route(
        page=request_new_page,
        route="/requests/new",
        title="New Payment Request · WisPay",
        description="Create and submit a Vendor or Employee Payment Request.",
    ),
    Route(
        page=approvals_page,
        route="/approvals",
        title="Approvals · WisPay",
        description="Track and record Payment Request approval decisions.",
    ),
    Route(
        page=server_error_page,
        route="/500",
        title="Something Went Wrong · WisPay",
        description="WisPay encountered an unexpected error.",
    ),
    Route(
        page=unavailable_page,
        route="/503",
        title="WisPay Temporarily Unavailable",
        description="WisPay is temporarily unavailable.",
    ),
)


def register_routes(app: rx.App) -> None:
    """Register the configured WisPay pages with the application instance."""
    for route in ROUTES:
        app.add_page(
            route.page,
            route=route.route,
            title=route.title,
            description=route.description,
        )
