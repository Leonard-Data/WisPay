"""WisPay page components."""

from .dashboard import dashboard_page
from .errors import not_found_page, server_error_page, unavailable_page
from .requests import requests_page

__all__ = [
    "dashboard_page",
    "not_found_page",
    "requests_page",
    "server_error_page",
    "unavailable_page",
]
