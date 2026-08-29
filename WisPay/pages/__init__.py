"""WisPay page components."""

from .admin import admin_page
from .approvals import approvals_page
from .audit import audit_page
from .callback import callback_page
from .dashboard import dashboard_page
from .errors import not_found_page, server_error_page, unavailable_page
from .finance_review import finance_review_page
from .login import login_page
from .logout import logout_page
from .payments import payments_page
from .reports import reports_page
from .request_detail import request_detail_page
from .request_new import request_new_page
from .requests import requests_page
from .signup import signup_page

__all__ = [
    "admin_page",
    "approvals_page",
    "audit_page",
    "callback_page",
    "dashboard_page",
    "finance_review_page",
    "login_page",
    "logout_page",
    "not_found_page",
    "payments_page",
    "reports_page",
    "request_detail_page",
    "request_new_page",
    "requests_page",
    "server_error_page",
    "signup_page",
    "unavailable_page",
]
