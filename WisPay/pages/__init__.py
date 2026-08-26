"""WisPay page components."""

from .callback import callback_page
from .dashboard import dashboard_page
from .errors import not_found_page, server_error_page, unavailable_page
from .login import login_page
from .logout import logout_page
from .request_new import request_new_page
from .requests import requests_page
from .signup import signup_page

__all__ = [
    "callback_page",
    "dashboard_page",
    "login_page",
    "logout_page",
    "not_found_page",
    "request_new_page",
    "requests_page",
    "server_error_page",
    "signup_page",
    "unavailable_page",
]
