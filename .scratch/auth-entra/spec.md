# Spec: Entra ID authentication (`AuthState`, login / logout / signup)

Status: approved direction (hand-rolled MSAL, confirmed by Binh 2026-08-26)
Sources: `../WisPay-doc/CONTEXT.md`, ADR-0007, ADR-0005,
`docs/reference/backend/service-layer.md`, `docs/reference/backend/authz-rbac.md`,
repo `CONVENTIONS.md`, `DESIGN.md`.

## Goal

Corporate SSO sign-in for WisPay using **Microsoft Entra ID** (OIDC Authorization
Code + PKCE, confidential client) implemented in OSS Reflex 0.9.8:

- `AuthState` base Reflex state; every application state inherits from it.
- Pages: `/login`, `/signup`, `/auth/callback`, `/logout`.
- Pure-Python services own the flow; states stay thin UI adapters (ADR-0005).

## Decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Stack | Hand-rolled MSAL in OSS Reflex (user decision 2026-08-26) | reflex-enterprise `AuthPlugin` requires a commercial license + `rxe.App()` migration and does not expose an inheritable `AuthState` |
| Flow | OIDC Authorization Code + PKCE, confidential client, `msal` lib | ADR-0007 corporate IdP SSO; secret stays server-side |
| Sessions | Opaque random session id in an httpOnly `rx.Cookie`; server-side `SessionStore` (in-memory for MVP) | No token material in browser storage; swap store for Azure SQL later |
| Signup | "Request access" page creating an `AccessRequest`; Entra tenant membership still gates authentication; role activation is administrative | ADR-0007 non-decisions: role assignment is administrative; CONTEXT.md scope excludes employee identity management |
| Roles | Resolved fresh per page load from role assignments (`RoleName` enum) | Revocation-friendly; authorization decisions stay in backend services |
| Audit | Successful logins, failed exchanges, and logouts emit audit events through the existing audit-trail service boundary | Service catalog: AuthenticationContextService audits authentication failures |

## Configuration contract (`.env`)

```text
AZURE_ENTRA_TENANT_ID=<directory (tenant) id>
AZURE_ENTRA_CLIENT_ID=<application (client) id>
AZURE_ENTRA_CLIENT_SECRET=<client secret value>
AZURE_ENTRA_REDIRECT_URI=http://localhost:3000/auth/callback
SESSION_SECRET=<random 32-byte hex, signs nothing today; reserved>
```

Authority derived: `https://login.microsoftonline.com/{tenant_id}`.
Scopes: `openid profile email User.Read`.

## Service contracts (fixed for parallel implementation)

### `WisPay/services/authentication.py`

No `reflex` imports. Pydantic settings + MSAL wrapper + session store.

```python
class EntraAuthSettings(BaseSettings):
    tenant_id: str = ""; client_id: str = ""; client_secret: str = ""
    redirect_uri: str = "http://localhost:3000/auth/callback"
    scopes: tuple[str, ...] = ("openid", "profile", "email", "User.Read")
    session_ttl_minutes: int = 480
    def configured(self) -> bool          # all three required values non-empty
    @property def authority(self) -> str  # https://login.microsoftonline.com/{tenant_id}

def get_entra_settings() -> EntraAuthSettings  # cached

class PendingFlowRegistry:            # process-global, TTL 10 min, thread-safe
    def register(self, flow: PendingFlow) -> None      # stores keyed by state
    def consume(self, state: str) -> PendingFlow | None   # pops; None if unknown/expired

class AuthenticatedIdentity(NamedTuple):
    external_identity_id: str   # oid claim
    email: str                  # preferred_username / email claim
    display_name: str           # name claim
    id_token_hint: str | None
class EntraAuthService:
    def __init__(self, settings=None, app_factory=None)  # app_factory injectable for tests
    def build_authorization_url(self, registry, redirect_to="/", login_hint=None) -> str
    def exchange_code(self, registry, code: str, state: str) -> ExchangeResult
    def build_logout_url(self, post_logout_redirect_uri: str, id_token_hint=None) -> str

class SessionRecord(BaseModel):     # frozen
    session_id: str; external_identity_id: str; email: str
    display_name: str; id_token_hint: str | None; created_at; expires_at
    def expired(self, now) -> bool

class SessionStore(Protocol):
    def create(self, record) -> None
    def get(self, session_id) -> SessionRecord | None   # returns None if expired/deleted
    def delete(self, session_id) -> None
class InMemorySessionStore(SessionStore)

class AuthConfigError(RuntimeError): ...
class AuthFlowError(RuntimeError): ...      # invalid state, expired flow, token errors

def new_session(store, identity, settings, clock=...) -> SessionRecord
```

### `WisPay/services/user_context.py`

No `reflex` imports. Identity normalization + roles + access requests.

```python
class UserProfile(BaseModel):       # frozen; mirrors UserSnapshot fields where possible
    external_identity_id: str; email: str; display_name: str
    department: str | None = None; activated: bool = False; created_at

class UserRepository(Protocol):
    def find_by_identity(self, external_identity_id) -> UserProfile | None
    def save(self, profile) -> UserProfile
class InMemoryUserRepository(UserRepository)

class AccessRequest(BaseModel):     # frozen
    request_id: UUID; email: str; display_name: str; business_unit: str
    justification: str; status: Literal["Pending","Approved","Denied"]
    submitted_at: datetime; decided_at: datetime | None = None
class AccessRequestRepository(Protocol): add / list_all / set_status
class InMemoryAccessRequestRepository(...)

def resolve_user(users: UserRepository, identity: AuthenticatedIdentity-like,
                 now) -> UserProfile        # provisions inactive profile on first login
def active_roles(assignments: Iterable[RoleAssignment], identity_id, now) -> tuple[RoleName, ...]
def submit_access_request(repo, *, email, display_name, business_unit,
                          justification, now) -> AccessRequest
```

Role assignments come from `models.authorization.RoleAssignment` records held in an
in-memory collection for MVP; production swaps the repository.

### `states/auth_state.py`

```python
class AuthState(rx.State):
    session_token: str = rx.Cookie("", name="wispay_session", max_age=28800,
                                   same_site="lax", secure=False)
    auth_error: str = ""
    # computed: is_authenticated, current_user_name, current_user_email,
    #           current_user_roles (tuple[str, ...])
    @rx.event def start_login(self): ...        # -> rx.redirect(authorization url, is_external=True)
    @rx.event def handle_callback(self): ...    # reads self.router_data["query"]; sets cookie; redirects
    @rx.event def initiate_logout(self): ...    # deletes session, clears cookie, redirects
    @rx.event def guard(self): ...              # on_load: redirect "/login" when unauthenticated
```

Var/handler names above are the cross-agent contract consumed by the navbar and
routers; changing them requires updating both call sites.

## Routing

- Public routes: `/login`, `/signup`, `/auth/callback`, canonical error routes.
- Protected routes (`/`, `/requests`, `/requests/new`) gain `on_load=AuthState.guard`.
- `/logout` page exists so a plain link works; its `on_load` runs `initiate_logout`.
- `routers.Route` dataclass extended with optional `on_load` passthrough.

## UI contract

- Follows `DESIGN.md` + `assets/token.css` tokens via `styles.py`; Buridan UI
  component index consulted before writing markup (record chosen component page).
- Navbar shows "Sign in" when anonymous; user chip + "Sign out" when authenticated.
- Login page: brand mark, display heading, primary "Sign in with Microsoft"
  button (44px min height), secondary "Request access" link to `/signup`,
  inline error banner from `auth_error`.
- Signup page: form fields (work email, full name, business unit, justification),
  validation messages inline, success state explains admin activation. Copy never
  implies WisPay moves money or grants immediate access.
- Callback page: centered spinner + "Completing sign-in…" copy; no interactive chrome.

## Security invariants honored

1. State parameter validated against `PendingFlowRegistry` (CSRF); PKCE verifier
   consumed exactly once; flows expire after 10 minutes.
2. Session cookie httpOnly (Reflex default for cookies), `same_site=lax`;
   `secure=True` behind production TLS via settings.
3. Secrets only from `.env` (CONVENTIONS; AGENTS invariant 6).
4. Login failures and logouts audit-logged via the audit-trail service boundary.
5. No authorization decisions in state/UI — roles surfaced read-only; enforcement
   remains in services (ADR-0007 consequence).

## Test plan

- `tests/services/test_authentication.py`: URL shape (authority, client_id,
  redirect_uri, scope, state), PKCE consume-once, unknown-state rejection,
  exchange happy path + MSAL error mapping (msal monkeypatched), session expiry.
- `tests/services/test_user_context.py`: provisioning on first login, idempotent
  re-resolution, role filtering by effective dates, access-request submission
  validation + status transitions.
- `tests/states/test_auth_state.py`: guard redirects anonymous users, callback
  sets cookie and redirects on success, error paths surface `auth_error`
  (services stubbed).
- Gate: `bash scripts/validate.sh`; e2e marker excluded by default per pyproject.

## Out of scope (follow-ups)

- Azure SQL-backed `SessionStore`/`UserRepository` (Phase 1 delivery gate),
  MFA/step-up policy, group-claims-driven role sync, admin approval UI for
  access requests, refresh-token rotation.
