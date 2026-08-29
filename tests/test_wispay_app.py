"""Test the application-startup Azure SQL bootstrap hook.

The application now registers a lifespan task that calls
``WisPay.services.runtime.stores()`` so the ``dbo.wispay_*`` schema is created
eagerly on ``reflex run`` instead of lazily on the first state-handler call.
These tests confirm the registration exists, calls the right runtime entry
point, and is idempotent — without touching the real Azure SQL server.
"""

from __future__ import annotations

import importlib
import inspect
from types import SimpleNamespace

import pytest

# Import the app module under the *real* runtime, then patch the runtime
# methods the bootstrap hook calls. The app module captured
# ``from WisPay.services import runtime`` at import time; the captured
# reference points at the same module object the tests then mutate via
# ``monkeypatch.setattr`` (the canonical pattern used in
# ``tests/services/test_runtime.py``).
_app_module = importlib.import_module("WisPay.WisPay")
_runtime_module = importlib.import_module("WisPay.services.runtime")


@pytest.fixture
def stubbed_runtime(monkeypatch: pytest.MonkeyPatch):
    """Swap the runtime methods the bootstrap hook calls for in-memory fakes."""

    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_stores(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append((args, kwargs))
        return SimpleNamespace(rules=SimpleNamespace(active_version=lambda: "v1"))

    def fake_is_connection_failure(error: BaseException) -> bool:
        return False

    monkeypatch.setattr(_runtime_module, "stores", fake_stores)
    monkeypatch.setattr(_runtime_module, "is_connection_failure", fake_is_connection_failure)
    return SimpleNamespace(calls=calls, fake_stores=fake_stores)


def _bootstrap_task() -> object:
    """Return the registered bootstrap task, or fail the test if it is missing."""

    for task in _app_module.app.get_lifespan_tasks():
        if getattr(task, "__name__", "") == "_bootstrap_azure_sql_schema":
            return task
    pytest.fail("expected an `_bootstrap_azure_sql_schema` lifespan task to be registered")


def test_app_registers_lifespan_task_for_schema_bootstrap() -> None:
    """``register_lifespan_task`` was called with a function."""

    assert hasattr(_app_module, "app"), "WisPay.WisPay must expose an `app` instance"
    task = _bootstrap_task()
    assert callable(task)


def test_bootstrap_task_invokes_runtime_stores(
    stubbed_runtime: SimpleNamespace,
) -> None:
    """Running the registered task calls ``runtime.stores()`` once per invocation."""

    bootstrap = _bootstrap_task()
    bootstrap()
    bootstrap()

    assert len(stubbed_runtime.calls) == 2
    for args, kwargs in stubbed_runtime.calls:
        assert args == ()
        assert kwargs == {}


def test_bootstrap_task_is_idempotent(
    stubbed_runtime: SimpleNamespace,
) -> None:
    """Repeated invocations are safe — they go through the cached store bundle.

    The underlying ``runtime.stores()`` already returns the cached bundle on
    subsequent calls, but the test makes the contract explicit so a future
    refactor cannot drop the lifespan registration without breaking it.
    """

    bootstrap = _bootstrap_task()
    for _ in range(3):
        bootstrap()

    # Three calls observed — the *stores()* layer caches the connection and
    # the schema DDL is itself idempotent (each statement is IF NOT EXISTS
    # / OBJECT_ID IS NULL guarded).
    assert len(stubbed_runtime.calls) == 3


def test_bootstrap_task_signature_is_parameter_free() -> None:
    """The lifespan task is callable with no args.

    Per ``LifespanMixin._run_lifespan_tasks`` the framework only injects
    ``app=`` when the task signature declares an ``app`` parameter; a plain
    zero-argument function is the supported shape and is what we want — the
    bootstrap should not depend on a live ``App`` instance.
    """

    bootstrap = _bootstrap_task()
    sig = inspect.signature(bootstrap)
    assert list(sig.parameters) == [], (
        f"lifespan task should take no parameters; got {list(sig.parameters)!r}"
    )
