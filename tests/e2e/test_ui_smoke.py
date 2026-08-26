"""Baseline browser checks for the running WisPay frontend."""

import re

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_index_page_renders_across_viewports(
    page: Page,
    base_url: str,
    browser_errors: list[str],
) -> None:
    """Verify the baseline route and its responsive layout."""
    response = page.goto(f"{base_url}/", wait_until="domcontentloaded")

    assert response is not None
    assert response.ok, f"Frontend returned HTTP {response.status}"
    expect(page).to_have_title("Dashboard · WisPay")
    expect(page.get_by_role("heading", name="A clear place to start")).to_be_visible()
    expect(page.get_by_role("link", name="Start a new Payment Request")).to_have_attribute(
        "href", "/requests/new"
    )
    for label in (
        "Dashboard",
        "Requests",
        "New Request",
        "Approvals",
        "Finance Review",
        "Payments",
        "Audit",
    ):
        expect(page.get_by_role("link", name=label)).to_be_visible()
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")

    page.set_viewport_size({"width": 390, "height": 844})
    page.reload(wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="A clear place to start")).to_be_visible()
    expect(page.get_by_role("button", name="Open navigation")).to_be_visible()
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")

    assert not browser_errors, "Browser errors detected:\n" + "\n".join(browser_errors)


@pytest.mark.e2e
def test_shell_sidebar_is_responsive_and_interactive(
    page: Page,
    base_url: str,
    browser_errors: list[str],
) -> None:
    """Verify desktop rail, mobile drawer, group toggles, and shell overflow."""
    response = page.goto(f"{base_url}/requests", wait_until="domcontentloaded")

    assert response is not None
    assert response.ok, f"Frontend returned HTTP {response.status}"

    sidebar = page.locator(".wispay-sidebar")
    nav_labels = page.locator(".wispay-nav-item-label")
    main_frame = page.locator(".wispay-main-frame")

    for width, height in (
        (1440, 900),
        (1280, 900),
        (1024, 900),
        (768, 1024),
        (390, 844),
        (375, 812),
    ):
        page.set_viewport_size({"width": width, "height": height})
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")

        if width > 1024:
            assert sidebar.bounding_box() is not None
            assert round(sidebar.bounding_box()["width"]) == 264
            expect(main_frame).to_have_css("margin-left", "264px")
            expect(page.locator(".wispay-mobile-menu")).to_be_hidden()
        else:
            expect(page.locator(".wispay-mobile-menu")).to_be_visible()
            expect(main_frame).to_have_css("margin-left", "0px")
            assert (
                page.evaluate(
                    "() => getComputedStyle(document.querySelector('.wispay-navbar')).position"
                )
                == "fixed"
            )

    page.set_viewport_size({"width": 1440, "height": 900})
    page.get_by_role("button", name="Toggle sidebar").click()
    expect(sidebar).to_have_class(re.compile(r"is-collapsed"))
    expect(nav_labels.first).to_be_hidden()
    assert page.locator('.wispay-nav-item[title="Requests"]').count() == 1
    expect(sidebar).to_have_css("width", "72px")
    expect(main_frame).to_have_css("margin-left", "72px")

    page.get_by_role("button", name="Toggle sidebar").click()
    expect(nav_labels.first).to_be_visible()
    page.get_by_role("button", name="Toggle Review navigation group").click()
    expect(page.locator(".wispay-nav-group-items").nth(1)).to_be_hidden()

    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.get_by_role("button", name="Open navigation")).to_be_visible()
    expect(page.locator(".wispay-sidebar")).not_to_have_class(re.compile(r"is-open"))
    page.get_by_role("button", name="Open navigation").click()
    expect(page.get_by_role("button", name="Close navigation")).to_be_visible()
    expect(page.locator(".wispay-sidebar")).to_have_class(re.compile(r"is-open"))
    expect(page.locator(".wispay-backdrop")).to_have_class(re.compile(r"is-visible"))
    page.locator(".wispay-backdrop").click(position={"x": 340, "y": 422})
    expect(page.get_by_role("button", name="Open navigation")).to_be_visible()
    expect(page.locator(".wispay-backdrop")).not_to_have_class(re.compile(r"is-visible"))

    assert not browser_errors, "Browser errors detected:\n" + "\n".join(browser_errors)
