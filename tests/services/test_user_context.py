"""Unit tests for the user context service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from WisPay.models import RoleAssignment
from WisPay.services.user_context import (
    AccessRequest,
    InMemoryAccessRequestRepository,
    InMemoryUserRepository,
    active_roles,
    get_access_request_repository,
    resolve_user,
    submit_access_request,
    user_snapshot,
)

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


class IdentityStub:
    """Duck-typed authenticated identity for tests."""

    def __init__(self, id_: str, email: str, name: str) -> None:
        self.external_identity_id = id_
        self.email = email
        self.display_name = name


def make_assignment(
    identity_id: str,
    role_value: str,
    *,
    starts_days: float = -30.0,
    ends_days: float | None = 30.0,
) -> RoleAssignment:
    from WisPay.models import UserSnapshot
    from WisPay.models.enums import RoleName

    return RoleAssignment(
        assignment_id=uuid4(),
        user=UserSnapshot(
            external_identity_id=identity_id,
            display_name="Assignee",
            email=f"{identity_id}@corp.example",
            captured_at=NOW,
        ),
        role=RoleName(role_value),
        organization_scope="org-1",
        source="test",
        starts_at=NOW + timedelta(days=starts_days),
        ends_at=NOW + timedelta(days=ends_days) if ends_days is not None else None,
        version="v1",
    )


def test_resolve_user_provisions_deactivated_profile() -> None:
    users = InMemoryUserRepository()
    profile = resolve_user(users, IdentityStub("oid-1", "a@corp.example", "A"), NOW)
    assert profile.activated is False
    assert profile.created_at == NOW
    assert users.find_by_identity("oid-1") == profile


def test_resolve_user_is_idempotent_and_refreshes_snapshot() -> None:
    users = InMemoryUserRepository()
    first = resolve_user(users, IdentityStub("oid-1", "old@corp.example", "Old"), NOW)
    later = NOW + timedelta(days=1)
    second = resolve_user(users, IdentityStub("oid-1", "new@corp.example", "New"), later)
    assert second.created_at == first.created_at
    assert second.email == "new@corp.example"
    assert second.display_name == "New"
    assert len([second]) == 1
    assert users.find_by_identity("oid-1") == second


def test_active_roles_filters_by_user_and_dates() -> None:
    assignments = [
        make_assignment("oid-1", "Requester"),
        make_assignment("oid-2", "Requester"),
        make_assignment("oid-1", "Line Manager", starts_days=10.0),  # future
        make_assignment("oid-1", "Budget Owner", ends_days=-1.0),  # expired
    ]
    roles = active_roles(assignments, "oid-1", NOW)
    assert roles == ("Requester",)


def test_submit_access_request_validates_and_persists() -> None:
    repo = InMemoryAccessRequestRepository()
    request = submit_access_request(
        repo,
        email="  New.Person@Corp.Example ",
        display_name="New Person",
        business_unit="Finance",
        justification="Vendor payments for my team.",
        now=NOW,
    )
    assert request.status == "Pending"
    assert request.decided_at is None
    assert request.email == "new.person@corp.example"
    assert repo.list_all() == (request,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", ""),
        ("email", "no-at-sign"),
        ("email", "bad space@corp.example"),
        ("display_name", "   "),
        ("business_unit", ""),
        ("justification", ""),
    ],
)
def test_submit_access_request_rejects_invalid(field: str, value: str) -> None:
    kwargs = {
        "email": "p@corp.example",
        "display_name": "P",
        "business_unit": "BU",
        "justification": "Because.",
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        submit_access_request(InMemoryAccessRequestRepository(), now=NOW, **kwargs)  # type: ignore[arg-type]


def test_access_request_status_transition() -> None:
    repo = InMemoryAccessRequestRepository()
    request = submit_access_request(
        repo,
        email="p@corp.example",
        display_name="P",
        business_unit="BU",
        justification="Because.",
        now=NOW,
    )
    decided = NOW + timedelta(days=2)
    updated = repo.set_status(request.request_id, "Approved", decided)
    assert updated is not None
    assert isinstance(updated, AccessRequest)
    assert updated.status == "Approved"
    assert updated.decided_at == decided
    assert repo.set_status(uuid4(), "Denied", decided) is None


def test_repository_singleton_is_stable() -> None:
    assert get_access_request_repository() is get_access_request_repository()


def test_user_snapshot_shape() -> None:
    users = InMemoryUserRepository()
    profile = resolve_user(users, IdentityStub("oid-9", "nine@corp.example", "Nine"), NOW)
    snapshot = user_snapshot(profile, NOW + timedelta(hours=1))
    assert snapshot.external_identity_id == "oid-9"
    assert snapshot.captured_at == profile.created_at + timedelta(hours=1)
