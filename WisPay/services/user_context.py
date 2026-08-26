"""User context service: identity normalization, roles, and access requests.

Pure Python per ADR-0005 — no Reflex imports. Normalizes an authenticated
identity into a WisPay user profile (service catalog:
``AuthenticationContextService``), resolves effective roles from
:class:`~WisPay.models.authorization.RoleAssignment` records, and owns the
"request access" workflow used by the sign-up page.

MVP persistence: in-memory repositories. Production swaps in Azure SQL-backed
repositories implementing the same protocols; call sites do not change.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID, uuid4

from WisPay.models import RoleAssignment, RoleName, UserSnapshot
from WisPay.models._base import WisPayBaseModel


class UserProfile(WisPayBaseModel):
    """Application-level user record keyed by the external identity id."""

    external_identity_id: str
    email: str
    display_name: str
    department: str | None = None
    activated: bool = False
    created_at: datetime


class AccessRequest(WisPayBaseModel):
    """A submitted request for portal access pending administrative decision."""

    request_id: UUID
    email: str
    display_name: str
    business_unit: str
    justification: str
    status: Literal["Pending", "Approved", "Denied"] = "Pending"
    submitted_at: datetime
    decided_at: datetime | None = None


class UserRepository(Protocol):
    """Persistence boundary for user profiles."""

    def find_by_identity(self, external_identity_id: str) -> UserProfile | None: ...

    def save(self, profile: UserProfile) -> UserProfile: ...


class InMemoryUserRepository(UserRepository):
    """Thread-safe process-local user store for the MVP slice."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users: dict[str, UserProfile] = {}

    def find_by_identity(self, external_identity_id: str) -> UserProfile | None:
        with self._lock:
            return self._users.get(external_identity_id)

    def save(self, profile: UserProfile) -> UserProfile:
        with self._lock:
            self._users[profile.external_identity_id] = profile
        return profile


class AccessRequestRepository(Protocol):
    """Persistence boundary for access requests."""

    def add(self, request: AccessRequest) -> AccessRequest: ...

    def list_all(self) -> tuple[AccessRequest, ...]: ...

    def set_status(
        self,
        request_id: UUID,
        status: Literal["Pending", "Approved", "Denied"],
        decided_at: datetime,
    ) -> AccessRequest | None:
        """Transition one request's status and stamp the decision time."""

        ...


class InMemoryAccessRequestRepository(AccessRequestRepository):
    """Thread-safe process-local access-request store for the MVP slice."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[UUID, AccessRequest] = {}

    def add(self, request: AccessRequest) -> AccessRequest:
        with self._lock:
            self._requests[request.request_id] = request
        return request

    def list_all(self) -> tuple[AccessRequest, ...]:
        with self._lock:
            ordered = sorted(self._requests.values(), key=lambda r: r.submitted_at)
        return tuple(ordered)

    def set_status(
        self,
        request_id: UUID,
        status: Literal["Pending", "Approved", "Denied"],
        decided_at: datetime,
    ) -> AccessRequest | None:
        with self._lock:
            current = self._requests.get(request_id)
            if current is None:
                return None
            updated = current.evolve(status=status, decided_at=decided_at)
            self._requests[request_id] = updated
        return updated


class IdentityLike(Protocol):
    """Structural view of an authenticated identity for normalization."""

    @property
    def external_identity_id(self) -> str: ...

    @property
    def email(self) -> str: ...

    @property
    def display_name(self) -> str: ...


def resolve_user(
    users: UserRepository,
    identity: IdentityLike,
    now: datetime,
) -> UserProfile:
    """Return the profile for ``identity``, provisioning it on first login.

    ``identity`` is duck-typed to :class:`AuthenticatedIdentity` (attributes
    ``external_identity_id``, ``email``, ``display_name``). New profiles are
    created deactivated; activation is an administrative action (ADR-0007).
    Re-resolution refreshes the email/display-name snapshot without
    duplicating rows.
    """

    existing = users.find_by_identity(identity.external_identity_id)
    if existing is not None:
        refreshed = existing.evolve(email=identity.email, display_name=identity.display_name)
        return users.save(refreshed)
    profile = UserProfile(
        external_identity_id=identity.external_identity_id,
        email=identity.email,
        display_name=identity.display_name,
        activated=False,
        created_at=now,
    )
    return users.save(profile)


def active_roles(
    assignments: list[RoleAssignment],
    identity_id: str,
    now: datetime,
) -> tuple[RoleName, ...]:
    """Roles effectively held by ``identity_id`` at ``now``, input order kept."""

    seen: list[RoleName] = []
    for assignment in assignments:
        if assignment.user.external_identity_id != identity_id:
            continue
        if assignment.starts_at > now:
            continue
        if assignment.ends_at is not None and now >= assignment.ends_at:
            continue
        if assignment.role not in seen:
            seen.append(assignment.role)
    return tuple(seen)


def _validate_signup_field(label: str, value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} is required.")
    return cleaned


def submit_access_request(
    repo: AccessRequestRepository,
    *,
    email: str,
    display_name: str,
    business_unit: str,
    justification: str,
    now: datetime,
) -> AccessRequest:
    """Validate and persist a new Pending access request."""

    clean_email = _validate_signup_field("Work email", email)
    local, sep, domain = clean_email.partition("@")
    if sep != "@" or not local or not domain or any(c.isspace() for c in clean_email):
        raise ValueError("Enter a valid work email address.")
    clean_name = _validate_signup_field("Full name", display_name)
    clean_unit = _validate_signup_field("Business unit", business_unit)
    clean_reason = _validate_signup_field("Justification", justification)
    request = AccessRequest(
        request_id=uuid4(),
        email=clean_email.lower(),
        display_name=clean_name,
        business_unit=clean_unit,
        justification=clean_reason,
        status="Pending",
        submitted_at=now,
    )
    return repo.add(request)


def register_role_assignment(assignment: RoleAssignment) -> None:
    """Seed one role assignment into the MVP in-memory collection."""

    ROLE_ASSIGNMENTS.append(assignment)


def user_snapshot(profile: UserProfile, now: datetime) -> UserSnapshot:
    """Build the canonical user snapshot used by audit events and services."""

    return UserSnapshot(
        external_identity_id=profile.external_identity_id,
        display_name=profile.display_name,
        email=profile.email,
        department=profile.department,
        captured_at=now,
    )


_ACCESS_REQUEST_LOCK = threading.Lock()
_ACCESS_REQUESTS = InMemoryAccessRequestRepository()


def get_access_request_repository() -> AccessRequestRepository:
    """Process-wide access-request repository singleton."""

    with _ACCESS_REQUEST_LOCK:
        return _ACCESS_REQUESTS


ROLE_ASSIGNMENTS: list[RoleAssignment] = []
