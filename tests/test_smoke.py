"""Smoke test: the project manifest is valid and carries expected identity.

Deliberately avoids importing Reflex so the gate has at least one runnable
test even before all runtime dependencies are installed.
"""

import tomllib
from pathlib import Path


def _read_pyproject() -> dict:
    path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with path.open("rb") as fh:
        return tomllib.load(fh)


def test_project_identity() -> None:
    project = _read_pyproject()["project"]
    assert project["name"] == "wispay"
    assert project["requires-python"] == ">=3.14"


def test_dev_tooling_declared() -> None:
    dev = _read_pyproject().get("dependency-groups", {}).get("dev", [])
    names = {dep.split(">=", 1)[0].split("[", 1)[0].strip() for dep in dev}
    for tool in ("ruff", "mypy", "pytest", "pre-commit"):
        assert tool in names, f"{tool} missing from dev dependency group"
