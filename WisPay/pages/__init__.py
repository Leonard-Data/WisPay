"""WisPay page components."""

from .approvals import approvals_page
from .dashboard import dashboard_page
from .errors import not_found_page, server_error_page, unavailable_page
from .request_new import request_new_page
from .requests import requests_page

__all__ = [
    "approvals_page",
    "dashboard_page",
    "not_found_page",
    "request_new_page",
    "requests_page",
    "server_error_page",
    "unavailable_page",
]
