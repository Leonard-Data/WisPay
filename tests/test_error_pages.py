"""Coverage for shared operational error-page content."""

import pytest

from WisPay.layout.general import ERROR_PAGE_CONTENT, general_error_page


@pytest.mark.parametrize("status_code", [404, 500, 503])
def test_known_error_pages_render(status_code: int) -> None:
    """Each supported status code has a shared renderable page."""
    page = general_error_page(status_code)

    assert page is not None
    assert ERROR_PAGE_CONTENT[status_code].code == str(status_code)


def test_unknown_error_status_is_rejected() -> None:
    """Unsupported statuses do not silently get the wrong error copy."""
    with pytest.raises(ValueError, match="Unsupported error page status"):
        general_error_page(418)
