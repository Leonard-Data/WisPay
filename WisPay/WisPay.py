"""WisPay Reflex application entry point.

The ASGI lifespan task registered below bootstraps the Azure SQL schema
(``WisPay.services.db.ensure_schema`` via :func:`WisPay.services.runtime.stores`)
exactly once per process start. Before this hook was added, schema creation
was lazy: the ``dbo.wispay_*`` tables only existed after the first state
handler that touched the runtime was invoked, which surprised anyone reading
the server log and found "no tables" even though credentials were configured.
The hook fails loudly on connection errors so setup problems surface at boot,
not on the first user request.
"""

import reflex as rx

from WisPay.routers import register_routes
from WisPay.services import runtime


class State(rx.State):
    """Root application state; feature-specific state lives in substates."""


app = rx.App(stylesheets=["design-tokens.css", "layout.css", "globals.css"])


def _bootstrap_azure_sql_schema() -> None:
    """Create/seed the ``dbo.wispay_*`` tables when the ASGI app starts.

    Idempotent — every call is safe to repeat. Raises the underlying
    connection error so a misconfigured environment (missing driver, blocked
    firewall, wrong credentials) fails the boot instead of the first request.
    """

    runtime.stores()


app.register_lifespan_task(_bootstrap_azure_sql_schema)
register_routes(app)
