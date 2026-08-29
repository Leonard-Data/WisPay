"""Application route configuration and registration for the WisPay portal."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from states.admin_state import AdminState
from states.approvals import approvals_state
from states.audit_state import AuditState
from states.auth_state import AuthState
from states.dashboard_state import DashboardState
from states.finance_review_state import FinanceReviewState
from states.i18n_state import I18nState
from states.notifications_state import NotificationsState
from states.payments_state import PaymentsState
from states.persona_state import PersonaState
from states.reports_state import ReportsState
from states.request_tracking import request_tracking_state
from states.requests_state import RequestsState
from WisPay.pages import (
    admin_page,
    approvals_page,
    audit_page,
    callback_page,
    dashboard_page,
    finance_review_page,
    login_page,
    logout_page,
    not_found_page,
    payments_page,
    reports_page,
    request_detail_page,
    request_new_page,
    requests_page,
    server_error_page,
    signup_page,
    unavailable_page,
)
from WisPay.services import runtime as _runtime
from WisPay.services.demo_seed import demo_seed_active, seed_demo_state

if TYPE_CHECKING:
    from collections.abc import Callable

    import reflex as rx


_LOGGER = logging.getLogger(__name__)


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
        on_load=(
            AuthState.guard,
            PersonaState.ensure_default,
            DashboardState.refresh,
        ),
    ),
    Route(
        page=requests_page,
        route="/requests",
        title="Payment Requests · WisPay",
        description="Review and track Payment Requests in WisPay.",
        on_load=(
            AuthState.guard,
            RequestsState.refresh,
            request_tracking_state.refresh_queue,
        ),
    ),
    Route(
        page=request_detail_page,
        route="/requests/[number]",
        title="Payment Request Detail · WisPay",
        description="Track one Payment Request through review and approval.",
        on_load=(AuthState.guard, request_tracking_state.load_detail),
    ),
    Route(
        page=request_new_page,
        route="/requests/new",
        title="New Payment Request · WisPay",
        description="Create and submit a Vendor or Employee Payment Request.",
        on_load=(AuthState.guard,),
    ),
    Route(
        page=approvals_page,
        route="/approvals",
        title="Approvals · WisPay",
        description="Track and record Payment Request approval decisions.",
        on_load=(AuthState.guard, approvals_state.load_queue),
    ),
    Route(
        page=finance_review_page,
        route="/finance-review",
        title="Finance Review · WisPay",
        description="Triage Payment Requests across Budget, Compliance, Evidence, and Approval.",
        on_load=(AuthState.guard, FinanceReviewState.refresh),
    ),
    Route(
        page=payments_page,
        route="/payments",
        title="Payment Recording · WisPay",
        description="Record external payment completion. WisPay never initiates money movement.",
        on_load=(AuthState.guard, PaymentsState.refresh),
    ),
    Route(
        page=admin_page,
        route="/admin",
        title="Sample Configuration · WisPay",
        description="Tune rule set v1, persona matrix, and route simulator.",
        on_load=(AuthState.guard, AdminState.refresh),
    ),
    Route(
        page=audit_page,
        route="/audit",
        title="Audit Trail · WisPay",
        description="Read-only, append-only audit search.",
        on_load=(AuthState.guard, AuditState.refresh),
    ),
    Route(
        page=reports_page,
        route="/reports",
        title="Reports & Exports · WisPay",
        description="Spend analysis, success measures, and permission-scoped exports.",
        on_load=(AuthState.guard, ReportsState.refresh),
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
    """Register the configured WisPay pages with the application instance.

    When ``WISPAY_DEMO_MODE=1`` is exported, seed the durable store with
    S01–S16 demo fixtures before the lifespan task returns. The seed is
    additive (existing rows are left intact) so a re-seed refreshes demo
    data without losing real submissions.
    """

    _maybe_seed_demo_data()
    for route in ROUTES:
        app.add_page(
            route.page,
            route=route.route,
            title=route.title,
            description=route.description,
            on_load=list(route.on_load) if route.on_load else None,
        )


def _maybe_seed_demo_data() -> None:
    """Seed demo fixtures when ``WISPAY_DEMO_MODE=1`` is exported."""

    if not demo_seed_active():
        return
    if os.environ.get("WISPAY_DEMO_SEED_RAN") == "1":
        return
    try:
        bundle = _runtime.stores()
    except RuntimeError as error:
        _LOGGER.warning("Demo seed skipped — stores unavailable: %s", error)
        return
    summary = seed_demo_state(bundle)
    os.environ["WISPAY_DEMO_SEED_RAN"] = "1"
    _LOGGER.info(
        "Demo seed complete: %s requests, %s audits, %s payments, %s personas.",
        summary.requests,
        summary.audits,
        summary.payments,
        summary.personas,
    )


__all__ = [
    "I18nState",
    "NotificationsState",
    "ROUTES",
    "register_routes",
]
