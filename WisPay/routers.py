"""Application route configuration and registration for the WisPay portal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from states.auth_state import AuthState
from WisPay.pages import (
    callback_page,
    dashboard_page,
    login_page,
    logout_page,
    not_found_page,
    request_new_page,
    requests_page,
    server_error_page,
    signup_page,
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
    on_load: tuple[Any, ...] | None = None


ROUTES: tuple[Route, ...] = (
    Route(
        page=dashboard_page,
        route="/",
        title="Dashboard · WisPay",
        description="WisPay internal payment-request workspace.",
        on_load=(AuthState.guard,),
    ),
    Route(
        page=requests_page,
        route="/requests",
        title="Payment Requests · WisPay",
        description="Review and track Payment Requests in WisPay.",
        on_load=(AuthState.guard,),
    ),
    Route(
        page=request_new_page,
        route="/requests/new",
        title="New Payment Request · WisPay",
        description="Create and submit a Vendor or Employee Payment Request.",
        on_load=(AuthState.guard,),
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
        page=login_page,
        route="/login",
        title="Sign in · WisPay",
        description="Sign in to WisPay with your corporate Microsoft account.",
    ),
    Route(
        page=signup_page,
        route="/signup",
        title="Request access · WisPay",
        description="Request WisPay portal access for your corporate account.",
    ),
    Route(
        page=callback_page,
        route="/auth/callback",
        title="Completing sign-in · WisPay",
        description="Completing your WisPay single sign-on.",
        on_load=(AuthState.handle_callback,),
    ),
    Route(
        page=logout_page,
        route="/logout",
        title="Signing out · WisPay",
        description="Sign out of WisPay.",
        on_load=(AuthState.initiate_logout,),
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
            on_load=list(route.on_load) if route.on_load else None,
        )
