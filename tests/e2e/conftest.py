"""Shared Playwright fixtures for WisPay browser tests."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError

if TYPE_CHECKING:
    from collections.abc import Iterator

DEFAULT_BASE_URL = "http://127.0.0.1:3000"


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the running Reflex frontend URL."""
    return os.environ.get("WISPAY_E2E_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    """Create one Chromium instance for the e2e session."""
    headed = os.environ.get("WISPAY_E2E_HEADED") == "1"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        yield browser
        browser.close()


@pytest.fixture
def browser_errors() -> list[str]:
    """Collect browser-level errors so tests can fail with useful evidence."""
    return []


@pytest.fixture
def page(
    browser: Browser,
    browser_errors: list[str],
    request: pytest.FixtureRequest,
) -> Iterator[Page]:
    """Create an isolated desktop page and capture screenshots on failure."""
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.on("pageerror", lambda error: browser_errors.append(f"pageerror: {error}"))
    page.on(
        "console",
        lambda message: (
            browser_errors.append(f"console: {message.text}") if message.type == "error" else None
        ),
    )

    try:
        yield page
    finally:
        report = getattr(request.node, "rep_call", None)
        if report is not None and report.failed:
            artifact_dir = Path(os.environ.get("WISPAY_E2E_ARTIFACT_DIR", "test-results"))
            artifact_dir = artifact_dir / request.node.name
            artifact_dir.mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(PlaywrightError):
                page.screenshot(path=str(artifact_dir / "failure.png"), full_page=True)
        context.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo[object],
) -> Iterator[None]:
    """Expose the test report to fixtures during teardown."""
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
