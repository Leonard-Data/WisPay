"""New Payment Request wizard screen (``/requests/new``).

Package layout: ``catalogs`` holds static option data, ``controls`` the
RequestCreateState-bound field builders, ``step_*`` one module per wizard
step, and ``wizard_page`` the chrome plus final composition. All behavior
routes through ``states.request_create.RequestCreateState`` — no business
logic lives here.

Visual contract: ``docs/product/DESIGN.md`` plus the ``new-request.html``
source example (four steps: Type → Details → Documents → Review).
"""

from WisPay.pages.request_new.wizard_page import request_new_page

__all__ = ["request_new_page"]
