"""Application route configuration and registration for the WisPay portal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from states.approvals import approvals_state
from states.request_tracking import request_tracking_state
from WisPay.pages import (
    approvals_page,
    dashboard_page,
    not_found_page,
    request_detail_page,
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
    on_load: object | None = None


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
        on_load=request_tracking_state.refresh_queue,
    ),
    Route(
        page=request_detail_page,
        route="/requests/[number]",
        title="Payment Request Detail · WisPay",
        description="Track one Payment Request through review and approval.",
        on_load=request_tracking_state.load_detail,
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
        on_load=approvals_state.load_queue,
    ),
    Route(
        page=not_found_page,
        route="/404",
        title="Page Not Found · WisPay",
        description="The requested WisPay page could not be found.",
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
            on_load=route.on_load,
        )
