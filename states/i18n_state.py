"""i18n state adapter (EN/VI dictionary + persistence).

Server-side state. Persists the chosen language in a cookie so the EN↔VI
switch survives a page refresh (A9 contract).
"""

from __future__ import annotations

import reflex as rx

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "dashboard": "Dashboard",
        "requests": "Payment Requests",
        "approvals": "Approvals",
        "finance_review": "Finance Review",
        "payments": "Payment Recording",
        "admin": "Sample Configuration",
        "audit": "Audit Trail",
        "reports": "Reports & Exports",
        "language": "Language",
        "english": "English",
        "vietnamese": "Tiếng Việt",
    },
    "vi": {
        "dashboard": "Bảng điều khiển",
        "requests": "Yêu cầu thanh toán",
        "approvals": "Phê duyệt",
        "finance_review": "Duyệt tài chính",
        "payments": "Ghi nhận thanh toán",
        "admin": "Cấu hình mẫu",
        "audit": "Nhật ký kiểm toán",
        "reports": "Báo cáo & Xuất dữ liệu",
        "language": "Ngôn ngữ",
        "english": "English",
        "vietnamese": "Tiếng Việt",
    },
}


class I18nState(rx.State):
    """Language selection state for the EN↔VI toggle."""

    lang: str = rx.Cookie("en", name="wispay_lang", max_age=31536000, same_site="lax")

    @rx.event
    def set_lang(self, value: str) -> None:
        """Switch the active language; fall back to English on unknown value."""

        if value in _TRANSLATIONS:
            self.lang = value

    @rx.var
    def t(self) -> dict[str, str]:
        """Translation table for the current language."""

        return _TRANSLATIONS.get(self.lang, _TRANSLATIONS["en"])


__all__ = ["I18nState"]
