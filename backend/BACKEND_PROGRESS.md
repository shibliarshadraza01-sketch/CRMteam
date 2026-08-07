\# Qualify Learn CRM — Backend Progress



> Persistent implementation tracker. Update this file AND

> `BACKEND\_LEARNING\_GUIDE.md` at the end of every checkpoint.



\## Permanent Rules



\- PostgreSQL only — never silently fall back to SQLite.

\- Frontend is locked except for minimum required integration fixes.

\- Never expose `.env`, passwords, API keys, tokens, or secrets.

\- Never claim a command/test passed unless it was actually executed.

\- Security and authorization must be enforced server-side.

\- Do not modify unrelated code while fixing backend issues.

\- Do not mark a checkpoint complete until both documentation files are updated.



\## Checkpoint Status



| CP | Checkpoint | Status |

|---|---|---|

| CP1 | Backend Foundation | COMPLETE / VERIFIED |

| CP2 | Accounts + Custom User | PARTIAL / BLOCKED — model complete, migrate/tests blocked (no PostgreSQL) |

| CP3 | Authentication / JWT | PARTIAL / BLOCKED — implementation complete, migrate/DB-tests blocked (no PostgreSQL) |

| CP4 | Super Admin Secondary Access-Code Authentication | PARTIAL / BLOCKED — implementation complete, migrate/DB-tests blocked (no PostgreSQL) |

| CP5 | Device / Session Authorization | PARTIAL / BLOCKED — implementation complete, migrate/DB-tests blocked (no PostgreSQL) |

| CP6 | Hierarchy + RBAC | PARTIAL / BLOCKED — implementation complete, 59/59 new tests genuinely pass (no DB required), migrate still blocked (no PostgreSQL) |

| CP7 | Core CRM Foundation | PARTIAL / BLOCKED — abstract models + managers + utilities implemented, 54/54 new tests genuinely pass (no DB required), migrate still blocked (no PostgreSQL) |

| CP8 | Organization Hierarchy | PARTIAL / BLOCKED — models/serializers/permissions/services/admin implemented, 60/60 new tests genuinely pass (no DB required), migrate still blocked (no PostgreSQL) |

| CP9 | CRM Foundation (Customer/Lead/Contact/Address) | PARTIAL / BLOCKED — models/managers/serializers/permissions/services/admin implemented, 60/60 new tests genuinely pass (no DB required), migrate still blocked (no PostgreSQL) |

| CP10 | CRM REST API (Customers/Leads/Contacts/Addresses) | PARTIAL / BLOCKED — views/urls/filters/pagination implemented, 93/93 new tests genuinely pass (no DB required), migrate still blocked (no PostgreSQL) |

| CP11 | Sales Pipeline (Opportunities) | PARTIAL / BLOCKED — models/managers/services/API/filters implemented, 58/58 new-file DB-free tests genuinely pass, migrate still blocked (no PostgreSQL) |

| CP12 | Quoting & Invoicing (Sales) | PARTIAL / BLOCKED — models/services/API/filters implemented, 71/71 new-file DB-free tests genuinely pass, migrate still blocked (no PostgreSQL) |

| CP13 | Product/Service Catalog & Price Books | PARTIAL / BLOCKED — models/services/API/filters implemented, 59/59 new-file DB-free tests genuinely pass, migrate still blocked (no PostgreSQL) |

| CP14 | Activities (Tasks/Events/ActivityLog/Reminders) | PARTIAL / BLOCKED — models/services/API/filters implemented, 78/78 new-file DB-free tests genuinely pass, migrate still blocked (no PostgreSQL) |

| CP15 | Communications (Email Templates/Messages, Notifications, Communication Log) | PARTIAL / BLOCKED — models/services/API/filters implemented, 70/70 new-file DB-free tests genuinely pass, migrate still blocked (no PostgreSQL) |

| CP16 | Reports & Dashboards (Saved Reports, Report Executions, Dashboards, Widgets) | PARTIAL / BLOCKED — models/services/API/filters implemented, 65/65 new-file DB-free tests genuinely pass, migrate still blocked (no PostgreSQL) |

| CP17 | Workflow Automation (Workflows, Triggers, Actions, Executions) | PARTIAL / BLOCKED — models/services/API/filters implemented, 72/72 new-file DB-free tests genuinely pass, migrate still blocked (no PostgreSQL) |

| CP18 | Integrations (API Keys, Webhooks) | PARTIAL / BLOCKED — models/services/API/filters implemented, 80/80 new-file DB-free tests genuinely pass, migrate still blocked (no PostgreSQL) |

| CP19 | Platform (Audit Log, Settings, Feature Flags, Background Jobs) | PARTIAL / BLOCKED — models/services/API/filters implemented, audit logging wired to CRM/sales via signals, 69/69 new-file DB-free tests genuinely pass, migrate still blocked (no PostgreSQL) |

| CP20 | Final Project-Wide Audit (regression, security, performance, architecture) | PARTIAL / BLOCKED — full audit complete across CP1–CP19, two genuine bugs found and fixed (zero behavior change), 923/923 project DB-free tests still genuinely pass, migrate still blocked (no PostgreSQL) |



\## CP1 — Backend Foundation



\*\*Status:\*\* COMPLETE / VERIFIED



\### Implemented



\- Django 5.1.4 backend

\- Django REST Framework

\- PostgreSQL + psycopg

\- `base`, `development`, `production` settings

\- Environment-based configuration

\- `.env` protection + `.env.example`

\- django-filter

\- django-cors-headers

\- drf-spectacular

\- OpenAPI schema

\- Swagger UI

\- Health endpoint

\- pytest + pytest-django

\- 3 infrastructure smoke tests

\- ASGI + WSGI configuration

\- `BACKEND\_LEARNING\_GUIDE.md`



\### Verified



\- `manage.py check` — PASS, 0 issues

\- PostgreSQL connection — PASS

\- Database engine — `postgresql`

\- Development database — `crm\_db`

\- `makemigrations --check --dry-run` — PASS, no changes

\- pytest — 3 PASSED

\- `GET /health` — 200

\- `GET /api/schema/` — 200

\- `GET /api/docs/` — 200

\- Development server — PASS



\### Migration State (updated in CP2)



CP2 completed everything that does NOT require a live database connection:



\- `accounts` app created, `apps.accounts.User` model defined

\- `AUTH\_USER\_MODEL = "accounts.User"` configured in `base.py`

\- `apps/accounts/migrations/0001\_initial.py` generated and inspected — creates

  the custom `User` table, depends on `auth.0012\_alter\_user\_first\_name\_max\_length`

  (needed for the `groups`/`user\_permissions` M2M fields), correctly includes

  the `Lower(email)` unique constraint and the custom manager

\- `manage.py makemigrations --check --dry-run` → \*\*No changes detected\*\*



\*\*`migrate` has NOT been run — BLOCKED, not by choice.\*\*



This environment has no PostgreSQL available at all (no local install, no

Windows service, no Docker, no WSL distro — verified, not assumed). Running

`migrate` fails with a real `psycopg.OperationalError` (connection refused on

127.0.0.1:5432). Per project rules, this was reported rather than bypassed —

no SQLite fallback was introduced, and no migration/test result was faked.



18 built-in Django migrations + 1 accounts migration (19 total) remain

unapplied, waiting on a real PostgreSQL instance.



Required sequence (steps 1–5 are DONE; step 6 is the current blocker):



1\. CP2 accounts app — DONE

2\. custom User — DONE

3\. `AUTH\_USER\_MODEL = "accounts.User"` — DONE

4\. accounts initial migration generated + inspected — DONE

5\. `makemigrations --check --dry-run` clean — DONE

6\. FIRST `migrate` — BLOCKED on PostgreSQL availability



This still prevents changing the Django user model after initial migrations —

that guarantee holds regardless of when `migrate` itself finally runs, because

`AUTH\_USER\_MODEL` was set and the migration was generated before any table

exists anywhere.

---

## CP2 — Accounts + Custom User

**Status:** PARTIAL / BLOCKED (model foundation complete and verified everywhere
that does not require a live database; `migrate` and the new tests are blocked
by a genuinely missing PostgreSQL instance in this environment, not by any
code problem)

### Files created

- `backend/apps/__init__.py`
- `backend/apps/accounts/__init__.py`
- `backend/apps/accounts/apps.py` — `AccountsConfig`, `name = "apps.accounts"`, `label = "accounts"`
- `backend/apps/accounts/managers.py` — `UserManager(BaseUserManager)`
- `backend/apps/accounts/models.py` — `User(AbstractBaseUser, PermissionsMixin)`
- `backend/apps/accounts/admin.py` — `UserAdmin(DjangoUserAdmin)`
- `backend/apps/accounts/migrations/__init__.py`
- `backend/apps/accounts/migrations/0001_initial.py` (generated, inspected, **not applied**)
- `backend/apps/accounts/tests/__init__.py`
- `backend/apps/accounts/tests/test_user_model.py` (15 tests)
- `backend/.venv/` (local virtual environment, gitignored — Python 3.13.7,
  packages installed exactly per `requirements.txt`)
- `backend/.env` (local secrets, gitignored, **not** committed, **not** printed
  anywhere in this document or in chat — contains a freshly generated
  `DJANGO_SECRET_KEY` and placeholder local Postgres credentials)

### Files modified

- `backend/config/settings/base.py` — added `apps.accounts` to `LOCAL_APPS`,
  added `AUTH_USER_MODEL = "accounts.User"` (placed here, not duplicated in
  `development.py`/`production.py`, because it is a project-wide identity
  choice true in every environment)

No other existing file was touched. **No frontend file was read, opened, or
modified.**

### User model fields

`id` (BigAutoField, implicit PK) · `email` (EmailField, `unique=True`, also
covered by a `Lower(email)` unique constraint — see "Architectural decisions")
· `password` (from `AbstractBaseUser`, always hashed) · `last_login` (from
`AbstractBaseUser`) · `first_name` · `last_name` · `role` (CharField + choices,
default `EMPLOYEE`, `db_index=True`) · `is_active` (default `True`) ·
`is_staff` (default `False`) · `is_superuser` (from `PermissionsMixin`) ·
`groups` / `user_permissions` (from `PermissionsMixin`) · `date_joined`
(default `timezone.now`) · `updated_at` (`auto_now=True`).

### Role choices

`User.Role` (`TextChoices`): `SUPER_ADMIN`, `MANAGER`, `EMPLOYEE`. Default for
every user created via `create_user()` is `EMPLOYEE`. This is identity-only —
no permission/queryset logic reads this field yet; that begins at CP6.

### UserManager behavior

- `create_user(email, password, **extra_fields)` — requires and normalizes
  email (lowercased), rejects a blank email, hashes the password via
  `set_password()`, runs `full_clean(exclude=["password"])` for field-level
  validation, and explicitly **refuses** to create a Django staff/superuser
  (raises `ValueError` if `is_staff`/`is_superuser` is passed as `True`).
- `create_superuser(email, password, **extra_fields)` — same base creation
  path, but requires `is_staff=True` and `is_superuser=True` (defaults them,
  but rejects an explicit `False` for either — a caller mistake fails loudly
  instead of silently creating a half-privileged account).
- No custom password hashing was invented; `set_password()` uses Django's
  configured hasher (PBKDF2 by default) exactly as required.

### AUTH_USER_MODEL configuration

`AUTH_USER_MODEL = "accounts.User"` in `config/settings/base.py`, set before
any migration exists — the required ordering for a custom user model.

### Model invariant (role vs. Django privilege)

`User.save()` forces `role = SUPER_ADMIN` whenever `is_superuser` is `True`.
This is a one-directional promotion — it never demotes or otherwise touches
`role` for a non-superuser — so a Django superuser can never end up
contradictorily tagged `EMPLOYEE`/`MANAGER`, while `MANAGER`/`EMPLOYEE` users
remain completely free to exist with zero Django admin privileges (the normal
case for every real CRM user).

### Admin registration

`UserAdmin(DjangoUserAdmin)` registered for the custom model: email-based
`ordering`, `list_display`/`list_filter`/`search_fields` adapted for
email + role, `add_fieldsets` using Django's `password1`/`password2`
confirm-password widgets (never a raw editable password field), and the
inherited `ReadOnlyPasswordHashField` behavior for the change form — so a
password hash is visible only as a non-editable, non-reversible display, never
as plaintext or an editable value.

### Migration created

`apps/accounts/migrations/0001_initial.py` — creates the `accounts_user`
table with every field above, the `Lower(email)` unique constraint, the
`groups`/`user_permissions` M2M tables, and depends on
`auth.0012_alter_user_first_name_max_length` (required because those M2M
fields reference `auth.Group`/`auth.Permission`). Inspected manually — matches
the model exactly. Confirmed via `makemigrations --check --dry-run` → **No
changes detected**.

### Migration applied

**NO.** Blocked — see "Problems encountered" below. This is the only
incomplete step in the required CP2 sequence.

### Exact verification results (all actually executed)

```
manage.py check
    System check identified no issues (0 silenced).

manage.py makemigrations accounts
    Migrations for 'accounts':
      apps\accounts\migrations\0001_initial.py
        + Create model User
    (RuntimeWarning about migration-history consistency check against the DB —
    expected/harmless with no DB reachable; does not affect file generation.)

manage.py makemigrations --check --dry-run
    No changes detected

manage.py migrate
    django.db.utils.OperationalError: connection failed: connection to
    server at "127.0.0.1", port 5432 failed: could not receive data from
    server: Socket is not connected (0x00002749/10057)
    -> BLOCKED, not faked, not bypassed.

manage.py runserver 8010
    Same OperationalError at startup (runserver's own check_migrations()
    step also requires a DB connection) -> live HTTP verification of
    /health, /api/schema/, /api/docs/ against a running server was not
    possible either, for the identical root cause.

get_user_model()
    <class 'apps.accounts.models.User'>
    USERNAME_FIELD = "email", REQUIRED_FIELDS = []
    Role.choices = [('SUPER_ADMIN', 'Super Admin'), ('MANAGER', 'Manager'),
                     ('EMPLOYEE', 'Employee')]
    (confirmed via django.setup(), no DB connection required)

settings.DATABASES['default']['ENGINE']
    django.db.backends.postgresql   (confirmed — still the only engine
    configured anywhere; no SQLite fallback was introduced)
```

### Exact test count/result

```
pytest -v
    3 passed   <- the original CP1 infrastructure tests (test_infrastructure.py),
                  re-run unchanged, still green: /health, /api/schema/, /api/docs/
    15 errors  <- the 15 new CP2 model/manager tests in test_user_model.py,
                  every one erroring at pytest-django's test-database setup
                  step (same OperationalError as `migrate`), NOT at any
                  assertion. No test logic has actually failed; none have
                  actually passed either. Recorded honestly as blocked, not
                  claimed as green.
```

### PostgreSQL state

Not installed anywhere on this machine. Verified by absence of: a `psql`
binary, a `postgresql*` Windows service, a `docker` command, and any WSL
distribution. `backend/.env` is configured and ready (`DB_NAME=crm_db`,
`DB_USER=crm_dev`, `DB_HOST=localhost`, `DB_PORT=5432`) so that the moment a
real PostgreSQL server is reachable at those coordinates, `migrate` and the
full test suite can be run with no further code changes.

### Architectural decisions

- **`AbstractBaseUser` + `PermissionsMixin`** over Django's default concrete
  `User` — required to use email as the login identity and to add the CRM's
  own field set without carrying unused fields (`username`) forward.
- **Email uniqueness, defended twice.** `email` keeps `unique=True` (this is
  also what satisfies Django's own system check requiring `USERNAME_FIELD` to
  be unique) *and* the model adds a `models.UniqueConstraint(Lower("email"))`.
  Because `User.save()` and `UserManager` both always lowercase the email
  before writing, the plain `unique=True` index already behaves
  case-insensitively in practice — the functional constraint is a second,
  database-level guarantee that holds even if some future code path (a data
  migration, a raw insert) ever bypassed that normalization. Two indexes on
  one column is a small, deliberate cost for that guarantee.
- **`create_user()` cannot mint Django staff/superuser access**, even if a
  caller passes `is_staff=True`/`is_superuser=True` — it raises instead. Only
  `create_superuser()` can grant those flags, and it validates them the other
  direction (rejects an explicit `False`). This keeps the two creation paths
  from ever producing a half-privileged, ambiguous account.
- **Role vs. Django privilege invariant** lives in `User.save()`, not in the
  manager — so it also protects any future code path that saves a `User`
  outside the manager (e.g. an admin form, a data-migration script), not only
  `create_user`/`create_superuser`.
- **`full_clean(exclude=["password"])` inside the manager** — an intentional
  addition beyond Django's default `UserManager` pattern, to satisfy "identity
  fields are validated" as a manager-level guarantee rather than relying only
  on admin-form validation.
- **`apps.accounts`, not a top-level `accounts` package** — keeps all future
  domain apps (`leads`, `customers`, `payments`, …) grouped under one
  `backend/apps/` namespace instead of scattering top-level packages next to
  `config/`. `AppConfig.label` is set explicitly to `"accounts"` so
  `AUTH_USER_MODEL = "accounts.User"` and the migration app-label stay short
  and match the checkpoint spec exactly.

### Deferred to later checkpoints (intentionally NOT built in CP2)

- JWT / login / logout / refresh tokens (CP3)
- Super Admin secret access-code field/flow (CP4)
- Device/session authorization, mobile blocking (CP5)
- Manager → Employee hierarchy fields, full RBAC, row-level data scope (CP6)
- Any User serializer (no endpoint needs one yet; deferred rather than
  speculatively built)

### Confirmation frontend was untouched

**Confirmed.** No file under the frontend (`app/`, components, hooks, styles,
package files) was opened, read, or modified during CP2. `git status` at the
end of this checkpoint shows changes scoped entirely to `backend/`.

### Problems encountered

**PostgreSQL is not available anywhere on this machine.** No local install, no
Windows service, no Docker, no WSL distribution. This was discovered at the
start of CP2 (before any model code was written) and the user was asked how to
proceed; the explicit decision was: **complete every step that does not
require a live database now, and defer/report `migrate`, the new tests, and
live-server verification as blocked** rather than installing PostgreSQL
system-wide unilaterally or introducing a SQLite fallback. That decision is
reflected in this checkpoint's PARTIAL/BLOCKED status. Once PostgreSQL is
reachable at the coordinates already configured in `backend/.env`, the
remaining sequence is exactly: `manage.py migrate` → `pytest -v` → runtime
HTTP re-verification — no further code changes are anticipated.

---

## CP3 — Authentication / JWT

**Status:** PARTIAL / BLOCKED (implementation complete and verified everywhere
that does not require a live database; `migrate` and the 28 new tests remain
blocked by the same missing-PostgreSQL environment issue as CP2)

### Files created

- `backend/apps/accounts/serializers.py` — `UserSerializer`, `LoginSerializer`, `LogoutSerializer`
- `backend/apps/accounts/views.py` — `LoginView`, `MeView`, `LogoutView`
- `backend/apps/accounts/urls.py` — the 4 CP3 routes (mounts SimpleJWT's own `TokenRefreshView` for `/refresh/`)
- `backend/apps/accounts/tests/test_auth.py` — 28 tests

### Files modified

- `backend/requirements.txt` — added `djangorestframework-simplejwt==5.3.1`
- `backend/config/settings/base.py` — added `rest_framework_simplejwt.token_blacklist`
  to `THIRD_PARTY_APPS`; added `JWTAuthentication` to
  `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` (global default —
  `DEFAULT_PERMISSION_CLASSES` stays `AllowAny`, unchanged from CP1/CP2, so
  every existing public endpoint is unaffected); added the `SIMPLE_JWT`
  settings block
- `backend/config/urls.py` — mounted `path("api/v1/auth/", include("apps.accounts.urls"))`

No other existing file was touched. **No frontend file was read, opened, or
modified.**

### Dependencies added

`djangorestframework-simplejwt==5.3.1` (pulls in `pyjwt` transitively — left
unpinned in `requirements.txt`, matching this project's existing convention
of pinning only direct dependencies). No Redis, no Celery.

### Database / migration changes

`rest_framework_simplejwt.token_blacklist` was added to `INSTALLED_APPS`. Its
`OutstandingToken`/`BlacklistedToken` migrations ship inside the installed
package itself (nothing was generated by `makemigrations` for it — doing so
would have been wrong per this checkpoint's rules). `manage.py makemigrations
--check --dry-run` confirms **No changes detected**, i.e. our own `accounts`
app model is still fully captured by its existing CP2 migration and nothing
new needs generating. Applying `token_blacklist`'s shipped migrations still
requires `manage.py migrate` to actually run, which remains blocked — see
"Problems encountered".

### Endpoints

All mounted under `/api/v1/auth/`:

| Method | Path                    | Auth required | Purpose |
|--------|-------------------------|----------------|---------|
| POST   | `/api/v1/auth/login/`   | No             | email+password -> access + refresh + safe user info |
| POST   | `/api/v1/auth/refresh/` | No (refresh token in body) | refresh -> new access (+ new refresh, rotation enabled) |
| POST   | `/api/v1/auth/logout/`  | No (refresh token in body) | blacklist a refresh token |
| GET    | `/api/v1/auth/me/`      | Yes (Bearer access token) | the authenticated user's safe identity info |

CP1's `/health`, `/api/schema/`, `/api/docs/` are unchanged and still pass —
see "CP1 regression" below.

### Authentication

- Login validates credentials via Django's own `authenticate()` (which routes
  to `ModelBackend`, which calls `user.check_password()` — no manual hash
  comparison anywhere, and `is_active=False` users are excluded from a
  successful result by Django itself).
- Tokens are issued/verified by `djangorestframework-simplejwt`, signed with
  `SECRET_KEY` (already environment-sourced since CP1 — no second secret was
  introduced).
- `ACCESS_TOKEN_LIFETIME = 15 minutes`, `REFRESH_TOKEN_LIFETIME = 7 days`,
  `ROTATE_REFRESH_TOKENS = True`, `BLACKLIST_AFTER_ROTATION = True` — every
  refresh both rotates and single-uses the refresh token. Full reasoning in
  `BACKEND_LEARNING_GUIDE.md` CP3.
- Invalid credentials (wrong password, nonexistent email, inactive account)
  all return the **identical** 401 body — account existence and the
  wrong-field are never revealed (tested explicitly).
- Logout blacklists the presented refresh token via SimpleJWT's blacklist
  app; no custom session table was introduced.
- The Super Admin secondary access-code challenge is explicitly **NOT**
  implemented here — a `SUPER_ADMIN` logs in through the identical base
  email/password flow as any other role in CP3. That is deliberate and
  deferred to CP4; see the CP3 section of `BACKEND_LEARNING_GUIDE.md`.

### Migration

Same status as CP2: generated migrations are correct and complete
(`makemigrations --check --dry-run` -> "No changes detected"), but `manage.py
migrate` itself has **NOT** been run — blocked by the same missing
PostgreSQL instance. See "Problems encountered".

### Database

PostgreSQL remains the only configured engine (confirmed again:
`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`).
No SQLite fallback was introduced. Still no live PostgreSQL server reachable
on this machine.

### Tests

`apps/accounts/tests/test_auth.py` — 28 tests covering login (valid, wrong
password, nonexistent email, inactive user, missing email, missing password,
malformed email, response never contains password), refresh (success,
invalid, malformed, missing, blacklisted, rotation-reuse-rejected, refresh
token rejected by a protected endpoint), `/me/` (valid token, no token,
malformed token, correct fields, no sensitive fields), logout (valid, token
becomes unusable, missing token, invalid token, already-blacklisted token),
and login for all three roles (`EMPLOYEE`/`MANAGER`/`SUPER_ADMIN`).

All 28 require `pytest.mark.django_db` (token blacklisting writes real rows)
and currently **error** at pytest-django's test-database creation step — the
same `OperationalError` as `migrate`, not an assertion failure. Recorded
honestly as blocked, not claimed as passing.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3 passed, unchanged. Also
confirmed via `manage.py spectacular --file` that schema generation still
succeeds and includes `/health` alongside the new CP3 routes without error.

### CP2 regression

**Blocked, same as CP2 itself.** `apps/accounts/tests/test_user_model.py`'s
15 tests still error at the identical DB-unavailability step — not a new
regression introduced by CP3, the same pre-existing CP2 blocker.

### OpenAPI

Verified directly (`manage.py spectacular --file`): all 4 CP3 routes appear
in the generated schema. drf-spectacular auto-detected
`JWTAuthentication` and registered a `bearerAuth` (`type: http, scheme:
bearer, bearerFormat: JWT`) security scheme with **zero extra configuration**
— confirmed empirically, not assumed. `/api/v1/auth/me/` shows `security: -
jwtAuth: []` in the schema (protected); `/login/`, `/refresh/`, `/logout/`
show `security: - {}` (public) — exactly matching each view's
`permission_classes`/`authentication_classes`.

### Security checks performed

- Login/`/me/` responses inspected for the literal string "password" and for
  the actual password hash value — absent in both.
- `/me/` response keys asserted to be exactly `{id, email, first_name,
  last_name, role}` — no extra fields leak through.
- Wrong-password and nonexistent-email responses asserted **byte-for-byte
  identical** (status + body) — no account-enumeration signal.
- A refresh token used as a Bearer access token against `/me/` is rejected
  (SimpleJWT's token-type claim check) — refresh tokens cannot double as
  access tokens.
- A blacklisted/rotated-away refresh token is rejected by both `/refresh/`
  and a second `/logout/` call.
- Inactive users (`is_active=False`) cannot obtain tokens — enforced by
  Django's own `ModelBackend`, not custom code.

### Architectural decisions

- **Login/logout live in `apps/accounts`**, not a new top-level `auth` app —
  CP2 already established `accounts` as the identity app, and login/logout
  are tightly coupled to `User`; a separate app would just add
  cross-app-import overhead for no isolation benefit at this size.
- **`/refresh/` uses SimpleJWT's own `TokenRefreshView` directly**, not a
  custom wrapper — it already implements exactly what STEP 5 required
  (rotation, blacklist-on-rotation, rejecting invalid/expired/blacklisted
  tokens), and re-implementing verified library behavior would only add risk.
- **Authentication logic lives in `LoginSerializer.validate()`**, not the
  view — DRF serializers are the conventional home for request-level
  business validation; the view stays a thin
  validate-then-issue-tokens-then-respond orchestrator.
- **`UserSerializer` is an explicit allowlist** (`fields = [...]`), not
  `exclude = [...]` — an allowlist can never accidentally leak a field added
  to the model later (e.g. a future CP4/CP5 field); an excludelist would.
- **`DEFAULT_PERMISSION_CLASSES` was left as `AllowAny`** rather than
  switched to `IsAuthenticated` globally — CP1's `/health` and CP3's own
  `/login/`/`/refresh/`/`/logout/` must stay public. Only `/me/` opts into
  `IsAuthenticated` on itself. A global switch to `IsAuthenticated` is
  exactly the kind of change CP6 (RBAC) will make deliberately, once there
  are protected domain endpoints to actually guard.

### Deferred to later checkpoints (intentionally NOT built in CP3)

- Super Admin secondary access-code verification (CP4)
- Device/session authorization, desktop-only enforcement (CP5)
- Full RBAC, hierarchy-aware permissions, row-level data scope (CP6)
- Any domain endpoint (leads, customers, ...) — CP7+

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Identical root cause to CP2: **no PostgreSQL instance exists anywhere on this
machine** (same verification repeated for CP3: no `psql`, no Windows
service, no Docker, no WSL). `manage.py migrate` was attempted and produced
the same `psycopg.OperationalError` as CP2. Per this checkpoint's explicit
"Database Unavailable Rule," no SQLite fallback was introduced, no
migration/test result was faked, and every step achievable without a live
database was completed and actually verified instead (`check`,
`makemigrations --check --dry-run`, `get_user_model()`, the DB engine check,
and full OpenAPI schema generation and inspection). This checkpoint's status
is recorded as PARTIAL/BLOCKED, not COMPLETE, consistent with the Mandatory
Checkpoint Protocol.

---

## CP4 — Super Admin Secondary Access-Code Authentication

**Status:** PARTIAL / BLOCKED (implementation complete; 19 tests genuinely
pass with no database at all — 3 CP1 + 16 new CP4 model/signing tests — while
`migrate` and the 75 total DB-dependent tests, CP2+CP3+CP4 combined, remain
blocked by the same missing-PostgreSQL environment issue)

### Files created

- `backend/apps/accounts/challenge.py` — `issue_super_admin_challenge()`, `read_super_admin_challenge()`
- `backend/apps/accounts/migrations/0002_user_super_admin_access_code_hash.py`
- `backend/apps/accounts/tests/test_super_admin_access_code.py` — 16 tests (no DB required — **genuinely passing**)
- `backend/apps/accounts/tests/test_super_admin_auth.py` — 32 tests (DB required — blocked)

### Files modified

- `backend/apps/accounts/models.py` — added `super_admin_access_code_hash`
  field, `set_access_code()`/`check_access_code()` methods, and a `save()`
  invariant clearing the hash for any non-SUPER_ADMIN role
- `backend/apps/accounts/serializers.py` — added `LoginSuccessSerializer`,
  `SuperAdminChallengeSerializer` (output-only, for OpenAPI), and
  `SuperAdminVerifySerializer`
- `backend/apps/accounts/views.py` — `LoginView` now branches on role for
  SUPER_ADMIN; added `SuperAdminVerifyView`; added a shared
  `_issue_token_pair_response()` helper
- `backend/apps/accounts/urls.py` — added `POST /super-admin/verify/`
- `backend/apps/accounts/admin.py` — documented (comment only) why the
  access-code hash is absent from every admin fieldset
- `backend/config/settings/base.py` — added `SUPER_ADMIN_CHALLENGE_TTL_SECONDS
  = 300`; added `DEFAULT_THROTTLE_RATES = {"super_admin_verify": "5/min"}`
  (scoped — does not affect any other endpoint)

No other existing file was touched. **No frontend file was read, opened, or
modified.**

### Model changes

`accounts.User` gained one field: `super_admin_access_code_hash` (CharField,
`max_length=128`, `blank=True`, `default=""`). Storage/verification go
through exactly two new model methods — `set_access_code(raw_code)` (hashes
via `django.contrib.auth.hashers.make_password`, same machinery as the
primary password) and `check_access_code(raw_code)` (verifies via
`check_password`; fails closed — returns `False`, never raises — for an
empty submission, a not-yet-configured code, or any role other than
SUPER_ADMIN). The raw code is never assigned to any attribute and does not
persist past `set_access_code()` returning.

### Migration

`apps/accounts/migrations/0002_user_super_admin_access_code_hash.py` —
a single, purely-additive `AddField` operation, depending on `accounts.0001_initial`.
Inspected by hand: matches the model exactly, correct default (`""`, not
`None`), no other changes. `makemigrations --check --dry-run` → **No changes
detected**. **Not applied** — same PostgreSQL blocker as CP2/CP3.

### Endpoints

| Method | Path | Auth required | CP4 change |
|---|---|---|---|
| POST | `/api/v1/auth/login/` | No | **Behavior change for SUPER_ADMIN only** — returns `{secondary_verification_required: true, challenge}` instead of tokens |
| POST | `/api/v1/auth/super-admin/verify/` | No (challenge + code in body) | **New.** challenge + access code -> access + refresh + user |
| POST | `/api/v1/auth/refresh/` | No (refresh token in body) | Unchanged |
| POST | `/api/v1/auth/logout/` | No (refresh token in body) | Unchanged |
| GET | `/api/v1/auth/me/` | Yes (Bearer access token) | Unchanged |

EMPLOYEE/MANAGER login is byte-for-byte the same CP3 response shape it
always was — verified directly (`test_employee_login_unchanged`,
`test_manager_login_unchanged`).

### Authentication flow

```
EMPLOYEE / MANAGER:  email+password -> access + refresh (unchanged CP3 flow)

SUPER_ADMIN:  email+password -> primary credentials valid
                              -> challenge (signed, 5-minute TTL, NOT a JWT)
                              -> POST /super-admin/verify/ {challenge, access_code}
                              -> access + refresh (ordinary SimpleJWT tokens —
                                 same refresh/blacklist/logout lifecycle as
                                 anyone else's, verified by
                                 test_super_admin_full_lifecycle_refresh_and_logout)
```

The challenge token is built on `django.core.signing` (not SimpleJWT),
carries only `{"user_id": ...}`, is cryptographically signed with
`SECRET_KEY` (no second secret introduced), and is structurally incapable of
being accepted as a Bearer access token or a refresh token — confirmed by
both the pure signing tests and the DB-backed token-separation tests.

### Security

- Raw access code never stored, never logged, never returned by any
  endpoint, never placed in a JWT claim, and never hardcoded anywhere in the
  codebase (verified: `grep` for hardcoded-secret patterns across
  `apps/accounts/` found nothing).
- Access code stored only as a `make_password()` hash;
  `super_admin_access_code_hash` is absent from `UserSerializer`'s allowlist
  (confirmed directly: `test_access_code_hash_never_appears_in_user_serializer`)
  and absent from every Django admin fieldset (by omission, not a hidden
  field).
- `check_access_code()` fails closed for a non-SUPER_ADMIN, an unconfigured
  code, and an empty submission alike — verified.
- The verify endpoint gives **one identical error** ("Invalid or expired
  challenge.") for every challenge-level failure (malformed, tampered,
  expired, unknown user, inactive user, role no longer SUPER_ADMIN) and a
  **separate** identical error ("Invalid access code.") for a wrong code
  *or* a not-configured code — no signal about which specific sub-case
  occurred, and no signal about "closeness" of a wrong code.
- `SuperAdminVerifyView` carries `throttle_scope = "super_admin_verify"`
  (`DEFAULT_THROTTLE_RATES: 5/min`) via DRF's `ScopedRateThrottle`. This uses
  Django's default in-process `LocMemCache` — a real speed bump today, but
  explicitly **not** a production-grade/distributed brute-force defense (it
  resets on process restart and does not share state across multiple
  workers/machines). Documented as a seam for CP17 (deployment hardening) to
  replace with a shared cache. Not claimed to be more than it is.
- Inactive users, and users whose role changed after the challenge was
  issued, are both re-checked at verify time (not just at login time).

### Tests

**No database required — genuinely executed, genuinely passing:**
`apps/accounts/tests/test_super_admin_access_code.py` — 16/16 passed. Covers
`set_access_code`/`check_access_code` (hash-not-raw, empty rejection,
correct/wrong/unconfigured/wrong-role verification, code rotation
invalidating the old code, absence from `UserSerializer`) and the challenge
helpers (issue/read round-trip, non-JWT shape, no secret material in the
payload, malformed/tampered/expired rejection, salt namespacing).

**Requires database — blocked:** `apps/accounts/tests/test_super_admin_auth.py`
— 32 tests covering every scenario in STEP 12 (normal-user regression,
Super-Admin primary login, the verify endpoint's success/failure matrix,
token-type separation, and the full verify -> refresh -> logout lifecycle).
All 31 error at pytest-django's test-database creation step — the same
`OperationalError` as `migrate`, zero assertion failures.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 regression

**Blocked**, same pre-existing cause (not a new CP4 regression). 15 tests in
`test_user_model.py` still error at DB setup, identically to CP2/CP3's own
reports.

### CP3 regression

**Blocked**, same pre-existing cause (not a new CP4 regression). 28 tests in
`test_auth.py` still error at DB setup. **CP3's historical status is
unchanged and is NOT being upgraded to VERIFIED by CP4's work** — its
PostgreSQL-backed `migrate`/tests still have not actually run successfully
on this machine.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again (no SQLite fallback introduced). No live PostgreSQL server
reachable on this machine — identical root cause to CP2/CP3, re-verified (no
`psql`, no Windows service, no Docker, no WSL).

### OpenAPI

Verified directly (`manage.py spectacular --file`): `/api/v1/auth/login/`'s
response is documented as a `LoginResponse` component with `oneOf:
[LoginSuccess, SuperAdminChallenge]` (via `PolymorphicProxySerializer`), and
`/api/v1/auth/super-admin/verify/` is documented with the same
`LoginSuccessSerializer` response shape as a successful login. `/api/schema/`
and `/api/docs/` continue to work (confirmed via the still-passing CP1
infrastructure tests).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed. No
`package.json`/`package-lock.json` touched.

### Problems encountered

Identical root cause to CP2/CP3: no PostgreSQL instance exists anywhere on
this machine (re-verified for CP4, same result). Per the Database Unavailable
Rule, no SQLite fallback was introduced, no migration/test result was faked.
Unlike CP2/CP3, CP4 was able to produce a meaningful set of *actually
executed and passing* tests (16) by isolating the pure hashing/signing logic
from anything requiring a live database — a pattern future checkpoints could
reuse where applicable.

### Deferred

- Device/session authorization (CP5)
- Full RBAC, hierarchy-aware permissions, row-level data scope (CP6)
- Any domain endpoint (leads, customers, ...) — CP7+
- Production-grade, distributed rate limiting for the verify endpoint (CP17,
  deployment hardening — see "Security" above)
- A management command or admin-site flow for setting a Super Admin's access
  code was intentionally NOT built — `set_access_code()` exists as the
  secure primitive; a convenient way to invoke it operationally is left to
  whichever future checkpoint actually needs one (STEP 4 explicitly asked
  for the model/service method, not a frontend or admin UI)

### Next

CP5 — Device / Session Authorization (blocked behind the same PostgreSQL
issue affecting CP2/CP3/CP4's DB-dependent verification)

---

## CP5 — Device / Session Authorization

**Status:** PARTIAL / BLOCKED (implementation complete; 35 tests genuinely
pass with no database at all — 3 CP1 + 16 CP4 + 16 CP5 model/parsing tests —
while `migrate` and the 103 total DB-dependent tests, CP2+CP3+CP4+CP5
combined, remain blocked by the same missing-PostgreSQL environment issue)

### Files created

- `backend/apps/accounts/session_utils.py` — `get_client_ip()`, `parse_user_agent()`, `build_device_name()` (no DB — **genuinely passing**, 16 tests)
- `backend/apps/accounts/services.py` — `create_session()`, `touch_session_on_refresh()`, `blacklist_by_jti()`, `deactivate_session_by_jti()`, `revoke_session()`, `revoke_all_sessions_except()`
- `backend/apps/accounts/migrations/0003_usersession.py`
- `backend/apps/accounts/tests/test_session_utils.py` — 16 tests (no DB required — **genuinely passing**, and caught a real bug during this checkpoint, see "Problems encountered")
- `backend/apps/accounts/tests/test_sessions.py` — 28 tests (DB required — blocked)

### Files modified

- `backend/apps/accounts/models.py` — added `UserSession` model
- `backend/apps/accounts/serializers.py` — added `UserSessionSerializer`,
  `RevokeAllResponseSerializer`; `LogoutSerializer.save()` now also
  deactivates the matching session
- `backend/apps/accounts/views.py` — `_issue_token_pair_response()` now
  accepts `request`, embeds a `session_jti` claim on the access token, and
  creates a `UserSession`; added `SessionAwareTokenRefreshView`,
  `SessionListView`, `SessionRevokeView`, `LogoutAllView`
- `backend/apps/accounts/urls.py` — `/refresh/` now routes to
  `SessionAwareTokenRefreshView`; added `/sessions/`, `/sessions/<id>/`,
  `/logout-all/`

No other existing file was touched. **No frontend file was read, opened, or
modified.**

### Model changes

New model `UserSession`: `id`, `user` (FK, `CASCADE`), `refresh_token_jti`
(unique), `device_name`, `device_type` (choices), `browser`,
`operating_system`, `ip_address`, `user_agent`, `created_at`
(`auto_now_add`), `last_used_at`, `expires_at`, `is_active`. Indexes on
`user`, `refresh_token_jti`, `is_active`, `created_at` as required. Never
stores the refresh token itself, only its JTI.

### Migration

`apps/accounts/migrations/0003_usersession.py` — a single `CreateModel`
operation, depending on `accounts.0002_user_super_admin_access_code_hash`.
Inspected by hand: all fields, the FK, and all four required indexes present
and correct. `makemigrations --check --dry-run` → **No changes detected**.
**Not applied** — same PostgreSQL blocker as CP2/CP3/CP4.

### Endpoints

| Method | Path | Auth required | CP5 change |
|---|---|---|---|
| POST | `/api/v1/auth/login/` | No | Now also creates a `UserSession` (for EMPLOYEE/MANAGER; SUPER_ADMIN still only gets a challenge) |
| POST | `/api/v1/auth/super-admin/verify/` | No | Now also creates a `UserSession` on success |
| POST | `/api/v1/auth/refresh/` | No | Now routes through `SessionAwareTokenRefreshView` — updates `last_used_at` and the tracked JTI |
| POST | `/api/v1/auth/logout/` | No | Now also deactivates the matching `UserSession` |
| GET | `/api/v1/auth/sessions/` | Yes | **New.** The caller's own active sessions |
| DELETE | `/api/v1/auth/sessions/<id>/` | Yes | **New.** Revokes one of the caller's own sessions |
| POST | `/api/v1/auth/logout-all/` | Yes | **New.** Revokes every other active session for the caller |
| GET | `/api/v1/auth/me/` | Yes | Unchanged |

### Security

- `UserSessionSerializer` is an explicit allowlist: `id`, `device_name`,
  `device_type`, `browser`, `operating_system`, `created_at`, `last_used_at`,
  `current_session`. `refresh_token_jti`, `user`, `user_agent`, and
  `ip_address` are never serialized — confirmed directly
  (`test_list_sessions_response_never_contains_sensitive_fields` checks the
  raw response body for the JTI, the actual token strings, "password", and
  "access_code").
- `SessionListView`/`SessionRevokeView` both scope their queryset to
  `request.user` with **no role-based exception** — a `SUPER_ADMIN` sees and
  can revoke only their own sessions through these endpoints, exactly like
  an `EMPLOYEE`/`MANAGER` (verified directly:
  `test_super_admin_cannot_bypass_session_ownership`). Attempting to revoke
  another user's session returns 404, not a distinguishable 403 — existence
  of another user's session ID is never confirmed or denied.
- `LogoutAllView` never revokes the session making the current request —
  identified via a `session_jti` claim embedded on the access token at issue
  time, not by trusting any client-supplied identifier.
- Refresh rotation continues to update (not duplicate) the tracked session,
  so a compromised/stale refresh token being rejected by rotation's own
  blacklist-after-rotation (CP3) is reflected in the session list too.

### Tests

**No database required — genuinely executed, genuinely passing:**
`apps/accounts/tests/test_session_utils.py` — 16/16 passed. Covers
user-agent parsing (Chrome/Firefox/Safari/Edge/Opera, Windows/macOS/Linux/
Android/iOS, desktop/mobile/tablet, and browsers that impersonate other
browsers in their UA string), device-name building, and IP extraction
(`X-Forwarded-For` vs `REMOTE_ADDR`, whitespace handling, `None` safety).

**Requires database — blocked:** `apps/accounts/tests/test_sessions.py` — 28
tests covering every scenario asked for: login creates a session, refresh
updates `last_used_at` and rotates the tracked JTI (not a new row), logout
deactivates the session and blacklists its token, `logout-all` revokes every
other session but preserves the current one, deleting one session revokes
it, permission checks (401 without auth), cross-user access denied (404, not
403), multiple simultaneous devices produce separate session rows, and
`SUPER_ADMIN` compatibility (creates a session only after CP4 verification,
and is subject to the identical ownership rules as any other role). All 28
error at pytest-django's test-database creation step — the same
`OperationalError` as `migrate`, zero assertion failures.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 regression

**Blocked**, same pre-existing cause (not a new CP5 regression). Their
DB-backed tests (15 + 28 + 32) still error at DB setup, identically to their
own prior reports. **None of their statuses were upgraded to VERIFIED** by
CP5's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2/CP3/CP4, re-verified.

### OpenAPI

Verified directly (`manage.py spectacular --file`): all three new endpoints
appear in the generated schema, correctly marked as requiring `jwtAuth`.
Fixed two drf-spectacular warnings and one error surfaced during generation
(none were functional bugs — see "Problems encountered"); after the fix,
schema generation produces zero warnings and zero errors. `/api/schema/` and
`/api/docs/` continue to work (confirmed via the still-passing CP1
infrastructure tests).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2/CP3/CP4 (re-verified: no `psql`, no service,
no Docker, no WSL). No SQLite fallback, no faked result.

Two smaller, real issues were found and fixed **during** this checkpoint,
both before any DB-dependent step was needed:

1. **A genuine parsing bug**, caught by `test_session_utils.py` (which does
   not need a database and therefore actually ran): iPhone/iPad user-agent
   strings contain the literal substring "like Mac OS X" for legacy
   compatibility, which was matching the macOS check before the iOS check,
   misreporting every iPhone/iPad as a Mac. Fixed by reordering the checks so
   iOS is tested first. This is direct evidence of the value of writing
   DB-independent tests where possible (CP4's pattern, continued here) — a
   real bug was caught and fixed by an actually-executed test, not merely
   asserted-safe by inspection.
2. **Schema-generation warnings/error** (not functional bugs): `LogoutAllView`
   needed `request=None` in its `@extend_schema` (it has no request body);
   `SessionListView.get_queryset()` crashed against drf-spectacular's fake
   introspection request (fixed with a standard `swagger_fake_view` guard);
   `UserSessionSerializer.get_current_session()` needed a `-> bool` return
   hint. All three fixed; schema generation is now clean.

### Deferred

- Full RBAC, hierarchy-aware permissions, row-level data scope (CP6)
- Any domain endpoint (leads, customers, ...) — CP7+
- Actual device/mobile *blocking* (rejecting a login from a disallowed
  device class outright) was NOT implemented — CP5 as scoped here is device
  *session tracking and revocation*, not device *restriction policy*. If the
  client's "desktop-only CRM" requirement needs enforcement at login time
  rather than only visibility/revocation after the fact, that policy
  decision belongs to a dedicated follow-up (most naturally alongside CP6's
  permission work, since it's an authorization-adjacent policy, not
  authentication).
- A comprehensive user-agent database (e.g. the `user-agents` PyPI package)
  was deliberately not added — the heuristic parser in `session_utils.py`
  covers mainstream browsers/platforms well enough for a session list;
  upgrading it is a low-risk, isolated change if ever needed.

### Next

CP6 — Hierarchy + RBAC (blocked behind the same PostgreSQL issue affecting
CP2/CP3/CP4/CP5's DB-dependent verification)

---

## CP6 — Role-Based Access Control (RBAC)

**Status:** PARTIAL / BLOCKED (implementation complete; 59 new tests
genuinely pass with no database at all, bringing the running no-DB total to
94 — 3 CP1 + 16 CP4 + 16 CP5 + 59 CP6 — while `migrate` and the 103 total
DB-dependent tests from CP2+CP3+CP4+CP5 remain blocked by the same
missing-PostgreSQL environment issue. This checkpoint added no new model, so
it introduces zero additional DB-dependent tests of its own.)

### Files created

- `backend/apps/accounts/permissions.py` — role hierarchy utilities
  (`ROLE_LEVELS`, `role_level()`, `role_at_least()`,
  `user_has_role_at_least()`, `is_super_admin()`) and permission classes
  `IsSuperAdmin`, `IsManager`, `IsEmployee`, `IsManagerOrSuperAdmin`,
  `ReadOnlyOrSuperAdmin`, `IsOwnerOrSuperAdmin`, plus the object-ownership
  helpers `resolve_owner()` and `manager_has_access()`
- `backend/apps/accounts/mixins.py` — `RolePermissionMixin`
  (declarative `required_role` on a view) and `ObjectOwnershipMixin`
  (prepends `IsOwnerOrSuperAdmin`)
- `backend/apps/accounts/tests/test_permissions.py` — 59 tests (no DB
  required — **genuinely passing**)

### Files modified

None. CP6 is purely additive — no existing file needed a change to support
it. **No frontend file was read, opened, or modified.**

### Migration

**None required.** CP6 adds no new model and no new field to any existing
model — it is authorization infrastructure only, built entirely on
`User.role` (CP2). `makemigrations --check --dry-run` → **No changes
detected**, confirming this.

### Permission classes

| Class | Allows | Notes |
|---|---|---|
| `IsSuperAdmin` | `SUPER_ADMIN` only | Does not widen via hierarchy — nothing above it to inherit from |
| `IsManager` | `MANAGER`, `SUPER_ADMIN` | Hierarchy-based: "at least MANAGER" |
| `IsEmployee` | `EMPLOYEE`, `MANAGER`, `SUPER_ADMIN` | Hierarchy floor — any authenticated user |
| `IsManagerOrSuperAdmin` | `MANAGER`, `SUPER_ADMIN` | Explicit two-role union, not hierarchy-derived (see permissions.py docstring for why both this and `IsManager` exist) |
| `ReadOnlyOrSuperAdmin` | Any authenticated user reads; only `SUPER_ADMIN` writes | Uses `SAFE_METHODS` |
| `IsOwnerOrSuperAdmin` | The object's resolved owner, a `SUPER_ADMIN`, or a `MANAGER` with explicit per-object access | Object-level only (`has_object_permission`); `has_permission` just requires authentication |

`RolePermissionMixin` (in `mixins.py`) derives the correct permission class
from a `required_role = User.Role.X` view attribute, so a view doesn't have
to import a specific permission class by name. `ObjectOwnershipMixin`
prepends `IsOwnerOrSuperAdmin`. Both **prepend** to any existing
`permission_classes` rather than replacing them, so role and ownership
checks can be combined on one view.

### Hierarchy

`SUPER_ADMIN` (level 2) → `MANAGER` (level 1) → `EMPLOYEE` (level 0),
encoded as `ROLE_LEVELS` in `permissions.py`. `role_at_least(role, minimum)`
is the single function every hierarchy-aware check calls — a Manager
satisfies any Employee-level check, and a Super Admin satisfies every check
in the module, verified directly by
`test_role_hierarchy_matches_super_admin_inherits_everything` and
`test_role_hierarchy_matches_manager_inherits_employee_only`. Unrecognized
role values (e.g. `None`, a typo, an empty string) fail every check —
hierarchy comparisons fail closed, never open.

### Object-level permissions

`IsOwnerOrSuperAdmin.has_object_permission()`:

1. `SUPER_ADMIN` always passes (blanket override, no ownership check needed).
2. Otherwise, `resolve_owner(obj)` is tried — checks an `owner`, `user`, or
   `created_by` attribute (first one present), or treats `obj` itself as the
   owner if `obj` IS a `User` instance. If the resolved owner equals
   `request.user`, access is granted.
3. Otherwise, if the requester is at least `MANAGER`, a **per-object**
   `obj.manager_has_access(user)` method is called if the object defines
   one; if not, the module-level `manager_has_access(user, obj)` extension
   point is called (currently always returns `False` — CP6 introduces no
   team/hierarchy model for a Manager's "explicit access" to be derived
   from; see the function's docstring for how a future checkpoint should
   wire this up instead of monkey-patching it).
4. Otherwise denied.

This is deliberately convention-based rather than tied to any concrete
model, since CP6 is explicitly scoped to "no business modules yet."

### Utilities

`role_level()`, `role_at_least()`, `user_has_role_at_least()`,
`is_super_admin()`, `resolve_owner()`, and `manager_has_access()` are all
plain functions, independently unit-tested, and are the only place role
comparison / ownership resolution logic lives — no view in this checkpoint
(there are no new views) or any prior checkpoint's view hardcodes a role
string comparison; future checkpoints are expected to reuse these rather
than reimplementing `request.user.role == "..."` checks inline.

### Security

- Fails closed throughout: an anonymous/unauthenticated request, a `None`
  user, or an unrecognized role value is rejected by every permission class
  and every hierarchy utility — never silently allowed.
- `IsOwnerOrSuperAdmin` never guesses an owner: if none of `owner`/`user`/
  `created_by` is present and the object isn't a `User`, `resolve_owner()`
  returns `None`, and a non-Super-Admin, non-Manager-with-access requester
  is denied (verified by
  `test_is_owner_or_super_admin_denies_employee_with_no_resolvable_owner`).
  Only `SUPER_ADMIN` can pass with no resolvable owner at all.
- Owner comparison uses Django's `Model.__eq__` (pk-based equality), not
  Python object identity, so two separately-fetched instances of "the same"
  user row still compare equal (verified by
  `test_is_owner_or_super_admin_owner_check_uses_equality_not_identity`).
- Role checks deliberately do **not** duplicate `is_active` enforcement —
  that already happens earlier in the request lifecycle (SimpleJWT rejects
  an inactive user's token before any view's `permission_classes` run, per
  CP3) — documented and tested explicitly
  (`test_inactive_user_role_checks_do_not_special_case_is_active`) so a
  future reader doesn't assume it's a gap.
- No new endpoint, no new model, no new attack surface — this checkpoint is
  pure infrastructure not yet wired into any view, so there is nothing new
  reachable over HTTP.

### Tests

**No database required — genuinely executed, genuinely passing:**
`apps/accounts/tests/test_permissions.py` — 59/59 passed. Covers: role
hierarchy comparisons (full matrix of all 9 role×minimum combinations, plus
unrecognized-role edge cases), every permission class in isolation
(`IsSuperAdmin`, `IsManager`, `IsEmployee`, `IsManagerOrSuperAdmin`,
`ReadOnlyOrSuperAdmin` across all HTTP methods, `IsOwnerOrSuperAdmin`
including owner/non-owner/Super-Admin-override/Manager-without-access/
Manager-with-per-object-hook/no-resolvable-owner cases), `resolve_owner()`'s
attribute-preference order, `manager_has_access()`'s current always-False
behavior, both mixins (including that they prepend rather than replace
`permission_classes`, and that an unrecognized `required_role` raises
`ValueError`), and anonymous-vs-authenticated access on every class. All
operate on unsaved, in-memory `User` instances and lightweight dummy
request/view stand-ins — no database access anywhere in this file, following
the CP4/CP5 DB-free pattern.

**No new DB-dependent tests** — CP6 added no model, so there is nothing new
for `test_sessions.py`-style integration tests to cover yet; RBAC's
DB-backed behavior (permission classes actually gating a real endpoint
against real users) will be exercised once a future checkpoint wires these
classes into a business-module view.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 regression

**Blocked**, same pre-existing cause (not a new CP6 regression). Their
DB-backed tests (15 + 28 + 32 + 28 = 103) still error at DB setup,
identically to their own prior reports. Their DB-free tests (16 CP4 + 16
CP5 = 32) still pass, unchanged. **None of their statuses were upgraded to
VERIFIED** by CP6's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2/CP3/CP4/CP5, re-verified (`psql` not found, no
Windows service, no Docker, no WSL).

### OpenAPI

Verified directly (`manage.py spectacular --file`): schema generation still
succeeds with zero errors and zero warnings — unchanged from the end of CP5,
since CP6 added no view, serializer, or endpoint. All CP1–CP5 endpoints and
the CP4 challenge flow / CP5 session endpoints continue to appear correctly.

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2/CP3/CP4/CP5 (re-verified: no `psql`, no
service, no Docker, no WSL). No SQLite fallback, no faked result. No genuine
bugs were found during Phase 1 pre-implementation verification — every
CP1–CP5 endpoint, migration, serializer, JWT flow, session/challenge flow,
and the OpenAPI schema were confirmed intact before any CP6 code was
written. No genuine bugs were found in CP6's own implementation either; an
unused import (`user_has_role_at_least` in `mixins.py`, left over from an
earlier draft) was caught by IDE diagnostics and removed before it shipped.

### Deferred

- Wiring these permission classes into any actual business-module view —
  CP6 is infrastructure only, per its explicit scope ("No business modules
  yet"). CP7+ endpoints are expected to use `IsManager`,
  `IsOwnerOrSuperAdmin`, `RolePermissionMixin`, etc. directly.
- A real team/reporting-line model that would let `manager_has_access()`
  return `True` for an actual "this Manager has been explicitly granted
  access to this Employee's records" relationship — currently a documented
  extension point that always returns `False`.
- Device/mobile restriction *policy* (rejecting logins from a disallowed
  device class), still deferred from CP5, remains deferred — no checkpoint
  has claimed it yet.

### Next

CP7 (blocked behind the same PostgreSQL issue affecting CP2–CP6's
DB-dependent verification)

---

## CP7 — Core CRM Foundation

**Status:** PARTIAL / BLOCKED (implementation complete; 54 new tests
genuinely pass with no database at all, bringing the running no-DB total to
148 — 3 CP1 + 16 CP4 + 16 CP5 + 59 CP6 + 54 CP7 — while `migrate` and the
127 total DB-dependent tests (103 carried forward from CP2–CP5, plus 24 new
CP7 persistence round-trip tests) remain blocked by the same
missing-PostgreSQL environment issue.)

### Files created

- `backend/apps/core/__init__.py`, `apps.py` — new Django app, registered
  in `INSTALLED_APPS`
- `backend/apps/core/models.py` — `AuditModel`, `TimeStampedModel`,
  `SoftDeleteModel` (+ `SoftDeleteQuerySet`, `SoftDeleteManager`,
  `ActiveManager`), `SoftDeleteTimeStampedModel` — all abstract, no
  concrete model, no migration
- `backend/apps/core/utils.py` — `soft_delete()`, `restore()`,
  `bulk_soft_delete()`, `bulk_restore()`, `stamp_audit_fields()`,
  `active_queryset()`, `is_soft_deletable()`, `touch()`
- `backend/apps/core/serializers.py` — `TimeStampedSerializerMixin`,
  `AuditSerializerMixin`, `SoftDeleteSerializerMixin`,
  `SoftDeleteTimeStampedSerializerMixin`
- `backend/apps/core/permissions.py` — re-exports CP6's permission classes
  and hierarchy utilities under `apps.core`; adds `CanRestoreOrHardDelete`
  (a named `IsManagerOrSuperAdmin` subclass, zero new role logic)
- `backend/apps/core/views.py` — `AuditStampedModelMixin`,
  `SoftDeleteModelMixin` (with `restore`/`hard-delete` `@action`s),
  `SoftDeleteAuditModelViewSetMixin`
- `backend/apps/core/admin.py` — `ReadOnlyTimestampsAdminMixin`,
  `SoftDeleteAdminMixin`, `SoftDeleteTimeStampedAdminMixin`
- `backend/apps/core/urls.py` — empty `urlpatterns`, documented placeholder
  for the first future domain resource
- `backend/apps/core/migrations/__init__.py` — empty migrations package
  (no concrete model exists yet to migrate)
- `backend/apps/core/tests/models.py` — test-only concrete models
  (`SampleTimeStamped`, `SampleSoftDeleteOnly`, `SampleRecord`) that exist
  solely to exercise the abstract base classes end to end; not part of the
  production schema, not covered by any migration
- `backend/apps/core/tests/conftest.py` — a `core_test_tables` fixture that
  creates/drops those test-only models' tables directly via
  `schema_editor()`, avoiding the need for a throwaway migration
- `backend/apps/core/tests/test_models.py` — 28 tests
- `backend/apps/core/tests/test_managers.py` — 8 tests
- `backend/apps/core/tests/test_utils.py` — 13 tests
- `backend/apps/core/tests/test_permissions.py` — 6 tests
- `backend/apps/core/tests/test_serializers.py` — 6 tests
- `backend/apps/core/tests/test_admin.py` — 9 tests
- `backend/apps/core/tests/test_views.py` — 8 tests

(78 tests total: 54 genuinely pass with no database, 24 require a real
database and are blocked — see "Tests" below for the exact breakdown.)

### Files modified

- `backend/config/settings/base.py` — added `"apps.core"` to `LOCAL_APPS`

No other existing file was touched. **No frontend file was read, opened, or
modified.**

### Models

Three abstract base models, all built on a shared `AuditModel` ancestor:

- `AuditModel` — `created_by`/`updated_by` (nullable FKs to
  `AUTH_USER_MODEL`, `on_delete=SET_NULL`, `editable=False`).
- `TimeStampedModel(AuditModel)` — adds `created_at` (`auto_now_add`),
  `updated_at` (`auto_now`).
- `SoftDeleteModel(AuditModel)` — adds `is_deleted`/`deleted_at`, plus
  `objects`/`active_objects` managers and `soft_delete()`/`restore()`/
  `hard_delete()` instance methods.
- `SoftDeleteTimeStampedModel(TimeStampedModel, SoftDeleteModel)` — both,
  the base future domain models (Lead, Customer, ...) are expected to
  actually use.

This is a deliberate multiple-inheritance "diamond" (both `TimeStampedModel`
and `SoftDeleteModel` inherit `AuditModel`). Verified empirically, before
committing to this design, that Django 5.1.4 collapses the diamond correctly
— exactly one `created_by`/`updated_by` field, no clash, no duplicate
column — via a throwaway script exercising `ModelBase` directly; this is
also covered by `test_diamond_inheritance_produces_no_duplicate_fields`.

No concrete business model exists yet — per CP7's explicit scope ("no
business modules yet"), only the reusable foundation was built.

### Managers

- `objects` (`SoftDeleteManager`) — the DEFAULT manager, deliberately
  **unfiltered** (returns deleted rows too), so a deleted row is never
  unreachable — verified this resolves correctly to `SoftDeleteManager`
  (not a plain inherited `Manager`) despite `TimeStampedModel` appearing
  first in `SoftDeleteTimeStampedModel`'s MRO, via the same empirical
  script referenced above.
- `active_objects` (`ActiveManager`) — pre-filtered to `is_deleted=False`,
  the manager most call sites should actually use.
- `SoftDeleteQuerySet` backs both: `.active()`, `.deleted()`, `.restore()`
  (bulk), and a deliberately overridden `.delete()` that performs a **bulk
  soft delete**, not a real SQL DELETE — "No permanent delete unless
  explicitly requested" (CP7 spec). The only way to actually remove rows
  via a queryset is the differently-named `.hard_delete()`.
- At the instance level, `Model.delete()` itself is **not** overridden
  (unlike the queryset) — an instance received from elsewhere and asked to
  `.delete()` still performs Django's normal hard delete by default; soft
  delete is only reached via the explicitly-named `instance.soft_delete()`.
  This asymmetry (queryset `.delete()` is soft, instance `.delete()` is
  hard) is intentional and documented at length in `models.py` — see
  BACKEND_LEARNING_GUIDE.md CP7 for the full reasoning.

### Utilities

`apps/core/utils.py`: `soft_delete()`/`restore()` (thin wrappers around the
model methods), `bulk_soft_delete()`/`bulk_restore()` (queryset-level, with
optional `updated_by` stamping), `stamp_audit_fields(instance, user,
creating=...)` (sets `created_by` only when `creating=True`, always sets
`updated_by`; does not call `save()` — callers decide when to persist),
`active_queryset(model)` (works for any model, soft-deletable or not),
`is_soft_deletable(model)`, `touch(instance, updated_by=...)`.

### Permissions

**No duplicate permission logic** (CP7 spec). `apps/core/permissions.py`
re-exports CP6's `IsSuperAdmin`, `IsManager`, `IsEmployee`,
`IsManagerOrSuperAdmin`, `IsOwnerOrSuperAdmin`, `ReadOnlyOrSuperAdmin`, and
every CP6 hierarchy utility function — verified these are the exact same
objects, not copies, via `is`-identity assertions
(`test_reexported_classes_are_the_same_objects_as_accounts_permissions`).
The one addition, `CanRestoreOrHardDelete`, is a named subclass of CP6's
`IsManagerOrSuperAdmin` with zero role-comparison logic of its own — it
exists purely so `restore`/`hard-delete` actions can declare intent at the
call site.

### Admin

`ReadOnlyTimestampsAdminMixin` (appends `created_at`/`updated_at`/
`created_by`/`updated_by` to `readonly_fields`, without duplicating fields
a concrete admin already listed), `SoftDeleteAdminMixin` (unfiltered
`get_queryset()` so deleted rows stay visible/restorable in the admin;
`is_deleted` in `list_filter`; `soft_delete_selected`/`restore_selected`
actions replacing reliance on Django's built-in hard-delete action),
`SoftDeleteTimeStampedAdminMixin` (combines both).

### Tests

**No database required — genuinely executed, genuinely passing:** 54/54
across `test_models.py`, `test_managers.py`, `test_utils.py`,
`test_permissions.py`, `test_serializers.py`, and `test_admin.py`. Covers:
field definitions/defaults on every abstract base, the diamond-inheritance
field-count check, manager class wiring (`objects` vs `active_objects`),
queryset filter structure inspected via `queryset.query.where` (proves a
filter is compiled in without ever evaluating the queryset against a
database — building a `QuerySet` is lazy and needs no connection),
`delete()`/`hard_delete()` distinctness at both queryset and instance level,
every utility function's pure-Python logic, serializer mixin field
declarations and `read_only`/`allow_null` flags (including a
"client-supplied values are silently excluded from `validated_data`"
end-to-end check), permission re-export identity and `CanRestoreOrHardDelete`
behavior, and every admin mixin's `get_readonly_fields()`/`list_filter`/
`get_queryset()` logic against lightweight `ModelAdmin` stand-ins.

**Requires database — blocked:** 24 tests across `test_models.py`,
`test_managers.py`, `test_utils.py`, `test_admin.py`, and `test_views.py`,
covering real persistence round-trips (soft delete marks-not-removes,
restore reverses it, hard delete actually removes the row, `updated_at`
advances on soft delete, `updated_by` stamping, `active_objects` vs
`objects` filtering against real rows, bulk queryset operations, admin
action mutation, and the DRF view mixins' `perform_create`/
`perform_update`/`perform_destroy`/`restore`/`hard_delete` action
behavior). All use a new `core_test_tables` pytest fixture
(`apps/core/tests/conftest.py`) that creates the test-only models' tables
directly via `schema_editor()` rather than a throwaway migration — this
fixture itself requires the `db` fixture and therefore fails at the same
`OperationalError` as every other DB-dependent test, zero assertion
failures.

Three genuine test-authoring bugs were found and fixed **during** this
checkpoint's own verification (not pre-existing bugs — see "Problems
encountered"): three DB-free assertions incorrectly expected
`str(queryset.query.where) == ""` for an unfiltered queryset; Django 5.1.4
actually renders an empty `WhereNode` as the string `"(AND: )"`, not an
empty string. Fixed by asserting `len(queryset.query.where) == 0` instead,
which is the correct way to check "no filter conditions" — caught
immediately because these are DB-free tests that actually ran.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 regression

**Blocked**, same pre-existing cause (not a new CP7 regression). Their
DB-backed tests (103 total) still error at DB setup, identically to their
own prior reports. Their DB-free tests (16 CP4 + 16 CP5 + 59 CP6 = 91) still
pass, unchanged. **None of their statuses were upgraded to VERIFIED** by
CP7's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP6, re-verified (`psql` not found, no Windows
service, no Docker, no WSL).

### OpenAPI

Verified directly (`manage.py spectacular --file`): schema generation still
succeeds with zero errors and zero warnings — unchanged from the end of
CP6, since CP7 added no view, serializer, or endpoint reachable over HTTP
(`apps/core/urls.py` is intentionally empty).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP6 (re-verified: no `psql`, no service, no
Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs were
found in CP1–CP6's carried-forward code during Phase 1 verification.

Three test-authoring bugs in CP7's own new tests were found and fixed
before completion — see "Tests" above (`str(WhereNode) == ""` assumption
was wrong; fixed to `len(where) == 0`). No production code (`models.py`,
`utils.py`, `permissions.py`, `serializers.py`, `views.py`, `admin.py`) was
affected by this fix — it was purely a test-assertion correction, caught
because the affected tests are DB-free and therefore actually executed.

One design question was resolved empirically rather than assumed: whether
Django safely supports the `SoftDeleteTimeStampedModel(TimeStampedModel,
SoftDeleteModel)` diamond (both ultimately inheriting `AuditModel`) without
a field clash, and whether manager resolution (`objects`/`active_objects`)
survives that same diamond correctly despite MRO ordering. Both were
verified with small throwaway scripts against this project's actual Django
version before being relied upon in the real implementation — see
BACKEND_LEARNING_GUIDE.md CP7 for the full walkthrough.

### Deferred

- Any concrete domain model (Lead, Customer, ...) — CP8+. CP7 is
  foundation only, per its explicit scope.
- Wiring `apps/core/views.py`'s mixins into an actual routed endpoint —
  `apps/core/urls.py` remains empty until a real resource exists to route.
- The audit-stamping middleware `AuditModel`'s docstring anticipates
  (`created_by`/`updated_by` auto-populated from `request.user` without a
  view needing to call `stamp_audit_fields()` itself) — CP7 explicitly
  scoped this OUT ("Designed for future middleware. Do NOT implement
  middleware yet.").
- `manager_has_access()`'s always-`False` stub (deferred since CP6, still
  deferred) — still no team/hierarchy model to derive it from.

### Next

CP8 (blocked behind the same PostgreSQL issue affecting CP2–CP7's
DB-dependent verification)

---

## CP8 — Organization Hierarchy

**Status:** PARTIAL / BLOCKED (implementation complete; 60 new tests
genuinely pass with no database at all, bringing the running no-DB total to
208 — 3 CP1 + 16 CP4 + 16 CP5 + 59 CP6 + 54 CP7 + 60 CP8 — while `migrate`
and the 151 total DB-dependent tests (127 carried forward from CP2–CP7,
plus 24 new CP8 persistence/constraint/service tests) remain blocked by the
same missing-PostgreSQL environment issue.)

### Files created

- `backend/apps/organization/__init__.py`, `apps.py` — new Django app,
  registered in `INSTALLED_APPS`
- `backend/apps/organization/models.py` — `OrganizationQuerySet`,
  `Organization`, `Department`, `Team`, `Membership` — all concrete, all
  built on CP7's `TimeStampedModel`
- `backend/apps/organization/migrations/0001_initial.py` — hand-inspected;
  creates all four tables, both `UniqueConstraint`s, both `Index`es
- `backend/apps/organization/admin.py` — `OrganizationAdmin`,
  `DepartmentAdmin`, `TeamAdmin`, `MembershipAdmin` (each built on CP7's
  `ReadOnlyTimestampsAdminMixin`), plus `DepartmentInline`, `TeamInline`,
  `MembershipInline` for drill-down browsing
- `backend/apps/organization/serializers.py` — `OrganizationSerializer`,
  `DepartmentSerializer`/`DepartmentDetailSerializer`,
  `TeamSerializer`/`TeamDetailSerializer`,
  `MembershipSerializer`/`MembershipDetailSerializer`
- `backend/apps/organization/permissions.py` — re-exports CP6's permission
  classes under `apps.organization`; no new role logic
- `backend/apps/organization/services.py` — `add_member()`,
  `remove_member()`, `change_member_role()`, `is_member()`,
  `set_team_manager()`, `get_user_teams()`, `get_team_members()`
- `backend/apps/organization/tests/test_models.py` — 31 tests
- `backend/apps/organization/tests/test_managers.py` — 5 tests
- `backend/apps/organization/tests/test_serializers.py` — 15 tests
- `backend/apps/organization/tests/test_permissions.py` — 8 tests
- `backend/apps/organization/tests/test_admin.py` — 8 tests
- `backend/apps/organization/tests/test_services.py` — 10 tests
- `backend/apps/organization/tests/test_regression.py` — 7 tests

(84 tests total: 60 genuinely pass with no database, 24 require a real
database and are blocked — see "Tests" below for the exact breakdown.)

### Files modified

- `backend/config/settings/base.py` — added `"apps.organization"` to
  `LOCAL_APPS`

No other existing file was touched. **No frontend file was read, opened, or
modified.**

### Models

- **`Organization`** — `name` (unique), `slug` (unique `SlugField`),
  `is_active`, + CP7 timestamps/audit. Top of the hierarchy; one row per
  tenant.
- **`Department`** — FK to `Organization` (`related_name="departments"`,
  `CASCADE`), `name`, `description`. `UniqueConstraint(organization, name)`
  — a department name is unique *within* its organization, not globally.
- **`Team`** — FK to `Department` (`related_name="teams"`, `CASCADE`),
  `name`, FK `manager` to `settings.AUTH_USER_MODEL`
  (`related_name="teams_managed"`, nullable, `SET_NULL`).
  `UniqueConstraint(department, name)`.
- **`Membership`** — FK `user` (`related_name="team_memberships"`,
  `CASCADE`), FK `team` (`related_name="memberships"`, `CASCADE`), `role`
  (`Membership.Role.LEAD`/`MEMBER`, team-scoped — deliberately distinct
  from `accounts.User.role`, CP2/CP6's *global* RBAC role), `joined_at`.
  `UniqueConstraint(user, team)` — a user can only have one membership per
  team.

All four inherit `apps.core.models.TimeStampedModel` (CP7) for
`created_at`/`updated_at`/`created_by`/`updated_by` rather than redeclaring
them — the first concrete schema to actually build on CP7's foundation.
Soft delete (`SoftDeleteModel`) was deliberately NOT mixed in — see
"Problems encountered"/BACKEND_LEARNING_GUIDE.md CP8 for why.

Indexes: `Department(organization, name)`, `Team(department, name)`,
`Membership(team, role)` — each backing its model's most likely filter
pattern (all departments in an org, all teams in a department, all
leads/members on a team) beyond what the `UniqueConstraint`s and automatic
FK indexes already provide.

`Team.owner` (property returning `self.manager`) and
`Membership.owner`/`Membership.manager_has_access()` (properties/method
returning the member, and whether a given user manages the membership's
team) are the first real use of CP6/CP7's documented
`IsOwnerOrSuperAdmin` extension points — see "Permissions" below.

### Permissions

**No duplicate permission logic** (CP8 spec: "permissions using CP6
RBAC"). `apps/organization/permissions.py` re-exports CP6's `IsSuperAdmin`,
`IsManager`, `IsEmployee`, `IsManagerOrSuperAdmin`, `IsOwnerOrSuperAdmin`,
`ReadOnlyOrSuperAdmin` — verified as the exact same objects, not copies,
via `is`-identity assertions, following CP7's own precedent for its
`permissions.py`.

The only new code is on the models themselves: `Team.owner` and
`Membership.owner`/`manager_has_access()` — exercising CP6's documented
(but, until now, never-used) per-object extension points for real:
`IsOwnerOrSuperAdmin.has_object_permission()` now resolves a `Team`'s
manager as its owner, and a `Membership`'s own user as its owner, with a
`Membership`'s team-manager granted access via the `manager_has_access()`
hook — all without a single new line of role-comparison logic.

Documented access rules for a future view layer to apply (no views exist
yet in CP8 — see "Deferred"): Organization writes are `IsSuperAdmin`-only;
Department/Team writes are `IsManagerOrSuperAdmin`; a specific `Team`/
`Membership` object is additionally reachable by its manager/owner via
`IsOwnerOrSuperAdmin`.

### Services

`apps/organization/services.py`, following the CP5 `apps.accounts.services`
pattern (narrow, single-purpose, testable functions — not a wrapper for
every trivial `.objects.create()`):

- `add_member(team, user, role=MEMBER)` — idempotent (`get_or_create`);
  does NOT change an existing member's role.
- `remove_member(team, user)` — returns `True`/`False` for
  "removed"/"was never a member".
- `change_member_role(team, user, role)` — raises `Membership.DoesNotExist`
  rather than silently creating a membership if the user isn't already one.
- `is_member(team, user)` — existence check.
- `set_team_manager(team, user)` — assign or clear (`user=None`) a team's
  manager.
- `get_user_teams(user)` / `get_team_members(team, role=None)` — read
  helpers over the membership relation.

### Admin

`OrganizationAdmin`, `DepartmentAdmin`, `TeamAdmin`, `MembershipAdmin` —
each built on CP7's `ReadOnlyTimestampsAdminMixin` (timestamps/audit fields
shown, never hand-edited). `OrganizationAdmin` inlines `Department`,
`DepartmentAdmin` inlines `Team`, `TeamAdmin` inlines `Membership` — a full
drill-down path from organization to individual membership without
leaving the admin. `autocomplete_fields` used for every FK reference
(`organization`, `department`, `team`, `manager`, `user`) rather than slow
dropdown `<select>`s, confirmed safe by `manage.py check` (every
autocompleted-to admin declares `search_fields`).

### Tests

**No database required — genuinely executed, genuinely passing:** 60/60
across `test_models.py`, `test_managers.py`, `test_serializers.py`,
`test_permissions.py`, `test_admin.py`, and `test_regression.py`. Covers:
every field's definition/nullability/`on_delete`/`related_name`, every
`UniqueConstraint`/`Index` name, `__str__` methods, `Team.owner`/
`Membership.owner`/`Membership.manager_has_access()` on in-memory (unsaved)
instances, `Organization.objects.active()`'s compiled filter (inspected via
`queryset.query.where`, never evaluated against a database), every
serializer's field declarations and read-only/writable split (including
that every `*DetailSerializer` is entirely read-only), permission re-export
identity, `IsOwnerOrSuperAdmin` resolving `Team`/`Membership` ownership
correctly against in-memory objects, the admin registry (registered
classes, inline models, `ReadOnlyTimestampsAdminMixin` usage), and
lightweight regression spot-checks confirming CP3/CP4/CP5's URLs, CP6's
permission classes, and CP7's abstract models are all still importable and
functional after CP8's changes.

**Requires database — blocked:** 24 tests across `test_models.py`,
`test_managers.py`, `test_serializers.py`, and `test_services.py`, covering
real persistence (create/retrieve), both `UniqueConstraint`s actually
rejecting a duplicate row, `on_delete` behavior (`CASCADE` from
Organization through Department through Team to Membership; `SET_NULL`
when a team's manager is deleted), reverse-relationship traversal
(`org.departments`, `dept.teams`, `team.memberships`,
`user.team_memberships`), `active()` filtering real rows, a `TeamDetailSerializer`
serializing a real persisted `Team` with its nested manager, and every
service function's real read/write behavior. All error at the identical
`OperationalError` as every other DB-dependent test since CP2, zero
assertion failures.

One genuine test-authoring bug was found and fixed **during** this
checkpoint's own DB-free test run (not a pre-existing or production-code
bug): a test asserting `OrganizationSerializer.is_valid()` succeeds for
input containing extra, non-model fields was written assuming no database
access was needed — but `name`/`slug` are `unique=True` on `Organization`,
so DRF's `ModelSerializer` auto-attaches a `UniqueValidator` to each field,
which queries the database during `is_valid()` to check for a clash. Fixed
by moving the test to the DB-dependent section with `@pytest.mark.django_db`
— caught immediately because the DB-free suite genuinely executes.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 regression

**Blocked**, same pre-existing cause (not a new CP8 regression). Their
DB-backed tests (127 total) still error at DB setup, identically to their
own prior reports. Their DB-free tests (16 CP4 + 16 CP5 + 59 CP6 + 54 CP7 =
145) still pass, unchanged. **None of their statuses were upgraded to
VERIFIED** by CP8's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP7, re-verified (`psql` not found, no Windows
service, no Docker, no WSL).

### OpenAPI

Verified directly (`manage.py spectacular --file`): schema generation still
succeeds with zero errors and zero warnings — unchanged from the end of
CP7, since CP8 (like CP7) added no view/URL reachable over HTTP.

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP7 (re-verified: no `psql`, no service, no
Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs were
found in CP1–CP7's carried-forward code during Phase 1 verification.

One test-authoring bug in CP8's own new tests was found and fixed before
completion — see "Tests" above (a `UniqueValidator`-triggered DB access was
missed when first classifying a test as DB-free). No production code
(`models.py`, `serializers.py`, `permissions.py`, `services.py`,
`admin.py`) was affected — it was purely a test-classification correction,
caught because the affected test is in the DB-free suite and therefore
actually executed.

A design decision worth recording: **soft delete was deliberately NOT
added** to any CP8 model, even though CP7 makes `SoftDeleteModel` available
for exactly this kind of hierarchy. CP8's own spec only asked for
timestamps, and "what does deleting an Organization with active
Departments/Teams/Memberships mean" (cascade-archive children? block the
delete? something else?) is a real product decision, not one this
checkpoint has the authority or the requirement to make. Hard `CASCADE`
deletes were used instead — verified directly (deleting an `Organization`
removes its `Department`s; deleting a `Team` removes its `Membership`s) —
which is at least an honest, unsurprising default until a future checkpoint
decides otherwise.

### Deferred

- Any HTTP endpoint (views/urls) for this hierarchy — CP8, like CP7,
  builds no HTTP surface. `serializers.py`/`permissions.py` are ready for a
  future checkpoint's views to use directly.
- Soft delete for the organization hierarchy — see "Problems encountered"
  above; deferred as a real product decision, not an oversight.
- Multi-tenant data isolation (scoping every other future model's queries
  to "the caller's organization") — CP8 builds the *shape* of the
  hierarchy only; enforcing it as a data-access boundary is a separate,
  larger concern for a future checkpoint.
- A real driver for `manager_has_access()`'s general extension point
  (`apps.accounts.permissions`, deferred since CP6) remains deferred for
  every model EXCEPT `Membership`, which now has its own concrete
  `manager_has_access()` — a future model could follow the same pattern.

### Next

CP9 (blocked behind the same PostgreSQL issue affecting CP2–CP8's
DB-dependent verification)

---

## CP9 — CRM Foundation (Customer / Lead / ContactPerson / Address)

**Status:** PARTIAL / BLOCKED (implementation complete; 60 new tests
genuinely pass with no database at all, bringing the running no-DB total to
268 — 208 CP1–CP8 baseline + 60 CP9 — while `migrate` and the 188 total
DB-dependent tests (151 carried forward from CP2–CP8, plus 37 new CP9
persistence/constraint/service/serializer-validation tests) remain blocked
by the same missing-PostgreSQL environment issue.)

### Files created

- `backend/apps/crm/__init__.py`, `apps.py` — new Django app, registered in
  `INSTALLED_APPS`
- `backend/apps/crm/models.py` — `CustomerQuerySet`/`CustomerManager`/
  `ActiveCustomerManager`, `Customer`; `LeadQuerySet`/`LeadManager`/
  `ActiveLeadManager`, `Lead`; `ContactPerson`; `Address` — all built on
  CP7's `SoftDeleteTimeStampedModel`
- `backend/apps/crm/migrations/0001_initial.py` — hand-inspected; creates
  all four tables, the scoped `UniqueConstraint`, the partial
  `UniqueConstraint`, and every declared `Index`
- `backend/apps/crm/services.py` — `create_customer()`, `create_lead()`,
  `convert_lead()`, `assign_owner()`, `add_contact()`, `add_address()`
- `backend/apps/crm/serializers.py` — `CustomerSerializer`/
  `CustomerDetailSerializer`, `LeadSerializer`/`LeadDetailSerializer`,
  `ContactPersonSerializer`, `AddressSerializer`
- `backend/apps/crm/permissions.py` — re-exports CP6's permission classes
  under `apps.crm`; no new role logic
- `backend/apps/crm/admin.py` — `CustomerAdmin`, `LeadAdmin`,
  `ContactPersonAdmin`, `AddressAdmin` (each built on CP7's
  `SoftDeleteTimeStampedAdminMixin`), plus `ContactPersonInline`/
  `AddressInline`
- `backend/apps/crm/tests/conftest.py` — shared `organization`/`owner`/
  `customer` fixtures
- `backend/apps/crm/tests/test_models.py` — 29 tests
- `backend/apps/crm/tests/test_managers.py` — 11 tests
- `backend/apps/crm/tests/test_serializers.py` — 14 tests
- `backend/apps/crm/tests/test_permissions.py` — 8 tests
- `backend/apps/crm/tests/test_admin.py` — 9 tests
- `backend/apps/crm/tests/test_services.py` — 18 tests
- `backend/apps/crm/tests/test_regression.py` — 8 tests

(97 tests total: 60 genuinely pass with no database, 37 require a real
database and are blocked — see "Tests" below for the exact breakdown.)

### Files modified

- `backend/config/settings/base.py` — added `"apps.crm"` to `LOCAL_APPS`

No other existing file was touched. **No frontend file was read, opened, or
modified.**

### Migration

`apps/crm/migrations/0001_initial.py` — a single migration creating all
four tables. Depends on `organization.0001_initial` (CP8, for the
`Customer.organization` FK) and `settings.AUTH_USER_MODEL`'s swappable
dependency (for `owner`/`created_by`/`updated_by`). Hand-inspected field by
field; `makemigrations --check --dry-run` reports "No changes detected"
both before and after generation. **Not applied** — same PostgreSQL
blocker as every prior checkpoint.

### Models

- **`Customer`** — FK `organization` (`related_name="customers"`,
  `CASCADE`), `name`, `slug`, FK `owner` (`related_name="owned_customers"`,
  nullable, `SET_NULL`), `status` (`PROSPECT`/`ACTIVE`/`INACTIVE`/
  `CHURNED`), `industry`, `website`, `email`, `phone`, `notes`, `is_active`
  (a business flag, independent of soft delete — see "Problems
  encountered" for why both exist). `UniqueConstraint(organization, slug)`
  — a slug is unique *within* its organization, following CP8's
  `Department`/`Team` scoped-uniqueness precedent.
- **`Lead`** — `company_name`, `contact_name`, `email`, `phone`, `source`
  (`WEBSITE`/`REFERRAL`/`COLD_CALL`/`EVENT`/`ADVERTISEMENT`/`OTHER`),
  `status` (`NEW`/`CONTACTED`/`QUALIFIED`/`CONVERTED`/`LOST`), FK `owner`
  (`related_name="owned_leads"`), FK `converted_customer`
  (`related_name="converted_from_leads"`, nullable, `SET_NULL`), `notes`.
  Deliberately has NO `organization` FK — see "Problems encountered".
- **`ContactPerson`** — FK `customer` (`related_name="contacts"`,
  `CASCADE`), `first_name`, `last_name`, `designation`, `email`, `phone`,
  `is_primary`. A partial `UniqueConstraint` (`condition=Q(is_primary=True)`)
  enforces at most one primary contact per customer at the database level.
- **`Address`** — FK `customer` (`related_name="addresses"`, `CASCADE`),
  `address_type` (`BILLING`/`SHIPPING`), `line1`, `line2`, `city`, `state`,
  `country`, `postal_code`.

All four inherit `apps.core.models.SoftDeleteTimeStampedModel` (CP7) — the
first checkpoint to use the *combined* base (CP8 used `TimeStampedModel`
alone). `Customer`/`Lead` expose a plain `owner` FK (CP6's
`resolve_owner()` finds it automatically); `ContactPerson`/`Address` each
get an `owner` property delegating to `self.customer.owner`, following
CP8's `Team`/`Membership` precedent exactly.

### Managers

- **`Customer.objects`**/`active_objects` — `CustomerQuerySet` overrides
  CP7's `active()` (not-deleted only) to ALSO require `is_active=True`,
  plus `by_owner(user)`/`by_status(status)`.
- **`Lead.objects`**/`active_objects` — `LeadQuerySet` adds
  `by_owner(user)`/`by_status(status)`/`converted()`/`unconverted()`.
  `active_objects` here means only "not soft-deleted" (Lead has no
  business `is_active` flag the way Customer does — its lifecycle is
  `status` alone).
- **`ContactPerson`/`Address`** use CP7's plain `SoftDeleteManager`/
  `ActiveManager` directly — no extra query helpers, since CP9 didn't
  request any for these two models.

### Services

`apps/crm/services.py`, following the CP5/CP8 pattern (narrow,
single-purpose, only where there's real behavior beyond one ORM call):

- `create_customer(organization, name, owner=None, slug=None, **fields)` —
  auto-generates `slug` via `slugify(name)` when not supplied.
- `create_lead(company_name, contact_name, owner=None, **fields)` — thin
  wrapper, a seam for future intake rules (dedup, auto-assignment).
- `convert_lead(lead, organization, owner=None, slug=None, **fields)` —
  **the conversion workflow**: creates a `Customer` (defaulting
  `name`/`email`/`phone` from the lead, overridable), links
  `lead.converted_customer`, advances `lead.status` to `CONVERTED` — all
  together, atomically from the caller's perspective, so a lead is never
  left half-converted. Raises `ValueError` if the lead was already
  converted (`lead.is_converted`).
- `assign_owner(instance, user)` — works on both `Customer` and `Lead`
  (anything with an `owner` FK), mirroring CP8's `set_team_manager()`.
- `add_contact(customer, first_name, last_name, is_primary=False, **fields)`
  — if `is_primary=True`, demotes any existing primary contact FIRST, so
  "promote a new primary" is one safe call instead of the caller having to
  remember a two-step demote-then-create sequence.
- `add_address(customer, address_type, **fields)` — thin wrapper, symmetry
  with `add_contact()`.

### Serializers

Every serializer mixes in CP7's `SoftDeleteTimeStampedSerializerMixin` —
the first checkpoint to use it exactly as CP7's own usage example
anticipated. Writable + read-only-detail pairs, following CP8's pattern:

- `CustomerSerializer` (writable, `owner` as PK) /
  `CustomerDetailSerializer` (read-only: nests `owner` as a full
  `UserSerializer`, `organization_name`, and this customer's `contacts`/
  `addresses` as nested lists).
- `LeadSerializer` (writable; `converted_customer` is READ-ONLY even here
  — conversion is a service action, never a plain field edit) /
  `LeadDetailSerializer` (read-only: nests `owner` and the full converted
  `Customer`, not just its ID).
- `ContactPersonSerializer` (writable) — `validate()` mirrors the DB's
  partial unique constraint with a friendly 400 (`"This customer already
  has a primary contact."`) instead of a raw `IntegrityError`, correctly
  excluding the instance itself on update.
- `AddressSerializer` (writable).

**Validation**: `LeadSerializer.validate_status()` rejects a client
attempting to set `status=CONVERTED` directly (that would leave
`converted_customer` unset and the lead inconsistent) — only
`apps.crm.services.convert_lead()` can produce that state.

### Permissions

**No duplicate permission logic** (CP9 spec: "Reuse CP6 RBAC... Only
compose existing permission classes"). `apps/crm/permissions.py`
re-exports CP6's `IsSuperAdmin`, `IsManager`, `IsEmployee`,
`IsManagerOrSuperAdmin`, `IsOwnerOrSuperAdmin`, `ReadOnlyOrSuperAdmin` —
verified as the exact same objects via `is`-identity assertions, following
CP7/CP8's own precedent. All new code lives on the models themselves
(`owner` FK on `Customer`/`Lead`; `owner` property on `ContactPerson`/
`Address`) — CP6's `IsOwnerOrSuperAdmin` needed zero changes to work
correctly against all four.

### Admin

`CustomerAdmin`, `LeadAdmin`, `ContactPersonAdmin`, `AddressAdmin` — each
built on CP7's `SoftDeleteTimeStampedAdminMixin` (unfiltered queryset,
`is_deleted` in `list_filter`, soft-delete/restore bulk actions, read-only
timestamp/audit fields, all for free). `CustomerAdmin` inlines
`ContactPerson` and `Address` for a full drill-down from customer to its
contacts/addresses. `autocomplete_fields` used for every FK reference,
confirmed safe by `manage.py check` (every autocompleted-to admin declares
`search_fields`).

### Tests

**No database required — genuinely executed, genuinely passing:** 60/60
across `test_models.py`, `test_managers.py`, `test_serializers.py`,
`test_permissions.py`, `test_admin.py`, and `test_regression.py`. Covers
every field's definition/nullability/`on_delete`/`related_name`, both
`UniqueConstraint`s (including the partial one's exact `condition`),
`__str__`/`full_name`/`is_converted`/`owner` properties on in-memory
(unsaved) instances, every queryset helper's compiled filter (inspected via
`queryset.query.where`, never evaluated against a database), every
serializer's field declarations and read-only/writable split, the
`LeadSerializer` CONVERTED-status rejection (genuinely DB-free — no unique
fields involved), permission re-export identity, `IsOwnerOrSuperAdmin`
resolving `Customer`/`Lead`/`ContactPerson`/`Address` ownership correctly,
the admin registry, and regression spot-checks confirming CP3/CP4/CP5/CP6/
CP7/CP8 remain importable and functional.

**Requires database — blocked:** 37 tests across `test_models.py`,
`test_managers.py`, `test_serializers.py`, and `test_services.py`, covering
real persistence, both `UniqueConstraint`s actually rejecting a duplicate
row (including the partial one rejecting a second primary contact but
allowing unlimited non-primary ones), cascade/set-null delete behavior
through the full `Organization → Customer → ContactPerson/Address` chain,
`ContactPersonSerializer`'s DB-querying validation, and — the checkpoint's
centerpiece — every `convert_lead()` scenario (customer creation, field
defaulting and overriding, owner defaulting/overriding, status/link
consistency, and the double-conversion `ValueError`). All error at the
identical `OperationalError` as every other DB-dependent test since CP2,
zero assertion failures.

No genuine test-authoring bugs were found this checkpoint (unlike CP7/CP8,
which each caught one) — every DB-free test was correctly classified on
the first run.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 / CP8 regression

**Blocked**, same pre-existing cause (not a new CP9 regression). Their
DB-backed tests (151 total) still error at DB setup, identically to their
own prior reports. Their DB-free tests (16 CP4 + 16 CP5 + 59 CP6 + 54 CP7 +
60 CP8 = 205) still pass, unchanged. **None of their statuses were
upgraded to VERIFIED** by CP9's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP8, re-verified (`psql` not found, no Windows
service, no Docker, no WSL).

### OpenAPI

Verified directly (`manage.py spectacular --file schema.yaml`): schema
generation still succeeds with zero errors and zero warnings — unchanged
from the end of CP8, since CP9 (like CP7/CP8) added no view/URL reachable
over HTTP.

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP8 (re-verified: no `psql`, no service, no
Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs were
found in CP1–CP8's carried-forward code during Phase 1 verification.

Two deliberate design decisions worth recording:

1. **`Lead` has no `organization` FK.** CP9's own field list for `Lead`
   never mentions one, and a raw inbound inquiry genuinely may not be
   known to belong to any organization yet — it only gains one indirectly,
   through `converted_customer.organization`, once `convert_lead()` runs.
   Adding an `organization` FK to `Lead` would have been easy but not
   something the spec asked for, and would raise an unasked question
   (must a lead's organization match the organization it's converted
   into?) — left out rather than guessed at.
2. **`Customer.is_active` and `Customer.is_deleted` (from CP7) are two
   independent booleans, not one.** `is_deleted` (soft delete) means "this
   record's existence should not be considered at all." `is_active` means
   "this customer is currently active business" (as opposed to
   paused/churned) while still very much existing and visible. Collapsing
   them into one flag would make it impossible to represent "a churned
   customer we're still keeping visible history for" — a real CRM
   distinction. `Customer.active_objects` requires BOTH to be true,
   documented directly in `CustomerQuerySet.active()`'s docstring.

### Deferred

- Any HTTP endpoint (views/urls) for this domain — CP9, like CP7/CP8,
  builds no HTTP surface. `serializers.py`/`permissions.py` are ready for
  a future checkpoint's views to use directly.
- `Lead.organization` / multi-tenant lead scoping — see "Problems
  encountered" above.
- A "convert lead" HTTP endpoint wiring `services.convert_lead()` to a
  request — the service function itself is complete and tested; only the
  view layer is deferred.
- CP8's `manager_has_access()`-style per-object hook was NOT added to any
  CP9 model — `Customer`/`Lead`'s plain `owner` FK already gives
  `IsOwnerOrSuperAdmin` everything it needs; there was no "the object's
  manager differs from its owner" scenario here the way CP8's
  `Membership` had (team manager vs. member).

### Next

CP10 (blocked behind the same PostgreSQL issue affecting CP2–CP9's
DB-dependent verification)

---

## CP10 — CRM REST API (Customers / Leads / Contacts / Addresses)

**Status:** PARTIAL / BLOCKED (implementation complete. `apps/crm/` now
totals 194 tests — 93 genuinely pass with no database, 101 require a real
database and are blocked. Of those, the 12 new CP10 test files contribute
105 tests (42 pass with no database, 63 blocked); the 6 carried-forward
CP9 test files now total 89 tests — 51 pass, 38 blocked (one test,
`test_unrelated_manager_denied_on_a_contact_they_do_not_own`, moved from
passing-with-no-database to database-required this checkpoint — see
"Problems encountered"). Project-wide: **301 passed, 252 errors** — see
"Verification Results".)

### Files created

- `backend/apps/crm/views.py` — `CustomerViewSet`, `LeadViewSet`,
  `ContactPersonViewSet`, `AddressViewSet`, and their shared
  `_CrmModelViewSet` base
- `backend/apps/crm/urls.py` — `DefaultRouter` registration, mounted at
  `/api/v1/crm/` by `config/urls.py`
- `backend/apps/crm/filters.py` — `CustomerFilterSet`, `LeadFilterSet`
  (with the `converted` boolean filter reusing CP9's `LeadQuerySet
  .converted()`/`.unconverted()`), `ContactPersonFilterSet`,
  `AddressFilterSet`
- `backend/apps/core/pagination.py` — `StandardPagination` (page size 20,
  client-overridable up to 100)
- `backend/apps/crm/tests/test_urls.py` — 5 tests
- `backend/apps/crm/tests/test_views_config.py` — 15 tests
- `backend/apps/crm/tests/test_pagination.py` — 3 tests
- `backend/apps/crm/tests/test_filters.py` — 6 tests
- `backend/apps/crm/tests/test_openapi.py` — 5 tests
- `backend/apps/crm/tests/test_api_crud.py` — 19 tests
- `backend/apps/crm/tests/test_api_permissions.py` — 14 tests
- `backend/apps/crm/tests/test_api_search_filter_ordering.py` — 12 tests
- `backend/apps/crm/tests/test_api_pagination.py` — 3 tests
- `backend/apps/crm/tests/test_api_validation.py` — 3 tests
- `backend/apps/crm/tests/test_services_scoping.py` — 12 tests
- `backend/apps/crm/tests/test_regression.py` — 8 tests

(105 tests across these 12 new files: 42 genuinely pass with no database
— `test_urls.py` 5, `test_views_config.py` 15, `test_pagination.py` 3,
`test_filters.py` 6, `test_openapi.py` 5, `test_regression.py` 8 — and 63
require a real database and are blocked —`test_api_crud.py` 19,
`test_api_permissions.py` 14, `test_api_search_filter_ordering.py` 12,
`test_api_pagination.py` 3, `test_api_validation.py` 3,
`test_services_scoping.py` 12. Combined with CP9's carried-forward 89
tests — one of which is now DB-dependent per "Problems encountered" below
— the `apps/crm/` app total is 194 tests: 93 pass, 101 blocked.)

### Files modified

- `backend/apps/crm/models.py` — added `Customer.manager_has_access()`,
  `Lead.manager_has_access()`, and `ContactPerson`/`Address
  .manager_has_access()` (delegating to their `customer`) — CP6's
  documented per-object extension point, exercised here for CP10's
  "Managers see their team's records" rule
- `backend/apps/crm/services.py` — added `managed_user_ids()`,
  `scope_queryset_for_user()`
- `backend/config/settings/base.py` — `DEFAULT_PAGINATION_CLASS` now
  `apps.core.pagination.StandardPagination` (`PAGE_SIZE` 25 → 20);
  `ENUM_NAME_OVERRIDES` added to `SPECTACULAR_SETTINGS` (see "OpenAPI")
- `backend/config/urls.py` — mounted `apps.crm.urls` at `/api/v1/crm/`
- `backend/apps/crm/tests/conftest.py` — added `api_client`, `employee`,
  `other_employee`, `manager`, `super_admin`, `managed_team` fixtures
- `backend/apps/crm/tests/test_permissions.py` (CP9) — one test
  (`test_unrelated_manager_denied_on_a_contact_they_do_not_own`) marked
  `@pytest.mark.django_db` — see "Problems encountered"

No other existing file was touched. **No frontend file was read, opened, or
modified.**

### Migration

**None required.** CP10 added no model field — `manager_has_access()` and
`scope_queryset_for_user()` are pure Python/query logic, no schema change.
`makemigrations --check --dry-run` → "No changes detected", confirmed
before and after implementation.

### Endpoints

All four resources follow the identical shape, mounted under
`/api/v1/crm/`, via a single `DefaultRouter`:

| Method | Path | Notes |
|---|---|---|
| GET | `/customers/`, `/leads/`, `/contacts/`, `/addresses/` | List — paginated, scoped by ownership |
| POST | (same, no trailing id) | Create — routed through CP9 services where real behavior exists |
| GET | `.../<id>/` | Retrieve — detail serializer for Customer/Lead |
| PATCH | `.../<id>/` | Partial update only — **no PUT** on any resource |
| DELETE | `.../<id>/` | Soft delete (CP7's `SoftDeleteModelMixin`), not a real row removal |
| POST | `.../<id>/restore/` | Undo a soft delete (CP7 mixin, Manager-or-above only) |
| POST | `.../<id>/hard-delete/` | Permanent delete (CP7 mixin, Manager-or-above only) |

`PUT` is deliberately excluded via `http_method_names` on every viewset —
CP10's own endpoint spec lists PATCH for every resource and never PUT.

### ViewSets

`CustomerViewSet`, `LeadViewSet`, `ContactPersonViewSet`, `AddressViewSet`
— each a `viewsets.ModelViewSet` combined with CP7's
`SoftDeleteAuditModelViewSetMixin` (soft-delete-on-DELETE + audit stamping
+ `restore`/`hard-delete` actions, defined in CP7, wired to a real endpoint
for the first time here). `get_queryset()` uses the ACTIVE manager for
`list` and the UNFILTERED manager for every other action (so a
soft-deleted row stays reachable for `restore`/`hard-delete` — per CP7's
own documented warning), then scopes the result through
`scope_queryset_for_user()` regardless of action.

### Filtering

`django-filter`, already configured project-wide since CP7
(`DEFAULT_FILTER_BACKENDS`) — CP10 only needed to declare a
`filterset_class` per viewset:

- `CustomerFilterSet`: `status`, `owner`, `organization`, `industry`,
  `is_active`.
- `LeadFilterSet`: `status`, `owner`, `source`, plus a custom `converted`
  `BooleanFilter` reusing CP9's `LeadQuerySet.converted()`/`.unconverted()`
  (Lead has no boolean `converted` column — it's derived from
  `converted_customer`).
- `ContactPersonFilterSet`/`AddressFilterSet`: `customer` (+ `is_primary`/
  `address_type` respectively) — a sensible, minimal extension beyond
  CP10's literal filter-field list, since browsing a customer's contacts/
  addresses by `customer` is an obvious real need these two resources
  otherwise couldn't support at all.

### Searching

`rest_framework.filters.SearchFilter` (already a project-wide default
backend since CP7) via `search_fields`:

- `CustomerViewSet`: `name`, `email`, `phone`, `website`.
- `LeadViewSet`: `company_name`, `contact_name`, `email`, `phone`.
- `ContactPersonViewSet`/`AddressViewSet`: not explicitly requested by
  CP10's spec; given minimal, sensible fields (`first_name`/`last_name`/
  `email` and `line1`/`city`/`postal_code` respectively) for usability,
  same reasoning as the extra `customer` filter above.

### Ordering

`rest_framework.filters.OrderingFilter` via `ordering_fields`:

- `CustomerViewSet`: `name`, `created_at`, `updated_at`, `status` — exactly
  CP10's spec.
- `LeadViewSet`: `("company_name", "name")`, `created_at`, `updated_at`,
  `status` — `Lead` has no `name` field (it has `company_name`); DRF's
  `OrderingFilter` supports `(field, param)` tuples, so a client can still
  pass `?ordering=name` and have it map to `company_name`, honoring CP10's
  literal spec across both resources without inventing a fake field.
- `ContactPersonViewSet`/`AddressViewSet`: sensible subsets (`last_name`
  aliased to `name`, `created_at`, `updated_at`, `city` for Address) —
  neither model has `status`.

### Pagination

Project-wide, via a new `apps.core.pagination.StandardPagination`
replacing the bare DRF default: `page_size = 20`, client-overridable via
`?page_size=` up to `max_page_size = 100`. This is a genuinely project-wide
change (`DEFAULT_PAGINATION_CLASS`/`PAGE_SIZE` live in shared
`REST_FRAMEWORK` settings) — it also changes CP5's `SessionListView`'s
default page size from 25 to 20, a deliberate, requested change, not a
regression (verified: `SessionListView` never declared its own
`pagination_class`, so it picks up the new project default automatically;
see `test_pagination_class_swap_did_not_break_cp5_session_list_view`).

### Permissions

**No duplicated permission logic** (CP10 spec: "Reuse CP6 permissions").
Every viewset uses exactly `[IsAuthenticated, IsOwnerOrSuperAdmin]` — both
already existed (DRF's own `IsAuthenticated`; CP6's `IsOwnerOrSuperAdmin`).
The three-tier rule CP10 asked for — "Employees: own records only;
Managers: team records; Super Admin: everything" — was built entirely by
composing existing pieces, not by writing new role-comparison code:

- **List scoping**: `apps/crm/services.py`'s new `scope_queryset_for_user()`
  filters the queryset by `owner`/`owner_id__in` using CP6's
  `is_super_admin()`/`user_has_role_at_least()` (unchanged, just called)
  and a new `managed_user_ids()` helper that queries CP8's `Team`/
  `Membership` models for "who does this Manager manage."
- **Object-level access** (retrieve/update/destroy): unchanged CP6
  `IsOwnerOrSuperAdmin` — its `has_object_permission()` already checks an
  `owner` attribute, then a `manager_has_access()` hook if the object
  defines one. CP10 gave `Customer`/`Lead` (and, via delegation,
  `ContactPerson`/`Address`) exactly that hook, implemented by calling the
  SAME `managed_user_ids()` function `scope_queryset_for_user()` uses — so
  a Manager's list results and their individual object access can never
  disagree about who they can reach.
- **`restore`/`hard-delete`**: unchanged CP7 `CanRestoreOrHardDelete`
  (Manager-or-above by role only, no object-level scoping) — see "Problems
  encountered" for the one known, deliberate gap this leaves.

### Services Used

- `create_customer()`, `assign_owner()` (`CustomerViewSet.perform_create()`
  — real behavior: slug handling + owner defaulting)
- `assign_owner()` (`LeadViewSet.perform_create()` — owner defaulting;
  audit stamping still via CP7's `AuditStampedModelMixin` default, since
  `create_lead()` itself has no behavior beyond a bare `.create()`)
- `add_contact()` (`ContactPersonViewSet.perform_create()` — real
  behavior: demotes an existing primary contact before promoting a new
  one)
- `add_address()` (`AddressViewSet.perform_create()` — thin wrapper, used
  for architectural symmetry, not because it has real behavior today)
- `managed_user_ids()`, `scope_queryset_for_user()` (new this checkpoint —
  see "Permissions")

Per CP10's instruction ("views must call service-layer methods where
business logic exists... do not duplicate business logic inside views"),
no view reimplements slug generation, primary-contact demotion, or
ownership scoping — each delegates to the one function that owns that
logic.

### Serializers

**Reused verbatim from CP9** — no serializer was modified. `get_serializer_class()`
selects `CustomerDetailSerializer`/`LeadDetailSerializer` (nested owner,
organization name, contacts/addresses or converted customer) on `retrieve`
only; every other action uses the plain writable `CustomerSerializer`/
`LeadSerializer`. `ContactPersonSerializer`/`AddressSerializer` have no
detail variant (CP9 built none — neither model has a relation worth
nesting) and are used unconditionally.

### OpenAPI

`manage.py spectacular --file schema.yaml` — zero errors, zero warnings.
One genuine warning was found and fixed during this checkpoint:
`Customer.Status` and `Lead.Status` are two different `TextChoices`
classes that both back a field literally named `status`, which
drf-spectacular's automatic enum-naming collides on, falling back to an
unstable hash-suffixed component name (e.g. `Status80cEnum`). Fixed via a
new `ENUM_NAME_OVERRIDES` entry in `SPECTACULAR_SETTINGS` naming them
explicitly (`CustomerStatusEnum`, `LeadStatusEnum`) — not a bug in either
model (both fields are correctly named `status` for their own domain),
purely a schema-naming disambiguation. Verified both in-process (schema
generation via `SchemaGenerator` directly, asserting `GENERATOR_STATS` is
empty) and via the real `manage.py spectacular` CLI invocation.

### Tests

**No database required — genuinely executed, genuinely passing:** 42/42 in
CP10's new files (`test_urls.py`, `test_views_config.py`,
`test_pagination.py`, `test_filters.py`, `test_openapi.py`,
`test_regression.py`) plus 51/89 of CP9's carried-forward files (see
"Problems encountered" for the one test that moved out of this bucket this
checkpoint). Covers: URL
reversal for every endpoint including `restore`/`hard-delete`; every
viewset's declared HTTP methods (no PUT), permission classes, serializer
selection logic, filterset/search/ordering wiring, and `owner_field`
configuration; `get_queryset()`'s *query-building* for an anonymous
requester (lazy, never evaluated); `StandardPagination`'s configured
values; `LeadFilterSet.filter_converted()`'s reuse of CP9's queryset
methods (also lazy, never evaluated); and real, in-process OpenAPI schema
generation confirming every CRM path is present, the enum-naming fix
works, and `GENERATOR_STATS` shows zero warnings/errors.

**Requires database — blocked:** 63 tests in CP10's new files (plus the 1
reclassified CP9 test, 64 total among CP10-attributable blocked tests)
covering full HTTP-level CRUD for all four
resources; the complete three-tier ownership scoping matrix (Employee/
Manager/Super Admin × list/retrieve/update/delete, including a Manager
correctly seeing their team's records via a real CP8 `Team`/`Membership`
setup and NOT seeing an unrelated employee's); search across every
declared field; every filter (`status`, `owner`, `organization`,
`industry`, `is_active`, `source`, the derived `converted`); ordering
(including the `name`→`company_name` alias); pagination (default 20,
override, clamped at 100); validation enforced through the real HTTP layer
(Lead CONVERTED rejection, required-field rejection, duplicate-slug
rejection); and `managed_user_ids()`/`scope_queryset_for_user()`/
`manager_has_access()` against real `Team`/`Membership` rows. All error at
the identical `OperationalError` as every other DB-dependent test since
CP2, zero assertion failures.

Three genuine test-authoring bugs were found and fixed during this
checkpoint's own verification (not production-code bugs) — see "Problems
encountered".

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 / CP8 / CP9 regression

**Blocked**, same pre-existing cause (not a new CP10 regression). Every
CP2–CP9 DB-backed test still errors at DB setup, identically to its own
prior report; every CP2–CP9 DB-free test (including CP9's `test_permissions.py`,
now 7/8 DB-free with the one reclassified test — see "Problems
encountered" — still passing) continues to pass unchanged. CP5's
`SessionListView` was explicitly re-verified functional under the new
project-wide pagination class (see "Pagination"). **None of their statuses
were upgraded to VERIFIED** by CP10's work. Project-wide, the full suite
now reports **301 passed, 252 errors** (up from CP9's own reported 268
passed, 188 errors — the CP10 checkpoint's net contribution matches the
105 new tests plus the 1 reclassified CP9 test described above). 

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP9, re-verified (`psql` not found, no Windows
service, no Docker, no WSL).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP9 (re-verified: no `psql`, no service, no
Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs were
found in CP1–CP9's carried-forward code during Phase 1 verification.

Three test-authoring bugs (not production-code bugs) were found and fixed
during this checkpoint's own test run:

1. **A CP9 test became DB-dependent.** `test_unrelated_manager_denied_on_a_
   contact_they_do_not_own` (in CP9's `test_permissions.py`) exercised
   `IsOwnerOrSuperAdmin` with an unrelated Manager and expected `False` —
   correct at the time, since CP9 had no `manager_has_access()` hook on
   `Customer`/`ContactPerson` (the module-level stub always returned
   `False`, no DB needed). CP10 gave these models a real
   `manager_has_access()` that queries CP8's `Team`/`Membership` via
   `managed_user_ids()` — the same test now genuinely needs a database.
   Marked `@pytest.mark.django_db`; the test's own assertion was still
   correct and needed no logic change, only reclassification.
2. **A wrong assumption about `pagination_class` resolution.** A new
   regression test assumed `SessionListView.pagination_class` would be
   `None` (inheriting the project default lazily); it's actually resolved
   to the concrete class (`StandardPagination`) at class-definition time.
   Fixed the assertion to check for the concrete class instead of `None`.
3. **`/health` assumed to be part of the OpenAPI schema.** A regression
   test asserted `/health` appears in `manage.py spectacular`'s output;
   `/health` is a plain Django view (CP1), never a DRF `APIView`, so
   drf-spectacular has never included it — true before CP10 too. Removed
   the incorrect assertion; the test now only checks real DRF endpoints.

One known, deliberate permission-scoping gap, documented rather than
silently left implicit: CP7's `CanRestoreOrHardDelete` (reused unmodified
for `restore`/`hard-delete`, per "no duplicated permission logic") gates by
ROLE alone (Manager-or-above) — it does NOT check whether the acting
Manager actually manages the specific record's owner's team, unlike
ordinary retrieve/update/destroy, which DO go through `IsOwnerOrSuperAdmin`'s
per-object `manager_has_access()` check. This means any Manager (not just
the "right" one) can restore or hard-delete any record. This is CP7's
existing, unmodified design being reused as-is; extending
`CanRestoreOrHardDelete` to be object-level-aware (or building a CRM-
specific replacement) was judged out of scope for CP10, which asked to
reuse CP6/CP7 infrastructure, not extend it — verified and tested
explicitly (`test_any_manager_can_hard_delete_regardless_of_team`) rather
than silently assumed to be scoped.

### Deferred

- A CRM-specific, object-level-aware restore/hard-delete permission (see
  "Problems encountered" above) — left as a documented gap rather than a
  speculative fix.
- A "convert lead" HTTP endpoint wiring CP9's `services.convert_lead()` to
  the API — CP10's own endpoint spec never listed one for `/leads/`; the
  service function remains complete and tested, only unreachable over
  HTTP.
- Bulk operations (bulk create/update/delete) — not requested.
- Any endpoint versioning beyond the existing `/api/v1/` prefix.

### Next

CP11 (blocked behind the same PostgreSQL issue affecting CP2–CP10's
DB-dependent verification)

---

## CP11 — Sales Pipeline (Opportunities)

**Status:** PARTIAL / BLOCKED (implementation complete. 8 new test files
total 130 tests — 55 pass with no database, 75 blocked; 2 existing CP10
test files (`test_openapi.py`, `test_regression.py`) gained 3 more
DB-free tests each covering CP11's new endpoints/imports. Net: 133 new
tests, 58 pass with no database, 75 blocked. Project-wide: **359 passed,
327 errors** — up from CP10's 301/252, confirming zero regressions.)

### Files created

- `backend/apps/crm/opportunities.py` — `OpportunityQuerySet`/
  `OpportunityManager`/`ActiveOpportunityManager`, `Opportunity`;
  `OpportunityActivity`; `OpportunityNote` — all built on CP7's
  `SoftDeleteTimeStampedModel`, kept in their own module (see that file's
  docstring) but re-exported from `models.py` so Django's app-loading
  machinery discovers them (verified empirically — omitting the re-export
  left them invisible to `apps.get_model()` entirely)
- `backend/apps/crm/migrations/0002_opportunity_opportunityactivity_opportunitynote_and_more.py`
  — hand-inspected; creates all three tables and every declared index
- `backend/apps/crm/tests/test_opportunities_models.py` — 25 tests
- `backend/apps/crm/tests/test_opportunities_managers.py` — 14 tests
- `backend/apps/crm/tests/test_opportunities_services.py` — 23 tests
- `backend/apps/crm/tests/test_opportunities_serializers.py` — 16 tests
- `backend/apps/crm/tests/test_opportunities_permissions.py` — 7 tests
- `backend/apps/crm/tests/test_opportunities_admin.py` — 6 tests
- `backend/apps/crm/tests/test_opportunities_filters.py` — 8 tests
- `backend/apps/crm/tests/test_opportunities_api.py` — 31 tests

### Files modified

- `backend/apps/crm/models.py` — added the re-export import of
  `Opportunity`/`OpportunityActivity`/`OpportunityNote` from
  `opportunities.py` (load-bearing for Django's app registry, not merely
  cosmetic — see "Problems encountered")
- `backend/apps/crm/services.py` — added `create_opportunity()`,
  `advance_stage()`, `mark_won()`, `mark_lost()`, `reopen()`, `add_note()`,
  `add_activity()`; `assign_owner()` reused unmodified (already works for
  anything with an `owner` FK)
- `backend/apps/crm/serializers.py` — added `OpportunitySerializer`/
  `OpportunityDetailSerializer`, `OpportunityActivitySerializer`,
  `OpportunityNoteSerializer`, `OpportunityStageTransitionSerializer`
- `backend/apps/crm/admin.py` — added `OpportunityAdmin`,
  `OpportunityActivityAdmin`, `OpportunityNoteAdmin`, plus
  `OpportunityNoteInline`/`OpportunityActivityInline`
- `backend/apps/crm/filters.py` — added `OpportunityFilterSet`
- `backend/apps/crm/views.py` — added `OpportunityViewSet`
- `backend/apps/crm/urls.py` — registered `opportunities` with the
  existing `DefaultRouter`
- `backend/apps/crm/tests/conftest.py` — added an `opportunity` fixture
- `backend/apps/crm/tests/test_openapi.py` (CP10) — added CP11 path
  checks (1 new test)
- `backend/apps/crm/tests/test_regression.py` (CP10) — added 2 CP11-aware
  regression checks

No other existing file was touched. **No frontend file was read, opened,
or modified.**

### Migration

`apps/crm/migrations/0002_opportunity_opportunityactivity_opportunitynote_and_more.py`
— creates `Opportunity`, `OpportunityActivity`, `OpportunityNote` and six
indexes. One genuine bug was caught and fixed during generation: two
initial index names (`crm_opportunity_customer_stage_idx`,
`crm_opportunity_expected_close_idx`) exceeded PostgreSQL's 30-character
identifier limit, tripping Django's own `models.E034` system check before
any migration was even generated — shortened to `crm_opp_customer_stage_idx`/
`crm_opp_expected_close_idx` (and the two other `is_closed`/`is_won` and
`opportunity`+`occurred_at` indexes renamed to the same `crm_opp_*` prefix
for consistency). `makemigrations --check --dry-run` clean before and
after. **Not applied** — same PostgreSQL blocker as every prior checkpoint.

### Models

- **`Opportunity`** — FK `customer` (`related_name="opportunities"`,
  `CASCADE`), FK `owner` (`related_name="owned_opportunities"`, nullable,
  `SET_NULL`), `title`, `stage` (`NEW`/`QUALIFIED`/`PROPOSAL`/
  `NEGOTIATION`/`WON`/`LOST`), `value` (`DecimalField`, not float — correct
  for money), `probability` (0–100, validated), `expected_close_date`,
  `actual_close_date`, `currency` (ISO 4217, no cross-currency conversion
  attempted), `description`, `is_closed`, `is_won`.
- **`OpportunityActivity`** — FK `opportunity` (`related_name="activities"`,
  `CASCADE`), `activity_type` (`CALL`/`EMAIL`/`MEETING`/`TASK`/`OTHER`),
  `subject`, `notes`, `occurred_at`.
- **`OpportunityNote`** — FK `opportunity` (`related_name="notes"`,
  `CASCADE`), `content`.

All three inherit `SoftDeleteTimeStampedModel` (CP7), same reasoning as
every CP9+ CRM record. `OpportunityActivity`/`OpportunityNote` get `owner`
properties and `manager_has_access()` delegating to their parent
`Opportunity` — the exact `ContactPerson`/`Address` (CP9) pattern.
`Opportunity` itself gets a real `manager_has_access()` reusing CP10's
`managed_user_ids()` directly — zero new permission logic, same as
`Customer`/`Lead`.

### Managers

`Opportunity.objects`/`active_objects` (unfiltered / not-deleted, per CP7
convention — `Opportunity` has no separate business "is_active" flag the
way `Customer` does, so `active_objects` means exactly CP7's own
`.active()`). `OpportunityQuerySet` adds: `by_stage(stage)`, `open()`
(`is_closed=False`), `closed()` (`is_closed=True`), `won()` (`is_won=True`),
`lost()` (`is_closed=True, is_won=False` — closed AND not won, not merely
"not won yet"), `high_value(threshold=10000)`, `expected_this_month(today=None)`
(computes the current calendar month's bounds; `today` injectable for
testing, correctly handles December→January year rollover).
`OpportunityActivity`/`OpportunityNote` use CP7's plain `SoftDeleteManager`/
`ActiveManager` directly — no extra helpers requested for these two models.

### Services

`apps/crm/services.py` additions, implementing CP11's exact business rules:

- `create_opportunity(customer, title, owner=None, **fields)` — thin
  wrapper (no real behavior beyond `.create()`), kept for the same
  single-seam reasoning as `create_lead()`.
- `advance_stage(opportunity, stage)` — moves between OPEN stages only.
  Raises `ValueError` if the opportunity is already closed ("cannot move
  past WON/LOST unless reopened") or if `stage` is `WON`/`LOST` (must use
  `mark_won()`/`mark_lost()` instead).
- `mark_won(opportunity, actual_close_date=None)` — sets `stage=WON`,
  `is_closed=True`, `is_won=True`, `actual_close_date` (defaults to today)
  all together. Raises `ValueError` if already closed.
- `mark_lost(opportunity, actual_close_date=None)` — the LOST counterpart:
  `is_closed=True`, `is_won=False`, `actual_close_date` set.
- `reopen(opportunity, stage=Stage.NEW)` — clears `is_closed`, `is_won`,
  `actual_close_date`, returns to `stage` (`NEW` by default). Raises
  `ValueError` if not currently closed, or if `stage` is `WON`/`LOST`.
- `add_note(opportunity, content, created_by=None)` /
  `add_activity(opportunity, activity_type, subject, ..., created_by=None)`
  — create + optional CP7 `stamp_audit_fields()` audit stamping.
- `assign_owner()` — **reused unmodified from CP9/CP10**; already works
  for `Opportunity` since it only requires an `owner` FK attribute.

### Endpoints

`/api/v1/crm/opportunities/` — the same CRUD shape as every CP10 resource
(`GET`/`POST` list, `GET`/`PATCH`/`DELETE` detail, no `PUT`, plus CP7's
`restore`/`hard-delete`), plus six CP11-specific actions:

| Method | Path | Behavior |
|---|---|---|
| POST | `.../<id>/advance-stage/` | `{"stage": "..."}` → `services.advance_stage()` |
| POST | `.../<id>/mark-won/` | → `services.mark_won()` |
| POST | `.../<id>/mark-lost/` | → `services.mark_lost()` |
| POST | `.../<id>/reopen/` | → `services.reopen()` |
| GET/POST | `.../<id>/notes/` | list / create via `services.add_note()` |
| GET/POST | `.../<id>/activities/` | list / create via `services.add_activity()` |

Business-rule violations (e.g. advancing a closed opportunity) surface as
`400` with a `{"detail": "..."}` body carrying the service function's own
`ValueError` message — no duplicated validation text.

### ViewSets

`OpportunityViewSet(_CrmModelViewSet)` — reuses CP10's shared base
unchanged (HTTP-method restriction, the active-vs-unfiltered
`get_queryset()` split). All six custom actions are reached via
`self.get_object()`, which runs the identical `IsOwnerOrSuperAdmin`
object-level check as ordinary retrieve/update/destroy — none of them
declares its own `permission_classes` override, so "who may close a deal"
is governed by the exact same ownership rule as "who may edit it."

### Filtering

`OpportunityFilterSet`: `stage`, `owner`, `customer` (exact match, via
`Meta.fields`); `closed`/`won` (short aliases for `is_closed`/`is_won`);
`expected_close_date_from`/`_to` and `actual_close_date_from`/`_to` (date
ranges); `value_min`/`value_max` (value ranges) — each bound independently
optional, so `?value_min=10000` alone is a valid "at least $10k" filter.

### Searching

`title`, `customer__name`, `description` — exactly CP11's spec.

### Ordering

`title`, `value`, `probability`, `expected_close_date`, `created_at`,
`updated_at`, `stage` — a superset of CP10's Customer/Lead ordering shape,
extended with the sales-pipeline-specific sort keys (`value`,
`expected_close_date`) that make sense for a forecasting view.

### Pagination

Uses CP10's project-wide `StandardPagination` unchanged — no
Opportunity-specific pagination configuration needed or added.

### Permissions

**No duplicated permission logic** (CP11 spec: "Reuse CP6 RBAC. Reuse CP10
queryset scoping."). `OpportunityViewSet` uses the exact same
`[IsAuthenticated, IsOwnerOrSuperAdmin]` as every CP10 viewset, with
`owner_field = "owner"` (`Opportunity`'s own real FK). `Opportunity
.manager_has_access()` calls CP10's `managed_user_ids()` directly — the
identical function `Customer`/`Lead.manager_has_access()` already call —
so an Opportunity's Manager-visibility rules can never drift from a
Customer's or a Lead's. `OpportunityActivity`/`OpportunityNote` delegate
both `owner` and `manager_has_access()` to their parent `Opportunity`,
mirroring `ContactPerson`/`Address` (CP9) exactly.

### OpenAPI

`manage.py spectacular --file schema.yaml` — zero errors, zero warnings,
achieved on the first schema-generation run (no fix needed this
checkpoint, unlike CP10's enum-collision warning). All ten Opportunity
paths (list/detail plus the six custom actions plus `restore`/
`hard-delete`) verified present in the generated schema, both via the CLI
and via `test_openapi.py`'s in-process `SchemaGenerator` check.

### Tests

**No database required — genuinely executed, genuinely passing:** 58/58
across the 8 new test files plus the additions to `test_openapi.py`/
`test_regression.py`. Covers every field/constraint/Meta definition,
`__str__`/property/`manager_has_access()` behavior on in-memory instances
(the owner-direct and Super-Admin-override permission paths — the
Manager-not-owner path needs a database, see below), every queryset
helper's compiled filter (including `expected_this_month()`'s December→
January rollover, computed with an injectable `today` so no test depends
on when it runs), serializer field declarations and the stage-transition
`validate_stage()` rejection (tested directly as a field-level validator
call, DB-free — see "Problems encountered" for why the FULL serializer
validation of the same rule needs a database), the admin registry, filter
class declarations and their compiled queries, and OpenAPI schema
generation for every new path.

**Requires database — blocked:** 75 tests covering real persistence and
cascade behavior; the complete stage-machine business-rule matrix end to
end (`advance_stage`/`mark_won`/`mark_lost`/`reopen`, every raised
`ValueError` case, the full won→reopen→advance cycle); `add_note()`/
`add_activity()` audit stamping; the Manager-not-owner permission path
(queries CP8's `Team`/`Membership`); full HTTP-level CRUD, all six custom
actions (including ownership enforcement on `mark-won`, and soft-deleted
notes correctly excluded from the `notes` list action); search, filtering
(including value/date ranges), and ordering. All error at the identical
`OperationalError` as every other DB-dependent test since CP2, zero
assertion failures.

Two genuine bugs were found and fixed during this checkpoint's own
verification:

1. **A production-code bug** (the index-name-length issue — see
   "Migration"), caught by `manage.py check` before any migration was
   even generated.
2. **A test-authoring bug** (not production code): three new serializer
   tests assumed `OpportunitySerializer(data={"customer": 1, ...})` needed
   no database, but `customer` is a `PrimaryKeyRelatedField` that queries
   the database to confirm the referenced row exists, regardless of
   whether validation ultimately succeeds. Fixed by splitting
   `validate_stage()` into its own DB-free direct-call tests (exercising
   just that one field validator, which needs no FK to exist) plus a
   smaller set of full-serializer DB-required tests using a real
   `customer` fixture.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 / CP8 / CP9 / CP10 regression

**Blocked**, same pre-existing cause (not a new CP11 regression). Every
prior checkpoint's DB-backed tests still error at DB setup identically to
their own prior reports; every prior checkpoint's DB-free tests continue
to pass unchanged. CP10's own new endpoints/routes (`customers`, `leads`,
`contacts`, `addresses`) explicitly re-verified still resolving and
unaffected by CP11's new `opportunities` route. **None of their statuses
were upgraded to VERIFIED** by CP11's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP10, re-verified (`psql` not found, no
Windows service, no Docker, no WSL).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP10 (re-verified: no `psql`, no service, no
Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs were
found in CP1–CP10's carried-forward code during Phase 1 verification.

One genuine production-code bug this checkpoint (see "Migration" above):
two auto-generated index names exceeded PostgreSQL's 30-character
identifier limit, caught by `manage.py check`'s `models.E034` before any
migration was generated — fixed by shortening the `crm_opportunity_*`
prefix to `crm_opp_*` across all four `Opportunity` indexes.

One test-authoring bug (see "Tests" above): a `PrimaryKeyRelatedField`
query-the-database-during-validation gotcha, the same class of mistake
CP8/CP10 already documented — a reminder that ANY serializer field
referencing a real FK, not just ones with explicit uniqueness validators,
can make an otherwise "just checking one field's logic" test
DB-dependent. Fixed by isolating the field-level validator call from the
full serializer's FK resolution.

One design decision worth recording: **`opportunities.py` is a separate
module from `models.py`**, per CP11's own offered alternative ("or
integrate into models.py if preferred"). This required an explicit
re-export import at the bottom of `models.py` — Django's app-loading
machinery only auto-discovers models from the app's actual `models`
module, not arbitrary sibling files, confirmed empirically (`apps
.get_model("crm", "Opportunity")` raised `LookupError` until the
re-export was added). This is documented at length in both files so a
future checkpoint following the same "separate module" pattern doesn't
rediscover the same surprise.

### Deferred

- Reporting/forecasting aggregation endpoints (pipeline value by stage,
  win-rate, forecast-vs-actual) — CP11 builds the data model and the raw
  filtering primitives (`high_value()`, `expected_this_month()`, `won()`,
  `lost()`) these would be built on, but no aggregation/reporting endpoint
  itself was requested or built.
- Bulk stage transitions (e.g. moving many opportunities at once) — not
  requested.
- An object-level-aware permission for the six new custom actions beyond
  what `IsOwnerOrSuperAdmin` already provides — not needed; unlike CP10's
  `restore`/`hard-delete` (which use CP7's role-only
  `CanRestoreOrHardDelete`), every CP11 action already goes through the
  full ownership check via `self.get_object()`.

### Next

CP12 (blocked behind the same PostgreSQL issue affecting CP2–CP11's
DB-dependent verification)

---

## CP12 — Quoting & Invoicing (Sales)

**Status:** PARTIAL / BLOCKED (implementation complete. `apps/sales/`
totals 141 tests across 11 files — 71 genuinely pass with no database, 70
require a real database and are blocked. Project-wide: **430 passed, 397
errors** — up from CP11's 359/327, confirming zero regressions.)

### Files created

- `backend/apps/sales/{__init__.py, apps.py, models.py, services.py,
  serializers.py, permissions.py, admin.py, filters.py, views.py,
  urls.py}` — a genuinely new Django app (unlike CP11's `Opportunity`,
  folded into `apps.crm`) since quoting/invoicing is its own commercial-
  document domain with its own numbering/approval/payment lifecycle, not
  another shape of CRM account data
- `backend/apps/sales/migrations/0001_initial.py` — hand-inspected;
  creates all four tables (`Invoice` before `Quote`, then a deferred
  `AddField` for `Invoice.quote` once `Quote` exists — Django's standard
  resolution for the `Quote.converted_invoice` ↔ `Invoice.quote` circular
  FK pair) and every declared index
- `backend/apps/sales/tests/{conftest, test_models, test_managers,
  test_services, test_serializers, test_permissions, test_admin,
  test_filters, test_api, test_urls, test_openapi, test_regression}.py`
  — 141 tests (71 pass with no database, 70 blocked)

### Files modified

- `backend/config/settings/base.py` — added `"apps.sales"` to
  `LOCAL_APPS`; added `QuoteStatusEnum`/`InvoiceStatusEnum` to
  `ENUM_NAME_OVERRIDES` (same `status`-field-name collision as CP10's
  Customer/Lead pair — see "OpenAPI")
- `backend/config/urls.py` — mounted `apps.sales.urls` at `/api/v1/sales/`

No other existing file was touched. **No frontend file was read, opened,
or modified.**

### Migration

`apps/sales/migrations/0001_initial.py` — creates `Invoice`, `Quote`,
`QuoteItem`, `InvoiceItem` and 7 indexes. One genuine bug caught by
`manage.py check` before generation (the same class of mistake CP11 hit):
four auto-derived index names exceeded PostgreSQL's 30-character
identifier limit (`sales_quote_customer_status_idx`,
`sales_invoice_customer_status_idx`, `sales_quoteitem_quote_order_idx`,
`sales_invoiceitem_inv_order_idx`) — shortened
(`sales_quote_cust_status_idx`, `sales_invoice_cust_status_idx`,
`sales_quoteitem_order_idx`, `sales_invoiceitem_order_idx`).
`makemigrations --check --dry-run` clean before and after. **Not
applied** — same PostgreSQL blocker as every prior checkpoint.

### Models

- **`Quote`** — FK `customer` (`CASCADE`), FK `opportunity` (nullable,
  `SET_NULL`, links back to CP11), FK `owner` (nullable, `SET_NULL`),
  `quote_number` (unique), `status` (`DRAFT`/`SUBMITTED`/`APPROVED`/
  `REJECTED`/`CONVERTED`), `valid_until`, `subtotal`/`tax`/`total`
  (`DecimalField`, not float), `notes`, `approved_by`/`approved_at`
  (nullable), `converted_invoice` (nullable FK to `Invoice`, the
  forward-reference side of the circular pair with `Invoice.quote`).
- **`QuoteItem`** — FK `quote` (`CASCADE`), `product_name`,
  `description`, `quantity`/`unit_price`/`total_price` (all `Decimal`,
  `total_price` always computed, never client-set), `ordering`
  (explicit `PositiveIntegerField` for display order).
- **`Invoice`** — FK `customer` (`CASCADE`), FK `quote` (nullable,
  `SET_NULL`, the reverse side of the pair with `Quote.converted_invoice`),
  FK `owner` (nullable, `SET_NULL`), `invoice_number` (unique), `status`
  (`DRAFT`/`SENT`/`PAID`/`CANCELLED`), `due_date`,
  `subtotal`/`tax`/`total`, `paid_at`.
- **`InvoiceItem`** — same shape as `QuoteItem`, FK `invoice`.

All four inherit `SoftDeleteTimeStampedModel` (CP7). `Quote`/`Invoice`
expose a plain `owner` FK (CP6's `resolve_owner()` finds it automatically)
plus a `manager_has_access()` reusing CP10's `managed_user_ids()`
**imported directly from `apps.crm.services`**, not reimplemented — the
fourth model (after `Customer`/`Lead`/`Opportunity`) to reuse it.
`QuoteItem`/`InvoiceItem` delegate `owner`/`manager_has_access()` to their
parent, the same `ContactPerson`/`Address` (CP9) / `OpportunityActivity`/
`OpportunityNote` (CP11) pattern, now established a fourth time.

### Managers

`Quote.objects`/`active_objects` + `QuoteQuerySet.draft()`/`.submitted()`/
`.approved()`/`.rejected()`/`.converted()`. `Invoice.objects`/
`active_objects` + `InvoiceQuerySet.draft()`/`.sent()`/`.paid()`/
`.cancelled()`/`.overdue(today=None)` (past `due_date`, excluding
`PAID`/`CANCELLED`; `today` injectable for testing, same reasoning as
CP11's `expected_this_month()`). `QuoteItem`/`InvoiceItem` use CP7's plain
managers directly — no extra helpers requested for line items.

### Services

`apps/sales/services.py`, implementing every CP12 business rule:

- `create_quote()` / `create_invoice()` — thin wrappers.
- `add_quote_item()` / `add_invoice_item()` — compute `total_price`
  (`quantity * unit_price`, never accepted from a caller), auto-assign
  `ordering` when omitted, and call `recalculate_*_totals()` — "totals
  automatically recalculate."
- `recalculate_quote_totals()` / `recalculate_invoice_totals()` — sum
  active line items into `subtotal`, add the (separately-set) `tax` into
  `total`. Exposed directly, not just as a side effect of adding an item.
- `submit_quote()` — `DRAFT` → `SUBMITTED` only.
- `approve_quote()` — `SUBMITTED` → `APPROVED` only ("cannot approve
  draft"); stamps `approved_by`/`approved_at` together.
- `reject_quote()` — `SUBMITTED` → `REJECTED` only ("cannot reject
  approved" — and, by the same check, cannot reject a draft either).
- `convert_quote_to_invoice()` — "cannot convert unless approved";
  creates the `Invoice` (`status=SENT` — "invoice starts SENT"), copies
  line items, links both sides (`quote.converted_invoice` and
  `invoice.quote`), sets `quote.status=CONVERTED`. **Idempotent**: a
  second call on an already-converted quote returns the existing invoice
  rather than erroring or duplicating.
- `mark_invoice_paid()` — "cancelled invoice cannot become paid" (and
  cannot re-mark an already-paid invoice).
- `cancel_invoice()` — "paid invoice cannot be cancelled" (and cannot
  re-cancel an already-cancelled invoice).
- `assign_owner()` — **reused unmodified, imported directly from
  `apps.crm.services`** rather than redefined a third time.

### Endpoints

`/api/v1/sales/quotes/`, `/invoices/` — full CRUD (no PUT) + CP7's
`restore`/`hard-delete`, plus:

| Method | Path | Behavior |
|---|---|---|
| POST | `quotes/<id>/submit/` | → `services.submit_quote()` |
| POST | `quotes/<id>/approve/` | → `services.approve_quote()` |
| POST | `quotes/<id>/reject/` | → `services.reject_quote()` |
| POST | `quotes/<id>/convert/` | `{"invoice_number": "..."}` → `services.convert_quote_to_invoice()` |
| POST | `invoices/<id>/mark-paid/` | → `services.mark_invoice_paid()` |
| POST | `invoices/<id>/cancel/` | → `services.cancel_invoice()` |

`/api/v1/sales/quote-items/`, `/invoice-items/` are also registered as
their own ordinary CRUD resources (full CRUD + restore/hard-delete) — a
deliberate departure from CP11's nested-action choice for notes/
activities, since CP12's own API spec never bundles line items under
their parent resource the way CP11's spec bundled notes/activities; the
CP10 precedent (`ContactPerson`/`Address` as separate top-level resources)
is the better fit here.

### ViewSets

`QuoteViewSet`, `InvoiceViewSet`, `QuoteItemViewSet`, `InvoiceItemViewSet`
— all built on **CP10's `_CrmModelViewSet`, imported directly from
`apps.crm.views`** rather than redefined. All six custom actions are
reached via `self.get_object()`, running the identical `IsOwnerOrSuperAdmin`
check as ordinary retrieve/update/destroy — none declares its own
`permission_classes` override.

### Filtering

`QuoteFilterSet`: `owner`, `customer`, `status` (exact); `valid_until_from`/
`_to` (range). `InvoiceFilterSet`: `owner`, `customer`, `status` (exact);
`due_date_from`/`_to` (range); `paid` (a friendlier boolean alias for
`status=PAID`, reusing `InvoiceQuerySet.paid()`).

### Searching

`Quote`: `quote_number`, `customer__name`. `Invoice`: `invoice_number`,
`customer__name`.

### Ordering

`Quote`: `created_at`, `valid_until`, `total`, `status`. `Invoice`:
`created_at`, `due_date`, `total`, `status`.

### Permissions

**No duplicated permission logic.** `[IsAuthenticated, IsOwnerOrSuperAdmin]`
on every viewset, identical to every CP10/CP11 viewset. `Quote`/
`Invoice.manager_has_access()` call CP10's `managed_user_ids()` directly
(cross-app import from `apps.crm.services`) — the same function every
other CRM/sales model with an `owner` FK already calls, so a Manager's
"team records" visibility can never drift between apps.

### OpenAPI

`manage.py spectacular --file schema.yaml` — zero errors, zero warnings.
One genuine warning found and fixed during implementation: `Quote.Status`
and `Invoice.Status` collide on the field name `status`, the identical
class of issue CP10 hit with `Customer`/`Lead` — fixed via the same
`ENUM_NAME_OVERRIDES` mechanism, extended with two more entries.

### Tests

**No database required — genuinely executed, genuinely passing:** 71/71.
Covers every field/constraint/Meta definition, `__str__`/property/
`manager_has_access()` behavior on in-memory instances, every queryset
helper's compiled filter (including `overdue()`'s injectable `today`),
serializer field declarations (every workflow-only field — `status`,
`subtotal`/`total`, `approved_by`/`approved_at`/`converted_invoice`,
`paid_at`, item `total_price` — confirmed read-only on every serializer,
including the writable ones), the admin registry, filter class
declarations, URL routing for every endpoint including all six custom
actions, and OpenAPI schema generation.

**Requires database — blocked:** 70 tests covering real persistence and
cascade behavior; the complete business-rule matrix end to end (submit/
approve/reject draft-vs-submitted-vs-approved guards, the full convert
idempotency check, mark-paid/cancel terminal-state guards); line-item
total computation and auto-ordering; full HTTP-level CRUD and all six
custom actions (including ownership enforcement and the idempotent
convert-twice API call); the Manager-not-owner permission path; search,
filtering (including the `paid`/date-range filters), and ordering. All
error at the identical `OperationalError` as every other DB-dependent
test since CP2, zero assertion failures.

No test-authoring bugs were found this checkpoint (unlike CP10/CP11, each
of which caught one) — every DB-free test was correctly classified on the
first run.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 / CP8 / CP9 / CP10 / CP11 regression

**Blocked**, same pre-existing cause (not a new CP12 regression). Every
prior checkpoint's DB-backed tests still error at DB setup identically to
their own prior reports; every prior checkpoint's DB-free tests continue
to pass unchanged. CP10's/CP11's own endpoints (`customers`, `leads`,
`contacts`, `addresses`, `opportunities`) explicitly re-verified still
resolving and unaffected by CP12's new `apps.sales` app/routes. **None of
their statuses were upgraded to VERIFIED** by CP12's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP11, re-verified (`psql` not found, no
Windows service, no Docker, no WSL).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP11 (re-verified: no `psql`, no service, no
Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs were
found in CP1–CP11's carried-forward code during Phase 1 verification.

One genuine production-code bug this checkpoint (see "Migration" above):
four auto-generated index names exceeded PostgreSQL's 30-character
identifier limit — the identical class of mistake CP11 hit one checkpoint
earlier, caught the same way (`manage.py check`'s `models.E034`, before
any migration was generated) and fixed the same way (shortening the
prefix). No test-authoring mistakes this checkpoint.

Two design decisions worth recording:

1. **`apps.sales` is a genuinely new app**, not folded into `apps.crm` the
   way CP11's `Opportunity` was folded into `apps.crm.opportunities`.
   Quoting/invoicing has its own numbering, approval, and payment
   lifecycle — a distinct commercial-document domain, not another shape
   of CRM account/contact data.
2. **Two pieces of CP10 infrastructure were imported directly across app
   boundaries** rather than reimplemented: `_CrmModelViewSet`
   (`apps.crm.views`) and `managed_user_ids()`/`assign_owner()`
   (`apps.crm.services`). `apps.sales` already depends on `apps.crm` for
   `Customer`/`Opportunity`, so this is a natural extension of an existing
   dependency, not a new architectural coupling — and it's exactly what
   CP12's "reuse existing infrastructure... do not duplicate" instruction
   asked for. A future third consumer of `_CrmModelViewSet` would be the
   natural trigger to promote it to `apps.core.views` — not done here
   since CP12 didn't ask for that refactor and only two apps use it today.

### Deferred

- Reporting endpoints (quote win-rate, invoice aging/collections) — CP12
  builds the data model and raw filtering primitives (`overdue()`,
  the five `Quote` stage helpers) these would be built on, but no
  aggregation endpoint itself was requested.
- A "send invoice" transition moving a directly-created `DRAFT` invoice to
  `SENT` — not requested; only conversion-created invoices reach `SENT`
  in this checkpoint (a directly-created invoice starts `DRAFT` and has no
  action to advance it, since only `mark-paid`/`cancel` were requested).
- An object-level-aware permission for `restore`/`hard-delete` beyond
  CP7's role-only `CanRestoreOrHardDelete` — same known, documented gap
  CP11 already recorded; unchanged here.

### Next

CP13 (blocked behind the same PostgreSQL issue affecting CP2–CP12's
DB-dependent verification)

---

## CP13 — Product/Service Catalog & Price Books

**Status:** PARTIAL / BLOCKED (implementation complete. `apps/catalog/`
totals 102 tests across 11 files — 59 genuinely pass with no database, 43
require a real database and are blocked. Project-wide: **489 passed, 440
errors** — up from CP12's 430/397, confirming zero regressions.)

### Files created

- `backend/apps/catalog/{__init__.py, apps.py, models.py, services.py,
  serializers.py, permissions.py, admin.py, filters.py, views.py,
  urls.py}` — a genuinely new Django app: catalog data (what exists to be
  sold, and at what list price) is shared reference data with no
  per-salesperson ownership, a different access shape from every prior
  CRM/sales model
- `backend/apps/catalog/migrations/0001_initial.py` — hand-inspected;
  creates `PriceBook`, `Product`, `Service`, `PriceBookEntry` and every
  declared index/constraint
- `backend/apps/catalog/tests/{conftest, test_models, test_managers,
  test_services, test_serializers, test_permissions, test_admin,
  test_filters, test_api, test_urls, test_openapi, test_regression}.py`
  — 102 tests (59 pass with no database, 43 blocked)

### Files modified

- `backend/config/settings/base.py` — added `"apps.catalog"` to
  `LOCAL_APPS`
- `backend/config/urls.py` — mounted `apps.catalog.urls` at
  `/api/v1/catalog/`

No other existing file was touched. **No frontend file was read, opened,
or modified.**

### Migration

`apps/catalog/migrations/0001_initial.py` — creates all four tables, 3
indexes, and 3 constraints (a `CheckConstraint` enforcing "exactly one of
`product`/`service`", plus two partial `UniqueConstraint`s — "at most one
entry per product per price book" and the same for service). No
index-name-length issue this time (unlike CP11/CP12) — every name checked
against the 30-character limit while writing the model, not after.
`makemigrations --check --dry-run` clean before and after. **Not
applied** — same PostgreSQL blocker as every prior checkpoint.

### Models

- **`Product`** — `name`, `sku` (unique), `description`, `default_price`
  (`Decimal`), `currency`, `is_active`.
- **`Service`** — `name`, `code` (unique — services aren't stocked, so a
  deliberately different field name from `Product.sku`), `description`,
  `default_rate` (`Decimal`), `currency`, `is_active`.
- **`PriceBook`** — `name` (unique), `description`, `currency`
  (price-book-wide, every entry in it assumed denominated in it),
  `is_active`.
- **`PriceBookEntry`** — `price_book` (`CASCADE`), `product` (nullable,
  `CASCADE`), `service` (nullable, `CASCADE`), `price`, `is_active`.
  Exactly one of `product`/`service` must be set — enforced by a
  `CheckConstraint`, not merely convention.

All four inherit `SoftDeleteTimeStampedModel` (CP7). All four have their
own `is_active` business flag, independent of soft delete — the same
"two independent booleans" shape CP9's `Customer` established, reused
here via a new shared `CatalogItemQuerySet.active()` override (not a
copy-pasted one per model).

### Managers

`CatalogItemQuerySet` (shared by `Product`/`Service`/`PriceBook`):
overrides CP7's `active()` to also require `is_active=True`, the same
override pattern CP9's `CustomerQuerySet` established. `PriceBookEntryQuerySet`
adds the same `active()` override plus `for_product(product)`/
`for_service(service)`. All four models get `objects`
(unfiltered)/`active_objects` (not-deleted AND business-active) per CP7's
convention.

### Services

`apps/catalog/services.py`: `create_product()`, `create_service()`,
`create_pricebook()` (thin wrappers, single-seam reasoning), `add_pricebook_entry()`
(validates exactly one of `product`/`service` up front — `ValueError`
otherwise — mirroring the model's own check constraint with a friendlier
error, same "constraint is the real guarantee, validation is UX" layering
CP9 established), `update_pricebook_price()`, `deactivate_pricebook_entry()`
(sets `is_active=False` WITHOUT soft-deleting — retiring a price without
losing its history, the same distinction CP9's `Customer.is_active` drew).

### Endpoints

`/api/v1/catalog/{products,services,pricebooks,pricebook-entries}/` — full
CRUD (no PUT) + CP7's `restore`/`hard-delete`, sixteen routes total.

### ViewSets

`ProductViewSet`, `ServiceViewSet`, `PriceBookViewSet`,
`PriceBookEntryViewSet` — built on CP7's
`SoftDeleteAuditModelViewSetMixin` directly (soft-delete-on-DELETE, audit
stamping, restore/hard-delete). Deliberately does NOT reuse CP10's
`_CrmModelViewSet` — that base's `get_queryset()` scopes by `owner_field`/
`scope_queryset_for_user()`, which assumes an `owner` FK catalog models
don't have. A new, small `_CatalogModelViewSet` provides the identical
HTTP-method restriction and active-vs-unfiltered `get_queryset()` split
without any ownership layer — reusing what applies, not force-fitting
what doesn't.

### Filtering

`Product`/`Service`/`PriceBook`: `is_active`, `currency`.
`PriceBookEntry`: `price_book`, `product`, `service`, `is_active`, plus
`price_min`/`price_max` range filters.

### Searching

`Product`: `name`, `sku`, `description`. `Service`: `name`, `code`,
`description`. `PriceBook`: `name`, `description`. `PriceBookEntry`:
`product__name`, `product__sku`, `service__name`, `service__code`.

### Ordering

`Product`: `name`, `default_price`, `created_at`, `updated_at`.
`Service`: `name`, `default_rate`, `created_at`, `updated_at`.
`PriceBook`: `name`, `created_at`, `updated_at`. `PriceBookEntry`:
`price`, `created_at`, `updated_at`.

### Pagination

CP10's project-wide `StandardPagination`, unchanged — no
catalog-specific configuration needed.

### Permissions

**No duplicated RBAC logic.** Catalog data has no owner, so CP10's
ownership-scoping model doesn't apply — instead, "any authenticated user
may read; only a Manager-or-above may write" is expressed by composing
two EXISTING CP6 classes with DRF's own built-in permission `|` (OR)
operator, not by writing a new permission class:

    CatalogWritePermission = ReadOnlyOrSuperAdmin | IsManagerOrSuperAdmin

Verified directly (both via a truth-table unit test and empirically before
relying on it): an Employee can read but not write; a Manager can do
both; a Super Admin can do both; an anonymous request is denied entirely.
Zero new role-comparison code.

### OpenAPI

`manage.py spectacular --file schema.yaml` — zero errors, zero warnings,
achieved on the FIRST schema-generation run (no enum-collision fix needed
this time — no two catalog models share a colliding field name the way
CP10's `Customer`/`Lead` or CP12's `Quote`/`Invoice` did).

### Tests

**No database required — genuinely executed, genuinely passing:** 59/59.
Covers every field/constraint/Meta definition, `__str__`/property
behavior on in-memory instances, every queryset helper's compiled filter,
serializer field declarations and the `exactly_one_of_product_or_service`
validation (tested as a direct `validate()` call — genuinely DB-free,
since it never touches an FK field's `to_internal_value()`), the
`CatalogWritePermission` truth table (employee read/no-write,
manager/super-admin full access, anonymous denied), the admin registry,
filter class declarations, URL routing for all sixteen endpoints, and
OpenAPI schema generation.

**Requires database — blocked:** 43 tests covering real persistence and
cascade behavior; both the check constraint and the two partial unique
constraints actually rejecting bad rows; full HTTP-level CRUD and
permission enforcement (employee 403 on write, manager 201/200/204,
restore/hard-delete gating); search/filter/ordering/pagination; and the
full serializer validation path for `PriceBookEntry` (its `product`/
`service` PK fields query the database during validation). All error at
the identical `OperationalError` as every other DB-dependent test since
CP2, zero assertion failures.

One genuine (non-production-blocking) issue was found and fixed during
this checkpoint's own test run: `CheckConstraint(check=...)` triggered a
`RemovedInDjango60Warning` (this Django version deprecates the `check`
keyword in favor of `condition`) — fixed by using `condition=` instead,
confirmed via a clean re-run with the warning gone and
`makemigrations --check --dry-run` still reporting no changes (the
migration's serialized form was already `condition=` either way — this
was purely a call-site deprecation, not a schema change). No
test-authoring mistakes this checkpoint.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 / CP8 / CP9 / CP10 / CP11 / CP12 regression

**Blocked**, same pre-existing cause (not a new CP13 regression). Every
prior checkpoint's DB-backed tests still error at DB setup identically to
their own prior reports; every prior checkpoint's DB-free tests continue
to pass unchanged. CP10's/CP11's/CP12's own endpoints explicitly
re-verified still resolving and unaffected by CP13's new `apps.catalog`
app/routes. **None of their statuses were upgraded to VERIFIED** by
CP13's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP12, re-verified (`psql` not found, no
Windows service, no Docker, no WSL).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP12 (re-verified: no `psql`, no service, no
Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs were
found in CP1–CP12's carried-forward code during Phase 1 verification.

One deprecation warning (not an error, not a production bug) was found
and fixed during this checkpoint's own test run — see "Tests" above.
Unlike CP11/CP12, no index-name-length bug occurred this checkpoint (every
name was pre-checked against the 30-character limit while writing the
model, applying the lesson from the two prior checkpoints proactively).
No test-authoring mistakes.

One design decision worth recording: **catalog models have no `owner`
FK, and `apps.catalog.permissions` does not reuse CP10's ownership-scoping
model at all.** This is a deliberate recognition that not every domain
fits the "Employee owns their own records" shape CP9–CP12 established —
catalog data is shared reference data. Rather than forcing an artificial
owner concept onto `Product`/`Service`/`PriceBook`, the simpler, correct
access rule ("read: anyone; write: Manager-or-above") was expressed by
composing two existing CP6 permission classes with DRF's built-in `|`
operator — genuinely zero new logic, not a workaround.

### Deferred

- Currency conversion/normalization across price books in different
  currencies — same deliberately-out-of-scope reasoning CP11 already
  recorded for `Opportunity.currency`.
- A "clone price book" or "bulk price update" action — not requested.
- Product/Service categorization or tagging — not requested; the current
  models are deliberately minimal (name + unique identifier + price/rate +
  description + is_active).

### Next

CP14 (blocked behind the same PostgreSQL issue affecting CP2–CP13's
DB-dependent verification)

---

## CP14 — Activities (Tasks, Events, Activity Log, Reminders)

**Status:** PARTIAL / BLOCKED (implementation complete. `apps/activities/`
totals 134 tests across 11 files — 78 genuinely pass with no database, 56
require a real database and are blocked. Project-wide: **567 passed, 496
errors** — up from CP13's 489/440, confirming zero regressions.)

### Files created

- `backend/apps/activities/{__init__.py, apps.py, models.py, services.py,
  serializers.py, permissions.py, admin.py, filters.py, views.py,
  urls.py}` — a genuinely new Django app: the first checkpoint whose
  models attach to more than one kind of CRM entity, via Django's
  contenttypes framework rather than five separate nullable FK columns.
- `backend/apps/activities/migrations/0001_initial.py` — hand-inspected;
  creates `Event`, `Task`, `Reminder`, `ActivityLog` and every declared
  index/constraint.
- `backend/apps/activities/tests/{conftest, test_models, test_managers,
  test_services, test_serializers, test_permissions, test_admin,
  test_filters, test_api, test_urls, test_openapi, test_regression}.py`
  — 134 tests (78 pass with no database, 56 blocked).

### Files modified

- `backend/config/settings/base.py` — added `"apps.activities"` to
  `LOCAL_APPS`.
- `backend/config/urls.py` — mounted `apps.activities.urls` at
  `/api/v1/activities/`.

No other existing file was touched. **No frontend file was read, opened,
or modified.**

### Migration

`apps/activities/migrations/0001_initial.py` — creates all four tables, 9
indexes, and 2 constraints (`activities_event_end_after_start` — a
`CheckConstraint` rejecting `end_at < start_at` — and
`activities_reminder_exactly_one_of_task_or_event`, the same "exactly one
of two FKs" technique CP13's `PriceBookEntry` established). Every index
name checked against PostgreSQL's identifier limits while writing the
model (the CP11/CP12 lesson, applied proactively again, as in CP13).
`makemigrations --check --dry-run` clean before and after. **Not
applied** — same PostgreSQL blocker as every prior checkpoint.

### Models

- **`Task`** — `title`, `description`, `owner` (ownership-scoping FK),
  `assigned_to` (a separate "who's actually doing this" FK — CP14's
  "support assignment" requirement, distinct from ownership), `priority`
  (LOW/MEDIUM/HIGH/URGENT), `status` (PENDING/IN_PROGRESS/COMPLETED/
  CANCELLED), `due_date`, `completed_at`.
- **`Event`** — `title`, `description`, `owner`, `location`, `start_at`,
  `end_at` (constrained `>= start_at`), `recurrence_frequency`
  (NONE/DAILY/WEEKLY/MONTHLY/YEARLY — "basic recurrence only", per CP14's
  own wording), `recurrence_end_date`.
- **`ActivityLog`** — `actor`, `activity_type` (NOTE/CALL/EMAIL/MEETING/
  STATUS_CHANGE/OTHER), `description`, `occurred_at`. The generic
  counterpart to CP11's `OpportunityActivity` (which is
  Opportunity-only); this one logs against any of the five CRM entities.
- **`Reminder`** — `task` (nullable), `event` (nullable — exactly one of
  the two required), `remind_at`, `message`, `is_sent`. Deliberately NOT
  generic to the five CRM entities directly — a reminder only makes
  sense attached to a `Task` or `Event` ("remind me before this is
  due"/"before this starts"), so it uses two plain FKs with an
  exactly-one-of constraint instead of the contenttypes machinery below.

All four inherit `SoftDeleteTimeStampedModel` (CP7).

**`Task`/`Event`/`ActivityLog`** additionally inherit a new abstract
mixin, `RelatedToEntityModel` — `content_type` (`ForeignKey` to
`ContentType`, `limit_choices_to` narrowed to exactly `crm.customer`,
`crm.lead`, `crm.opportunity`, `sales.quote`, `sales.invoice`),
`object_id` (`PositiveBigIntegerField`, matching every model's
`BigAutoField` PK), and `related_object` (`GenericForeignKey`). This is
the first checkpoint to use `django.contrib.contenttypes` — CP14 needed
one model to optionally attach to any of FIVE unrelated concrete models,
which a single regular `ForeignKey` cannot express and five nullable FK
columns (four of which would always be NULL on every row) would be worse
than the contenttypes-based alternative. Each concrete subclass declares
its OWN `(content_type, object_id)` index with a model-specific name —
deliberately not declared on the abstract mixin itself, since PostgreSQL
index names are unique per-schema (not per-table); an index name
inherited unchanged from an abstract base across `Task`/`Event`/
`ActivityLog` would collide.

### Managers

`TaskQuerySet` (`for_entity(entity)`, `open()` — excludes COMPLETED/
CANCELLED), `EventQuerySet` (`for_entity(entity)`, `upcoming()`),
`ActivityLogQuerySet` (`for_entity(entity)`), `ReminderQuerySet`
(`pending()`, `due(as_of=...)`). All four models get `objects`
(unfiltered)/`active_objects` (not-deleted) per CP7's convention —
`Reminder` has no separate business-active flag the way CP9's `Customer`
does, so its `active_objects` is CP7's plain not-deleted `active()`,
unmodified.

### Services

`apps/activities/services.py` re-exports CP10's `managed_user_ids()`/
`scope_queryset_for_user()` from `apps.crm.services` UNCHANGED (imported,
not copied) — per CP14's "Use CP6 permissions"/"Do not duplicate logic"
rules. New functions: `create_task()`/`create_event()` (accept an
optional `related_object=` kwarg, resolving it into `content_type`/
`object_id` so callers never touch the contenttypes framework directly),
`reassign_task()`, `complete_task()`/`cancel_task()` (same "already
closed" `ValueError` guard shape as CP11's `mark_won()`/`mark_lost()`),
`generate_occurrences()` (pure date-math — DAILY/WEEKLY/MONTHLY/YEARLY
stepping, clamping day-of-month for short months, e.g. Jan 31 + 1 month
→ Feb 28 — NOT a full RFC 5545 RRULE engine; returns a list of
`datetime`s without persisting anything), `log_activity()` (the generic
counterpart to CP11's `add_activity()`), `create_reminder()` (validates
exactly-one-of `task`/`event`, mirroring the DB constraint — same
"constraint is the real guarantee, validation is UX" layering as CP13's
`add_pricebook_entry()`), `mark_reminder_sent()` (deliberately NOT
guarded against double-marking — unlike CP12's `mark_invoice_paid()`,
no invariant is broken by re-sending the same "sent" flag), and
`get_timeline(entity, user=None)` — merges `Task`/`Event`/`ActivityLog`
for one entity into one chronologically-sorted list; when `user` is
supplied, scopes each of the three querysets through
`scope_queryset_for_user()` first, reusing the exact same ownership rule
the viewsets already apply rather than inventing entity-level access
control from scratch.

### Endpoints

`/api/v1/activities/{tasks,events,activity-logs,reminders}/` — full CRUD
(no PUT) + CP7's `restore`/`hard-delete`, plus lifecycle actions
(`tasks/<id>/{complete,cancel,reassign}/`, `events/<id>/occurrences/`,
`reminders/<id>/mark-sent/`) and one standalone endpoint,
`GET /api/v1/activities/timeline/?content_type=<app_label.model>&object_id=<id>`
— CP14's "activity timeline retrieval" requirement.

### ViewSets

`TaskViewSet`/`EventViewSet`/`ActivityLogViewSet` reuse CP10's
`_CrmModelViewSet` (`apps.crm.views`) directly across the app boundary —
same "reuse over duplicate" choice CP12's `apps/sales/views.py` already
made for the identical base. `ActivityLogViewSet` sets
`owner_field = "actor"` (a real FK field — CP10's single-field-path
`scope_queryset_for_user()` needs no changes). `ReminderViewSet` cannot
reuse `scope_queryset_for_user()` unchanged: `Reminder` delegates
ownership to whichever of `task`/`event` it belongs to, a shape
`scope_queryset_for_user()`'s single-`owner_field`-path design cannot
express (it can't follow "whichever of two mutually exclusive FKs is
set"). Its `get_queryset()` applies the IDENTICAL three-tier rule via
`Q(task__owner=...) | Q(event__owner=...)` instead — documented inline
as an unavoidable adaptation, not a logic fork.

### Filtering

`Task`: `status`, `priority`, `owner`, `assigned_to`, `content_type`,
`object_id`, plus `due_before`/`due_after` range filters. `Event`:
`owner`, `recurrence_frequency`, `content_type`, `object_id`, plus
`starts_before`/`starts_after`. `ActivityLog`: `activity_type`, `actor`,
`content_type`, `object_id`. `Reminder`: `task`, `event`, `is_sent`.

### Searching

`Task`: `title`, `description`. `Event`: `title`, `description`,
`location`. `ActivityLog`: `description`. `Reminder`: `message`.

### Ordering

`Task`: `due_date`, `priority`, `created_at`, `status`. `Event`:
`start_at`, `created_at`. `ActivityLog`: `occurred_at`, `created_at`.
`Reminder`: `remind_at`.

### Pagination

CP10's project-wide `StandardPagination`, unchanged — no
activities-specific configuration needed.

### Permissions

**No new comparison logic.** `apps/activities/permissions.py`
re-exports CP6's `IsOwnerOrSuperAdmin` unchanged. `Task`/`Event` have a
real `owner` FK; `ActivityLog` exposes an `owner` PROPERTY delegating to
`actor`; `Reminder` exposes an `owner` PROPERTY delegating to whichever
`Task`/`Event` it belongs to — the same delegation pattern CP9's
`ContactPerson.owner`/`Address.owner` established for "no owner of its
own, but access follows the parent it belongs to". `resolve_owner()`
(CP6) discovers ownership via a plain `hasattr(obj, "owner")` check,
which is satisfied by a property exactly like a real field — zero
changes needed to CP6's own code for this checkpoint's two delegating
models to work.

### OpenAPI

`manage.py spectacular --file schema.yaml` — zero errors, zero warnings.
One fix was needed to get there: `RelatedObjectMixin.get_related_object()`
(a `SerializerMethodField`) had no return-type hint, which
drf-spectacular flagged as an "unable to resolve type hint" warning on
all three serializers that use it (`Task`/`Event`/`ActivityLog`) — fixed
with an explicit `@extend_schema_field(...)` describing the `{type, id,
label}` shape, the standard drf-spectacular idiom for a
`SerializerMethodField` whose return shape isn't inferable from a type
hint alone.

### Tests

**No database required — genuinely executed, genuinely passing:** 78/78.
Covers every field/constraint/Meta definition (including the
`RELATABLE_ENTITY_TYPES` content-type restriction), `__str__`/property
behavior on in-memory instances (including the `owner`-delegation chain:
`Reminder.owner` → `Task.owner`, `ActivityLog.owner` → `actor`), every
queryset helper's compiled filter, `generate_occurrences()`'s pure
date-math (daily/weekly/monthly-with-clamping/yearly stepping,
end-date truncation — no database involved, since it never persists
anything), serializer field declarations and the
`exactly_one_of_task_or_event` validation (a direct `validate()` call,
not full serializer validation), the `IsOwnerOrSuperAdmin` object-permission
truth table applied to all four models' owner-resolution shapes, the
admin registry, filter class declarations, URL routing for every
endpoint including the six custom actions and the standalone timeline
route, and OpenAPI schema generation.

**Requires database — blocked:** 56 tests covering real persistence and
cascade behavior; both check constraints actually rejecting bad rows;
full HTTP-level CRUD and ownership-scoping enforcement (including that
an Employee cannot see another Employee's `Task`/`Reminder`, and that
`ReminderViewSet`'s Q-based scoping behaves identically to the
single-field-path version used everywhere else); the `Task`/`Event`
lifecycle actions; the `occurrences`/`mark-sent`/timeline endpoints
against real rows; search/filter/ordering/pagination; and the full
serializer validation path for `Task`/`Reminder` (FK fields query the
database during validation). All error at the identical
`OperationalError` as every other DB-dependent test since CP2, zero
assertion failures.

One genuine, non-obvious issue was found and fixed while WRITING this
checkpoint's own tests (not a bug in the app code): a test asserting
`Task.objects.for_entity(some_object)` builds its filter "without hitting
the database" was itself wrong — `ContentType.objects.get_for_model()`
(called inside `for_entity()`) always queries (or consults Django's
per-process cache of) the `django_content_type` table; it is NOT a pure
Python-level metadata lookup the way `some_model._meta.app_label` is.
This is the same class of gotcha CP10/CP11 already recorded ("any
FK-referencing serializer field queries the DB during validation, not
just `unique=True` ones") — here applied to `ContentType` lookups
specifically. Fixed by moving that assertion to the `@pytest.mark.django_db`
section, where it belongs. No other test-authoring mistakes this
checkpoint.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 / CP8 / CP9 / CP10 / CP11 / CP12 / CP13 regression

**Blocked**, same pre-existing cause (not a new CP14 regression). Every
prior checkpoint's DB-backed tests still error at DB setup identically to
their own prior reports; every prior checkpoint's DB-free tests continue
to pass unchanged. CP10's/CP11's/CP12's/CP13's own endpoints explicitly
re-verified still resolving and unaffected by CP14's new
`apps.activities` app/routes/`django.contrib.contenttypes` usage. **None
of their statuses were upgraded to VERIFIED** by CP14's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP13, re-verified (`psql` not found, no
Windows service, no Docker, no WSL).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP13 (re-verified: no `psql`, no service,
no Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs
were found in CP1–CP13's carried-forward code during Phase 1
verification (`manage.py check`, `makemigrations --check --dry-run`,
`spectacular --file schema.yaml`, and a full `pytest -q` run all clean
before any CP14 code was written).

One test-authoring mistake was found and fixed during this checkpoint's
own test-writing — see "Tests" above (the `ContentType.objects.get_for_model()`
DB-access gotcha). No index-name-length issue this checkpoint (every name
pre-checked against PostgreSQL's limits while writing the model, same
proactive habit as CP13).

Two design decisions worth recording:

1. **`Reminder` is not generic to the five CRM entities** — only
   `Task`/`Event`/`ActivityLog` use `RelatedToEntityModel`. A reminder
   without a task or event to be a reminder FOR is meaningless, so
   `Reminder` uses two specific nullable FKs (`task`, `event`) with an
   exactly-one-of constraint instead of the contenttypes machinery —
   simpler, and DB-enforceable in a way a generic relation to "one of
   five other generically-related models" would not be.
2. **`ReminderViewSet.get_queryset()` cannot reuse
   `scope_queryset_for_user()` unchanged** — see "ViewSets" above. This
   is the one place CP14 could not achieve zero-new-logic reuse; the
   alternative (forcing `Reminder` to carry its own redundant `owner`
   FK just so the existing single-field-path helper would work) was
   judged worse: it would duplicate data that already lives on whichever
   `Task`/`Event` the reminder belongs to, and could drift out of sync
   with it. The three-tier RULE itself (Super Admin sees everything,
   Manager sees their team, Employee sees only their own) is still
   defined in exactly one place (`managed_user_ids()`); only its
   application to a two-mutually-exclusive-FK shape had to be
   re-expressed.

### Deferred

- Full RFC 5545 RRULE support (BYDAY/BYMONTH/exceptions/until-vs-count
  combinations) for `Event` recurrence — CP14 explicitly asked for
  "basic recurrence only"; `generate_occurrences()` covers DAILY/WEEKLY/
  MONTHLY/YEARLY stepping only.
  Materializing recurring `Event` occurrences as their own persisted rows
  (vs. computing them on demand) — not requested, and would add
  self-referential-FK/cascade-deletion complexity the "basic recurrence
  only" scope doesn't call for.
- A background job actually delivering reminders (email/push/SMS) when
  `remind_at` arrives — `mark_reminder_sent()` and `Reminder.due()` exist
  as the building blocks a future scheduler would call; no scheduler
  itself was requested or built this checkpoint.
- Entity-level (not just activity-row-level) access control for the
  timeline endpoint — e.g. an Employee who does not own a `Customer`
  directly can still request its `content_type`/`object_id` and see
  their OWN task/event/log rows attached to it (scoped correctly), but
  nothing currently checks whether they're allowed to know the customer
  exists at all. Out of scope for this checkpoint (would require
  cross-app entity-ownership coordination CP14 wasn't asked to build).

### Next

CP15 (blocked behind the same PostgreSQL issue affecting CP2–CP14's
DB-dependent verification)

---

## CP15 — Communications (Email Templates/Messages, Notifications, Communication Log)

**Status:** PARTIAL / BLOCKED (implementation complete. `apps/communications/`
totals 115 tests across 11 files — 70 genuinely pass with no database, 45
require a real database and are blocked. Project-wide: **637 passed, 541
errors** — up from CP14's 567/496, confirming zero regressions.)

### Files created

- `backend/apps/communications/{__init__.py, apps.py, models.py,
  services.py, serializers.py, permissions.py, admin.py, filters.py,
  views.py, urls.py}` — a genuinely new Django app: outbound email
  (templates + queued/sent messages), in-app notifications, and a unified
  cross-channel communication audit log.
- `backend/apps/communications/migrations/0001_initial.py` —
  hand-inspected; creates `EmailTemplate`, `EmailMessage`, `Notification`,
  `CommunicationLog` and every declared index.
- `backend/apps/communications/tests/{conftest, test_models, test_managers,
  test_services, test_serializers, test_permissions, test_admin,
  test_filters, test_api, test_urls, test_openapi, test_regression}.py`
  — 115 tests (70 pass with no database, 45 blocked).

### Files modified

- `backend/config/settings/base.py` — added `"apps.communications"` to
  `LOCAL_APPS`.
- `backend/config/urls.py` — mounted `apps.communications.urls` at
  `/api/v1/communications/`.

No other existing file was touched. **No frontend file was read, opened,
or modified.**

### Migration

`apps/communications/migrations/0001_initial.py` — creates all four
tables and 6 indexes. No constraints beyond the standard FK/unique ones
(`EmailTemplate.name` unique) — unlike CP13's `PriceBookEntry`/CP14's
`Reminder`, no model here needs an exactly-one-of `CheckConstraint`.
Every index name checked against PostgreSQL's identifier limits while
writing the model (proactive habit continued from CP13/CP14).
`makemigrations --check --dry-run` clean before and after. **Not
applied** — same PostgreSQL blocker as every prior checkpoint.

### Models

- **`EmailTemplate`** — `name` (unique), `subject`, `body` (both support
  `{{placeholder}}` substitution — see Services), `is_active` (same
  "two independent booleans" shape as CP9's `Customer`/CP13's catalog
  models). No owner — shared reference data, same reasoning as CP13's
  `Product`/`Service`/`PriceBook`.
- **`EmailMessage`** — `template` (nullable FK, informational only —
  `subject`/`body` are a rendered SNAPSHOT, not a live re-render),
  `owner`, `to_email`, `subject`, `body`, `status`
  (QUEUED/SENT/FAILED), `sent_at`, `error_message`. Reuses CP14's
  `RelatedToEntityModel` mixin (`apps.activities.models`) UNCHANGED —
  imported, not re-implemented — so an email can optionally attach to
  the same five CRM entities a `Task`/`Event`/`ActivityLog` can.
- **`Notification`** — `recipient` (required, NOT nullable — unlike
  every other owner-shaped field in this project, a notification for no
  one is meaningless), `notification_type`
  (INFO/WARNING/ASSIGNMENT/REMINDER/SYSTEM), `title`, `message`,
  `is_read`, `read_at`. Also reuses `RelatedToEntityModel`.
- **`CommunicationLog`** — `channel` (EMAIL/NOTIFICATION/OTHER),
  `actor` (nullable — null for system-triggered entries), `summary`,
  `occurred_at`. Also reuses `RelatedToEntityModel`. Written
  AUTOMATICALLY by `services.send_queued_email()`/`create_notification()`
  — there is no create endpoint (see ViewSets).

All four inherit `SoftDeleteTimeStampedModel` (CP7).

### Managers

`EmailTemplateQuerySet.active()` (same `is_active=True` override
pattern as CP9/CP13), `EmailMessageQuerySet` (`for_entity(entity)`,
`queued()`), `NotificationQuerySet` (`unread()`, `for_recipient(user)`),
`CommunicationLogQuerySet` (`for_entity(entity)`). All four models get
`objects` (unfiltered)/`active_objects` (not-deleted) per CP7's
convention.

### Services

`apps/communications/services.py` re-exports CP10's `managed_user_ids()`/
`scope_queryset_for_user()` from `apps.crm.services` UNCHANGED. New
functions: `render_template(template, context)` (simple
`{{placeholder}}` substitution via a regex — NOT a full template engine;
see the "Problems encountered"/learning-guide discussion for why),
`queue_email()` (creates a QUEUED `EmailMessage` from either a template+
context or an explicit subject+body — raises `ValueError` if neither
usable input shape is supplied), `send_queued_email()` (attempts
delivery via an injectable `send_func`, defaulting to a thin wrapper
around Django's `send_mail()`; catches ANY exception and marks the
message FAILED with `error_message` set rather than raising — a failed
send is a recorded fact, not a crash; rejects an already-SENT message
with the same "already closed" `ValueError` guard shape as CP11's
`mark_won()`/CP14's `complete_task()`; automatically writes a
`CommunicationLog` entry on every attempt, success or failure),
`create_notification()` (also automatically writes a `CommunicationLog`
entry), `mark_notification_read()`/`mark_notification_unread()` (same
idempotent-tolerant shape as CP14's `mark_reminder_sent()`), and
`log_communication()` (the single function that actually creates
`CommunicationLog` rows — called by the two functions above, not
exposed as a client-facing create endpoint).

### Endpoints

`/api/v1/communications/{email-templates,email-messages,notifications}/`
— full CRUD (no PUT) + CP7's `restore`/`hard-delete`, plus
`email-messages/<id>/send/`, `notifications/<id>/{mark-read,mark-unread}/`.
`/api/v1/communications/communication-logs/` — **read-only** (list/
retrieve only; every write verb, including `restore`/`hard-delete`,
returns 405 — see ViewSets).

### ViewSets

`EmailTemplateViewSet` uses a new, small `_ReferenceDataModelViewSet`
(no ownership scoping — `EmailTemplate` has no owner) rather than
importing CP13's `_CatalogModelViewSet`: that class hardcodes
`CatalogWritePermission`, a catalog-specific class, so importing it here
would couple this app to catalog's permission choice by coincidence, not
by an actual shared dependency — the same "reuse infrastructure does not
mean reuse every base class regardless of fit" judgment CP13's own
docstring describes, applied a second time. `EmailMessageViewSet`,
`NotificationViewSet`, `CommunicationLogViewSet` all reuse CP10's
`_CrmModelViewSet` (`apps.crm.views`) directly across the app boundary —
the same cross-app reuse CP12/CP14 already established.
`EmailMessageViewSet.create()` is overridden entirely (not just
`perform_create()`): queueing an email accepts a `template`(+`context`)
OR `subject`+`body` input union that doesn't map onto `EmailMessage`'s
flat field list the way ordinary creation does.
`CommunicationLogViewSet` sets `http_method_names = ["get", "head",
"options"]` — DRF returns 405 for every write verb, including the
inherited `restore`/`hard-delete` actions, with zero new permission
logic; confirmed both via a 405 API test and by the generated OpenAPI
schema genuinely omitting those two paths for this resource only.

### Filtering

`EmailTemplate`: `is_active`. `EmailMessage`: `status`, `owner`,
`template`, `content_type`, `object_id`. `Notification`:
`notification_type`, `is_read`, `recipient`, `content_type`, `object_id`.
`CommunicationLog`: `channel`, `actor`, `content_type`, `object_id`.

### Searching

`EmailTemplate`: `name`, `subject`. `EmailMessage`: `subject`,
`to_email`. `Notification`: `title`, `message`. `CommunicationLog`:
`summary`.

### Ordering

`EmailTemplate`: `name`, `created_at`, `updated_at`. `EmailMessage`:
`created_at`, `sent_at`, `status`. `Notification`: `created_at`,
`is_read`. `CommunicationLog`: `occurred_at`.

### Pagination

CP10's project-wide `StandardPagination`, unchanged.

### Permissions

**No new comparison logic.** `EmailTemplateWritePermission =
ReadOnlyOrSuperAdmin | IsManagerOrSuperAdmin` — the EXACT SAME
composition CP13 built for its own catalog models, reused here for the
identical "shared reference data, any authenticated user reads, only a
Manager-or-above writes" shape. `IsOwnerOrSuperAdmin` (CP6) is re-exported
unchanged for `EmailMessage`/`Notification`/`CommunicationLog` — `owner`
is a real field on `EmailMessage`, and a delegating PROPERTY on
`Notification` (→ `recipient`) and `CommunicationLog` (→ `actor`), the
same pattern CP9's `ContactPerson.owner`/CP14's `ActivityLog.owner`
established.

### OpenAPI

`manage.py spectacular --file schema.yaml` — zero errors, zero warnings,
achieved on the FIRST schema-generation run this checkpoint (unlike
CP14, which needed one `@extend_schema_field` fix): reusing CP14's
`RelatedObjectMixin` UNCHANGED meant its already-fixed type-hint
annotation carried over automatically to every serializer that mixes it
in here, with no new warning to fix.

### Tests

**No database required — genuinely executed, genuinely passing:** 70/70.
Covers every field/constraint/Meta definition, `__str__`/property
behavior on in-memory instances (including the `owner`-delegation chain
for `Notification`/`CommunicationLog`), every queryset helper's compiled
filter, `render_template()`'s pure text substitution (known placeholder,
unknown placeholder left literal, no-context case — genuinely DB-free,
since it never touches a model instance's database-backed fields), the
`EmailMessageQueueSerializer`'s exactly-one-input-shape validation (a
direct `validate()` call), the `EmailTemplateWritePermission` truth
table, the admin registry, filter class declarations, URL routing for
every endpoint, and OpenAPI schema generation (including the
`CommunicationLog` read-only-endpoint-exclusion check).

**Requires database — blocked:** 45 tests covering real persistence and
cascade behavior (a deleted `EmailTemplate` sets `EmailMessage.template`
to NULL); full HTTP-level CRUD and ownership-scoping enforcement
(including that an Employee cannot see another Employee's
`EmailMessage`, and that `CommunicationLog` returns 405 on every write
attempt); the `send`/`mark-read`/`mark-unread` actions against real rows,
including confirming `send_queued_email()` actually writes a
`CommunicationLog` entry and that `create_notification()` does too;
search/filter/ordering/pagination; and the full serializer validation
path for `EmailMessageQueueSerializer`/`NotificationSerializer` (FK
fields query the database during validation). All error at the identical
`OperationalError` as every other DB-dependent test since CP2, zero
assertion failures.

No test-authoring mistakes this checkpoint — the `ContentType.objects
.get_for_model()` DB-access gotcha CP14 discovered was applied
proactively here: `EmailMessageQuerySet.for_entity()`/
`CommunicationLogQuerySet.for_entity()` both call `get_for_model()`
internally and their tests were written directly into the
`@pytest.mark.django_db` section from the start, never assumed DB-free.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 / CP8 / CP9 / CP10 / CP11 / CP12 / CP13 / CP14 regression

**Blocked**, same pre-existing cause (not a new CP15 regression). Every
prior checkpoint's DB-backed tests still error at DB setup identically to
their own prior reports; every prior checkpoint's DB-free tests continue
to pass unchanged. CP10's/CP12's/CP13's/CP14's own endpoints explicitly
re-verified still resolving and unaffected by CP15's new
`apps.communications` app/routes. `apps.activities`'s `RelatedToEntityModel`/
`RelatedObjectMixin` — the two pieces of CP14 infrastructure this
checkpoint imports directly — explicitly re-verified unchanged and still
importable. **None of their statuses were upgraded to VERIFIED** by
CP15's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP14, re-verified (`psql` not found, no
Windows service, no Docker, no WSL).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP14 (re-verified: no `psql`, no service,
no Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs
were found in CP1–CP14's carried-forward code during Phase 1 verification
(`manage.py check`, `makemigrations --check --dry-run`, a full `pytest
-q` run, and `spectacular --file schema.yaml` all clean before any CP15
code was written). No index-name-length issue, no test-authoring
mistakes this checkpoint — both lessons from CP11-CP14 applied
proactively.

Two design decisions worth recording:

1. **`EmailTemplate` rendering uses a simple `{{placeholder}}` regex
   substitution, not a full template engine.** Django's own template
   language or Jinja2 were both deliberately rejected — a CRM email
   template only ever needs flat field substitution (customer name, deal
   value, ...), and adopting a real template engine would mean deciding
   how to sandbox arbitrary CRM data against autoescaping/security rules
   that a bare `{{name}}`-style substitution never raises in the first
   place. An unresolved placeholder is left LITERAL rather than raising —
   a caller previewing against a partial context gets a usable partial
   result, not a hard failure.
2. **`CommunicationLog` has no create endpoint, by design, not by
   oversight.** It is the SYSTEM's own record of what it actually did
   (an email sent/failed, a notification created), written automatically
   by `send_queued_email()`/`create_notification()`. Letting a client
   `POST` directly to it would let anyone fabricate audit-trail entries
   for communications that never happened — the read-only restriction
   (`http_method_names`) is a deliberate integrity boundary, the same
   category of decision as CP7's "no permanent delete unless explicitly
   requested," just applied to writes instead of deletes.

### Deferred

- Actual SMTP configuration/credentials (`EMAIL_BACKEND`,
  `DEFAULT_FROM_EMAIL`) — not requested this checkpoint and untestable in
  this environment regardless (no outbound network access verified, same
  category of environment limitation as the PostgreSQL blocker); `send_queued_email()`'s
  injectable `send_func` is the seam a future checkpoint (or deployment
  configuration) would wire a real backend through.
- SMS/push notification channels — `CommunicationLog.Channel` has room
  for them (`OTHER` today), but only EMAIL/NOTIFICATION are actually
  implemented; not requested.
- A background worker that automatically calls `send_queued_email()` for
  every `EmailMessage.objects.queued()` row — `queue_email()`/
  `send_queued_email()` are the building blocks; no scheduler itself was
  requested or built.
- Broadening `RelatedToEntityModel`'s allowed content types beyond the
  five CRM entities (e.g. letting a `Notification` reference a CP14
  `Task`/`Event` directly, for "your task is due" notifications) — the
  mixin was reused UNCHANGED rather than modified, since extending its
  `limit_choices_to` would also affect `Task`/`Event`/`ActivityLog`'s own
  behavior in `apps.activities`, a cross-app side effect not requested
  this checkpoint.

### Next

CP16 (blocked behind the same PostgreSQL issue affecting CP2–CP15's
DB-dependent verification)

---

## CP16 — Reports & Dashboards (Saved Reports, Report Executions, Dashboards, Widgets)

**Status:** PARTIAL / BLOCKED (implementation complete. `apps/reports/`
totals 111 tests across 11 files — 65 genuinely pass with no database, 46
require a real database and are blocked. Project-wide: **702 passed, 587
errors** — up from CP15's 637/541, confirming zero regressions.)

### Files created

- `backend/apps/reports/{__init__.py, apps.py, models.py, services.py,
  serializers.py, permissions.py, admin.py, filters.py, views.py,
  urls.py}` — a genuinely new Django app fulfilling the original client
  requirement "Productivity reports": saved report definitions, their
  computed executions, and dashboards of widgets visualizing them.
- `backend/apps/reports/migrations/0001_initial.py` — hand-inspected;
  creates `SavedReport`, `ReportExecution`, `Dashboard`, `DashboardWidget`
  and every declared index/constraint.
- `backend/apps/reports/tests/{conftest, test_models, test_managers,
  test_services, test_serializers, test_permissions, test_admin,
  test_filters, test_api, test_urls, test_openapi, test_regression}.py`
  — 111 tests (65 pass with no database, 46 blocked).

### Files modified

- `backend/config/settings/base.py` — added `"apps.reports"` to
  `LOCAL_APPS`.
- `backend/config/urls.py` — mounted `apps.reports.urls` at
  `/api/v1/reports/`.

No other existing file was touched. **No frontend file was read, opened,
or modified.**

### Migration

`apps/reports/migrations/0001_initial.py` — creates all four tables, 4
indexes, and 1 constraint (`Dashboard`'s partial `UniqueConstraint` — "at
most one `is_default=True` dashboard per owner", the same technique CP9's
`ContactPerson`/CP13's `PriceBookEntry`/CP14's `Reminder` all established
for their own exactly-one/at-most-one rules). One index name initially
exceeded PostgreSQL's 30-character limit (`reports_execution_report_status_idx`,
37 chars) — caught by `manage.py check` itself (Django's own `models.E034`
system check, not a runtime surprise) before ever reaching
`makemigrations`, and shortened to `reports_execution_status_idx` (28
chars). `makemigrations --check --dry-run` clean before and after. **Not
applied** — same PostgreSQL blocker as every prior checkpoint.

### Models

- **`SavedReport`** — `name`, `description`, `report_type`
  (PRODUCTIVITY/LEAD_CONVERSION/SALES_PIPELINE/CUSTOMER_ACTIVITY/CUSTOM),
  `owner`, `filters` (`JSONField`, interpreted by the matching compute
  function — see Services), `is_active`. A DEFINITION of what to compute,
  not the computed result.
- **`ReportExecution`** — `report` (CASCADE), `executed_by`, `status`
  (PENDING/RUNNING/COMPLETED/FAILED), `started_at`/`completed_at`,
  `result_data` (`JSONField`), `row_count`, `error_message`. Written
  ENTIRELY by `services.execute_report()` — no create endpoint (see
  ViewSets), the same integrity-boundary pattern CP15's
  `CommunicationLog` established.
- **`Dashboard`** — `name`, `owner`, `is_default` (at most one per owner,
  DB-enforced).
- **`DashboardWidget`** — `dashboard` (CASCADE), `report` (CASCADE,
  required — a widget with nothing to visualize is meaningless),
  `widget_type` (CHART/TABLE/METRIC), `title`, `position`,
  `configuration` (`JSONField`, opaque to the backend, interpreted by the
  frontend).

All four inherit `SoftDeleteTimeStampedModel` (CP7). `SavedReport`/
`Dashboard` have a real `owner` FK; `ReportExecution`/`DashboardWidget`
each delegate ownership via a PROPERTY to the record they belong to
(`report.owner`/`dashboard.owner`) — the same pattern CP9's
`ContactPerson.owner`/`Address.owner` established.

### Managers

`SavedReportQuerySet` (`active()`, `by_owner(user)`),
`ReportExecutionQuerySet` (`for_report(report)`,
`latest_for_report(report)`), `DashboardQuerySet` (`by_owner(user)`),
`DashboardWidgetQuerySet` (`for_dashboard(dashboard)`). All four models
get `objects` (unfiltered)/`active_objects` (not-deleted) per CP7's
convention.

### Services

`apps/reports/services.py` re-exports CP10's `managed_user_ids()`/
`scope_queryset_for_user()` from `apps.crm.services` UNCHANGED. This
checkpoint's centerpiece is `execute_report()` — a small dispatch table
(`_REPORT_COMPUTERS`) mapping each `SavedReport.ReportType` to its own
compute function, each querying an EXISTING domain model rather than
this app maintaining a duplicate copy of lead/opportunity/activity data:

- `PRODUCTIVITY` — per-user counts of completed `Task`s (CP14) and
  logged `ActivityLog` entries (CP14). Fulfills the original "Employee
  activity tracking"/"Productivity reports" client requirements.
- `LEAD_CONVERSION` — `Lead` (CP9) volume and conversion rate, using the
  SAME `converted_customer` field CP9's `convert_lead()` sets.
- `SALES_PIPELINE` — open `Opportunity` (CP11) count/value grouped by
  `stage`.
- `CUSTOMER_ACTIVITY` — `ActivityLog` (CP14) count per `Customer`, using
  the SAME `content_type`/`object_id` generic relation CP14 built.
- `CUSTOM` — an explicit extension point, not a fallback for an
  unrecognized type; always succeeds with an empty result.

`execute_report()` itself creates the `ReportExecution`, runs the
matching compute function, and NEVER lets an exception propagate — a
failed computation is caught and recorded as `status=FAILED` +
`error_message`, the same "a failure is a recorded fact, not a crash"
contract CP15's `send_queued_email()` established. Also:
`create_saved_report()` (thin wrapper), `create_dashboard()`/
`set_default_dashboard()` (demote-then-promote, same shape as CP9's
`add_contact(is_primary=True)`), `add_widget()` (auto-assigns `position`
when omitted, same auto-ordering convenience as CP12's
`add_quote_item()`), `update_widget_configuration()` (thin wrapper).

### Endpoints

`/api/v1/reports/{saved-reports,dashboards,dashboard-widgets}/` — full
CRUD (no PUT) + CP7's `restore`/`hard-delete`, plus
`saved-reports/<id>/execute/`, `dashboards/<id>/set-default/`.
`/api/v1/reports/report-executions/` — **read-only** (list/retrieve
only; every write verb, including `restore`/`hard-delete`, returns 405).

### ViewSets

Every viewset reuses CP10's `_CrmModelViewSet` (`apps.crm.views`)
directly — all four models have a real or delegating `owner`, the same
cross-app reuse CP12/CP14/CP15 already established; no new small
reference-data base was needed this checkpoint (unlike CP13's
`_CatalogModelViewSet`/CP15's `_ReferenceDataModelViewSet` — every model
here HAS an owner concept). `SavedReportViewSet.execute` and
`DashboardViewSet.set_default` are both thin wrappers around their
matching service function. `ReportExecutionViewSet` sets
`http_method_names = ["get", "head", "options"]` — the identical
integrity-boundary technique CP15's `CommunicationLogViewSet` used,
confirmed both via a 405 API test and the OpenAPI schema genuinely
omitting `restore`/`hard-delete` for that resource.
`DashboardViewSet`/`DashboardSerializer` make `is_default` READ-ONLY on
the serializer — reachable only via the `set-default` action — so the
demote-then-promote invariant can never be bypassed by a plain
create/update payload racing the partial unique constraint.

### Filtering

`SavedReport`: `report_type`, `owner`, `is_active`. `ReportExecution`:
`report`, `status`, `executed_by`. `Dashboard`: `owner`, `is_default`.
`DashboardWidget`: `dashboard`, `report`, `widget_type`.

### Searching

`SavedReport`: `name`, `description`. `ReportExecution`: `report__name`.
`Dashboard`: `name`. `DashboardWidget`: `title`.

### Ordering

`SavedReport`: `name`, `created_at`, `updated_at`, `report_type`.
`ReportExecution`: `created_at`, `completed_at`, `status`. `Dashboard`:
`name`, `created_at`, `updated_at`. `DashboardWidget`: `position`,
`created_at`.

### Pagination

CP10's project-wide `StandardPagination`, unchanged.

### Permissions

**No new comparison logic.** `IsOwnerOrSuperAdmin` (CP6) is re-exported
unchanged — every model here has an owner-shaped attribute (real field or
delegating property), the same pattern this project has applied since
CP9.

### OpenAPI

`manage.py spectacular --file schema.yaml` — zero errors, zero warnings
on the first attempt. No `ENUM_NAME_OVERRIDES` addition was needed
despite `ReportExecution.Status`/`Task.Status`/`EmailMessage.Status` all
being distinctly-named choices classes on a field also called `status` —
confirmed empirically: drf-spectacular names each generated component
after its OWNING SERIALIZER (`ReportExecutionStatusEnum`,
`TaskStatusEnum`, `EmailMessageStatusEnum`), not just the bare field
name, so this collision class (which DID require an override for CP10's
`Customer`/`Lead` and CP12's `Quote`/`Invoice`) did not recur here — see
the learning guide for the fuller explanation of when the override is
and isn't needed.

### Tests

**No database required — genuinely executed, genuinely passing:** 65/65.
Covers every field/constraint/Meta definition, `__str__`/property
behavior on in-memory instances (including the `owner`-delegation chain
for `ReportExecution`/`DashboardWidget`), every queryset helper's
compiled filter, the report-execution dispatch table (confirms every
`ReportType` has a registered compute function; `_compute_custom()`
tested directly as a pure function, genuinely DB-free), serializer field
declarations (including `Dashboard.is_default`'s read-only status), the
admin registry, filter class declarations, URL routing for every
endpoint, and OpenAPI schema generation (including the
`ReportExecution` read-only-endpoint-exclusion check).

**Requires database — blocked:** 46 tests covering real persistence and
cascade behavior; the `Dashboard` default-uniqueness constraint actually
rejecting a second default per owner (and allowing one per DIFFERENT
owner); full HTTP-level CRUD and ownership-scoping enforcement; EVERY
report type's compute function against real `Lead`/`Opportunity`/`Task`/
`ActivityLog` rows (the actual point of `execute_report()` — these are
the tests that prove the cross-app queries are correct, not just that
they don't raise); the `execute`/`set-default` actions against real rows;
search/filter/ordering/pagination; and full serializer validation (FK
fields query the database). All error at the identical `OperationalError`
as every other DB-dependent test since CP2, zero assertion failures.

No test-authoring mistakes this checkpoint — the `ContentType.objects
.get_for_model()` gotcha (discovered CP14, applied proactively CP15) did
not recur here since `_compute_customer_activity()`'s own
`ContentType.objects.get_for_model()` call is only exercised inside
`execute_report()`'s DB-required test path, never assumed DB-free.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 / CP8 / CP9 / CP10 / CP11 / CP12 / CP13 / CP14 / CP15 regression

**Blocked**, same pre-existing cause (not a new CP16 regression). Every
prior checkpoint's DB-backed tests still error at DB setup identically to
their own prior reports; every prior checkpoint's DB-free tests continue
to pass unchanged. CP9's `Lead`, CP11's `Opportunity`, and CP14's
`Task`/`ActivityLog` — the three models this checkpoint's report
computations query directly — explicitly re-verified unchanged and
exposing the exact fields `services.py` relies on
(`test_cp9_cp11_cp14_models_this_checkpoint_computes_from_are_unchanged`).
**None of their statuses were upgraded to VERIFIED** by CP16's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP15, re-verified (`psql` not found, no
Windows service, no Docker, no WSL).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP15 (re-verified: no `psql`, no service,
no Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs
were found in CP1–CP15's carried-forward code during Phase 1 verification
(`manage.py check`, `makemigrations --check --dry-run`, a full `pytest
-q` run, and `spectacular --file schema.yaml` all clean before any CP16
code was written).

One index-name-length issue occurred and was fixed — see "Migration"
above; caught by `manage.py check`'s own system check (`models.E034`)
immediately after writing the model, before ever running
`makemigrations`, rather than being discovered later the way CP11/CP12
discovered theirs. No test-authoring mistakes.

One design decision worth recording: **`ReportExecution.result_data` is
a single, report-type-agnostic `{"rows": [...], "summary": {...}}`
envelope, the same shape regardless of which `report_type` produced it.**
Each compute function returns different CONTENTS inside that envelope
(productivity's rows have `user_id`/`tasks_completed`/
`activities_logged`; sales-pipeline's rows have `stage`/`count`/
`total_value`), but the outer shape is uniform — a caller/serializer/
future frontend widget can always read `result_data["summary"]` and
`result_data["rows"]` without first branching on `report_type` to know
which keys exist at the top level, even though the ROW contents
themselves remain report-type-specific. This was a deliberate design
choice made before writing the first compute function, not an accident
of how the functions happened to turn out similar.

### Deferred

- Async/background report execution (e.g. via Celery) — `execute_report()`
  runs synchronously today; CP16's own client-requirements roadmap lists
  "Transcription / Async Processing" as a SEPARATE future checkpoint, and
  nothing in this checkpoint's own scope asked for async execution.
- Scheduled/recurring report execution (e.g. "email me this report every
  Monday") — would naturally combine CP15's `queue_email()` with this
  checkpoint's `execute_report()`, but wasn't requested and would need a
  scheduler this project doesn't have yet (see CP15's own "Deferred"
  entry for the identical scheduler gap).
- Additional `ReportType`s (e.g. invoice aging, quote-to-invoice
  conversion rate) — the dispatch table (`_REPORT_COMPUTERS`) is the
  seam; not built because not requested.
- Widget-level access control finer than "can you see the dashboard" —
  e.g. a widget visualizing a report the viewer doesn't own is currently
  reachable only if the viewer can already reach the WIDGET (which
  requires owning/managing the dashboard); no additional per-widget
  report-ownership check was added, since `DashboardWidgetViewSet`
  already scopes by `dashboard__owner`, not by the underlying report's
  owner — not flagged as a gap requiring a fix, just an explicit note of
  the actual access boundary as built.

### Next

CP17 (blocked behind the same PostgreSQL issue affecting CP2–CP16's
DB-dependent verification)

---

## CP17 — Workflow Automation (Workflows, Triggers, Actions, Executions)

**Status:** PARTIAL / BLOCKED (implementation complete. `apps/workflows/`
totals 116 tests across 11 files — 72 genuinely pass with no database, 44
require a real database and are blocked. Project-wide: **774 passed, 631
errors** — up from CP16's 702/587, confirming zero regressions.)

### Files created

- `backend/apps/workflows/{__init__.py, apps.py, models.py, services.py,
  serializers.py, permissions.py, admin.py, filters.py, views.py,
  urls.py}` — a genuinely new Django app: automation rules (trigger +
  ordered actions) that, when run, dispatch INTO CP14's `apps.activities`
  and CP15's `apps.communications` service layers directly — this
  checkpoint is the project's first that is primarily an INTEGRATION
  layer over four prior checkpoints' work, not a new domain of its own
  data.
- `backend/apps/workflows/migrations/0001_initial.py` — hand-inspected;
  creates `Workflow`, `WorkflowTrigger`, `WorkflowAction`,
  `WorkflowExecution` and every declared index.
- `backend/apps/workflows/tests/{conftest, test_models, test_managers,
  test_services, test_serializers, test_permissions, test_admin,
  test_filters, test_api, test_urls, test_openapi, test_regression}.py`
  — 116 tests (72 pass with no database, 44 blocked).

### Files modified

- `backend/config/settings/base.py` — added `"apps.workflows"` to
  `LOCAL_APPS`; added ONE new `ENUM_NAME_OVERRIDES` entry (see OpenAPI,
  below).
- `backend/config/urls.py` — mounted `apps.workflows.urls` at
  `/api/v1/workflows/`.

No other existing file was touched. **No frontend file was read, opened,
or modified.**

### Migration

`apps/workflows/migrations/0001_initial.py` — creates all four tables
and 5 indexes. No constraints beyond standard FKs — unlike CP13's
`PriceBookEntry`/CP14's `Reminder`/CP16's `Dashboard`, no model here needs
an exactly-one-of or at-most-one-default constraint. Every index name
checked against PostgreSQL's 30-character limit while writing the model
— no violation this time (unlike CP16, which hit and immediately fixed
one via `manage.py check`). `makemigrations --check --dry-run` clean
before and after. **Not applied** — same PostgreSQL blocker as every
prior checkpoint.

### Models

- **`Workflow`** — `name`, `description`, `owner`, `is_active`. The only
  model here with a real `owner` FK.
- **`WorkflowTrigger`** — `workflow` (CASCADE), `trigger_type`
  (ON_CREATE/ON_UPDATE/ON_DELETE/MANUAL), `content_type` (nullable —
  which CRM entity TYPE this trigger watches, e.g. "any Lead"; reuses the
  SAME `RELATABLE_ENTITY_TYPES` constant CP14's `RelatedToEntityModel`
  limits its own `content_type` field to, WITHOUT pulling in that
  mixin's `object_id`/`GenericForeignKey` — a trigger watches a TYPE, not
  one row, a genuinely different shape from every other generic-relation
  use in this project so far), `conditions` (`JSONField`, a simple
  `{"field": ..., "equals": ...}` check).
- **`WorkflowAction`** — `workflow` (CASCADE), `action_type`
  (SEND_EMAIL/CREATE_TASK/CREATE_NOTIFICATION/LOG_ACTIVITY),
  `configuration` (`JSONField`, action-type-specific), `position` (run
  order).
- **`WorkflowExecution`** — `workflow` (CASCADE), `trigger` (nullable
  SET_NULL — null for a manually-invoked run with no matched trigger),
  `status` (PENDING/RUNNING/COMPLETED/FAILED), `started_at`/
  `completed_at`, `result_data` (`JSONField`, per-action outcomes),
  `error_message`. Reuses CP14's `RelatedToEntityModel` UNCHANGED — a run
  is always about one specific entity instance, the same shape CP15's
  `EmailMessage` and CP16's `ReportExecution`-adjacent models already use
  the generic relation for. Written entirely by `services.run_workflow()`
  — no create endpoint (see ViewSets).

All four inherit `SoftDeleteTimeStampedModel` (CP7).
`WorkflowTrigger`/`WorkflowAction`/`WorkflowExecution` each delegate
`owner` via a PROPERTY to the `Workflow` they belong to, the same
pattern CP9's `ContactPerson.owner` established.

### Managers

`WorkflowQuerySet` (`active()`, `by_owner(user)`),
`WorkflowTriggerQuerySet` (`for_workflow(workflow)`,
`for_entity_type(model)`), `WorkflowActionQuerySet`
(`for_workflow(workflow)`, ordered by `position`),
`WorkflowExecutionQuerySet` (`for_workflow(workflow)`). All four models
get `objects` (unfiltered)/`active_objects` (not-deleted) per CP7's
convention.

### Services

`apps/workflows/services.py` re-exports CP10's `managed_user_ids()`/
`scope_queryset_for_user()` from `apps.crm.services` UNCHANGED. This
checkpoint's centerpiece is the execution engine, in three layers:

1. **Trigger evaluation** — `evaluate_conditions(entity, conditions)` (a
   deliberately basic single field-equality check, the same "basic X
   only" scope discipline as CP14's `generate_occurrences()`/CP15's
   `render_template()`), `trigger_matches(trigger, entity, event_type=...)`
   (checks trigger type, watched entity type, then conditions, in that
   order — short-circuiting on the cheapest checks first).
2. **Action dispatch** — a small dispatch table (`_ACTION_DISPATCHERS`),
   the SAME "which code runs is a runtime decision driven by stored
   data" shape CP16's `_REPORT_COMPUTERS` established, mapping each
   `ActionType` to a function that routes into an EXISTING service:
   `SEND_EMAIL` calls CP15's `queue_email()`; `CREATE_TASK` calls CP14's
   `create_task()`; `CREATE_NOTIFICATION` calls CP15's
   `create_notification()`; `LOG_ACTIVITY` calls CP14's `log_activity()`.
   None of the four re-implements any logic those functions already
   have — this app only decides WHICH to call and WITH what
   configuration.
3. **Orchestration** — `run_workflow(workflow, entity, trigger=None)`
   creates a `WorkflowExecution`, runs every ACTIVE action in `position`
   order, and STOPS at the first failure (a workflow is a sequence, not
   an independent batch) — COMPLETED with every action's result folded
   into `result_data["actions"]`, or FAILED with `error_message` set on
   whichever action raised; never lets the exception propagate, the same
   "a failure is a recorded fact, not a crash" contract CP15's
   `send_queued_email()`/CP16's `execute_report()` both established.
   `evaluate_and_run(entity, event_type=...)` finds every matching active
   trigger across every active workflow and runs each matched workflow
   once — the function a FUTURE signal receiver would call (see
   "Problems encountered" for why none is wired up this checkpoint).

Also: `create_workflow()`, `add_trigger()` (thin wrappers), `add_action()`
(auto-assigns `position` when omitted, same convenience as CP12's
`add_quote_item()`/CP16's `add_widget()`).

### Endpoints

`/api/v1/workflows/{workflows,triggers,actions}/` — full CRUD (no PUT) +
CP7's `restore`/`hard-delete`, plus `workflows/<id>/execute/`.
`/api/v1/workflows/executions/` — **read-only** (list/retrieve only;
every write verb, including `restore`/`hard-delete`, returns 405).

### ViewSets

Every viewset reuses CP10's `_CrmModelViewSet` (`apps.crm.views`)
directly — the same cross-app reuse CP12/CP14/CP15/CP16 already
established; no new base class was needed (every model here has real or
delegating ownership, the same "when `_CrmModelViewSet` is enough"
judgment CP16 already made for its own four models).
`WorkflowViewSet.execute` is a thin action wrapper around
`services.run_workflow()`, accepting `{"content_type", "object_id"}` to
identify the target entity (`WorkflowExecuteSerializer`, a plain
`Serializer` — not a `ModelSerializer` — since "which entity to run
against" isn't a field on `Workflow` itself). `WorkflowActionViewSet.
perform_create()` routes through `services.add_action()` for the
auto-position behavior, the same pattern CP12's `QuoteItemViewSet`/
CP16's `DashboardWidgetViewSet` established.
`WorkflowExecutionViewSet` sets `http_method_names = ["get", "head",
"options"]` — the identical integrity-boundary technique CP15's
`CommunicationLogViewSet`/CP16's `ReportExecutionViewSet` used, confirmed
both via a 405 API test and the OpenAPI schema genuinely omitting
`restore`/`hard-delete` for that resource.

### Filtering

`Workflow`: `owner`, `is_active`. `WorkflowTrigger`: `workflow`,
`trigger_type`, `content_type`. `WorkflowAction`: `workflow`,
`action_type`. `WorkflowExecution`: `workflow`, `trigger`, `status`.

### Searching

`Workflow`: `name`, `description`. `WorkflowExecution`: `workflow__name`.

### Ordering

`Workflow`: `name`, `created_at`, `updated_at`. `WorkflowAction`:
`position`, `created_at`. `WorkflowExecution`: `created_at`,
`completed_at`, `status`.

### Pagination

CP10's project-wide `StandardPagination`, unchanged.

### Permissions

**No new comparison logic.** `IsOwnerOrSuperAdmin` (CP6) is re-exported
unchanged — every model here has an owner-shaped attribute (real field or
delegating property).

### OpenAPI

`manage.py spectacular --file schema.yaml` — zero errors, zero warnings,
but NOT on the first attempt this time (unlike CP16). Generation first
produced one warning: `WorkflowExecution.Status` and CP16's
`ReportExecution.Status` collide — not merely on FIELD NAME (the
CP10/CP12 pattern, both already override) but on having IDENTICAL CHOICE
VALUES too (`PENDING`/`RUNNING`/`COMPLETED`/`FAILED`), which is a
DIFFERENT collision shape than every prior `ENUM_NAME_OVERRIDES` entry in
this project. A single new entry — naming the shared component after
`ReportExecution.Status` — resolves it for BOTH models at once;
confirmed in the generated schema that `WorkflowExecution.status` now
correctly documents as `$ref: ReportExecutionStatusEnum`, not a
mismatched or duplicated name. See the learning guide for the fuller
mechanics of why this differs from every previous override this project
has needed.

### Tests

**No database required — genuinely executed, genuinely passing:** 72/72.
Covers every field/constraint/Meta definition (including confirming
`WorkflowTrigger` deliberately has NO `object_id` field, unlike every
other model reusing CP14's generic-relation machinery), `__str__`/
property behavior on in-memory instances (the `owner`-delegation chain
for all three non-`Workflow` models), every queryset helper's compiled
filter, `evaluate_conditions()`'s pure field-equality logic (empty/
missing conditions, matching, non-matching, missing-attribute cases —
genuinely DB-free, since it only calls `getattr()` on a plain object),
confirms every `ActionType` has a registered dispatcher, serializer field
declarations, the admin registry, filter class declarations, URL routing
for every endpoint including the `execute` action, and OpenAPI schema
generation (including a dedicated assertion that `WorkflowExecution
.status` actually resolves to the shared `ReportExecutionStatusEnum`
component, not just that generation doesn't warn).

**Requires database — blocked:** 44 tests covering real persistence and
cascade behavior; full HTTP-level CRUD and ownership-scoping enforcement;
EVERY action type's dispatcher against real rows (confirms `SEND_EMAIL`
actually creates an `EmailMessage`, `CREATE_TASK` an actual `Task`
correctly attached via `related_object`, etc. — not just that dispatch
doesn't raise); `run_workflow()`'s ordering guarantee (two LOG_ACTIVITY
actions at explicit positions produce `ActivityLog` rows in the correct
order) and its stop-on-first-failure guarantee (a failing
`CREATE_NOTIFICATION` action correctly prevents a LATER `LOG_ACTIVITY`
action from running at all); `evaluate_and_run()` against real triggers/
workflows (matching, inactive-workflow-skipped, no-match cases); the
`execute` action against real rows; search/filter/ordering/pagination;
and full serializer validation. All error at the identical
`OperationalError` as every other DB-dependent test since CP2, zero
assertion failures.

No test-authoring mistakes this checkpoint — the `ContentType.objects
.get_for_model()` gotcha (discovered CP14, applied proactively CP15/CP16)
was applied proactively again: `WorkflowTrigger.objects.for_entity_type()`'s
own test lives in the DB-required section from the start.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 / CP8 / CP9 / CP10 / CP11 / CP12 / CP13 / CP14 / CP15 / CP16 regression

**Blocked**, same pre-existing cause (not a new CP17 regression). Every
prior checkpoint's DB-backed tests still error at DB setup identically to
their own prior reports; every prior checkpoint's DB-free tests continue
to pass unchanged. CP14's `create_task()`/`log_activity()` and CP15's
`queue_email()`/`create_notification()` — the four functions this
checkpoint's action dispatchers call directly — explicitly re-verified
still importable and callable
(`test_cp14_cp15_functions_this_checkpoint_dispatches_into_are_unchanged`).
**None of their statuses were upgraded to VERIFIED** by CP17's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP16, re-verified (`psql` not found, no
Windows service, no Docker, no WSL).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP16 (re-verified: no `psql`, no service,
no Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs
were found in CP1–CP16's carried-forward code during Phase 1 verification
(`manage.py check`, `makemigrations --check --dry-run`, a full `pytest
-q` run, and `spectacular --file schema.yaml` all clean before any CP17
code was written).

One genuine, non-trivial OpenAPI enum collision occurred and was fixed —
see "OpenAPI" above; this is a DIFFERENT collision shape than every
prior `ENUM_NAME_OVERRIDES` case (same field name AND same choice
values, not just same field name), so it's recorded distinctly rather
than assumed to be "the same CP10/CP12 issue again." No index-name-length
issue, no test-authoring mistakes this checkpoint.

One design decision worth recording explicitly: **no Django signal is
wired to any CRM model (`Customer`/`Lead`/`Opportunity`/`Quote`/`Invoice`)
to fire `WorkflowTrigger`s automatically.** `ON_CREATE`/`ON_UPDATE`/
`ON_DELETE` trigger types are modeled and fully evaluable today via
`services.evaluate_and_run()` — but nothing in CP9's/CP11's/CP12's own
`save()`/`delete()` methods calls it. This was a deliberate scope
boundary, not an oversight: wiring an actual signal receiver would mean
editing ALREADY-SHIPPED checkpoints' models (or attaching `post_save`/
`post_delete` receivers to models this app doesn't own) as a side effect
of a NEW, unrelated checkpoint — the same restraint CP15 applied to not
widening `RelatedToEntityModel`'s allowed entity types and CP16 applied
to not adding entity-level access control it wasn't asked to build.
`MANUAL` is the only trigger type this checkpoint's own API exercises
end-to-end (via `WorkflowViewSet.execute`, which calls `run_workflow()`
directly, not `evaluate_and_run()` — an explicit, authenticated API call
IS the trigger, for a manual execution); `evaluate_and_run()` is fully
built, fully tested, and ready for a future checkpoint's signal receiver
to call.

### Deferred

- Actually wiring `evaluate_and_run()` to Django signals on CRM models —
  see "Problems encountered" above; the function exists and is tested,
  the wiring is a deliberately separate decision.
- More `ActionType`s (e.g. update a field on the entity, call a webhook)
  — `_ACTION_DISPATCHERS` is the extension seam, the same shape as
  CP16's `_REPORT_COMPUTERS`; not built because not requested.
- A boolean-expression condition language for `WorkflowTrigger.conditions`
  (AND/OR of multiple field checks, not just one) — `evaluate_conditions()`
  is deliberately basic (a single field-equality check), the same "basic
  X only" scope boundary CP14's recurrence support and CP15's template
  rendering both drew.
- Retrying a FAILED `WorkflowExecution` — `run_workflow()` records the
  failure; nothing currently re-attempts it. Would naturally pair with
  CP16's own deferred "async/background execution" item.

### Next

CP18 (blocked behind the same PostgreSQL issue affecting CP2–CP17's
DB-dependent verification)

---

## CP18 — Integrations (API Keys, Webhooks)

**Status:** PARTIAL / BLOCKED (implementation complete. `apps/integrations/`
totals 127 tests across 11 files — 80 genuinely pass with no database, 47
require a real database and are blocked. Project-wide: **854 passed, 678
errors** — up from CP17's 774/631, confirming zero regressions.)

### Files created

- `backend/apps/integrations/{__init__.py, apps.py, models.py, services.py,
  serializers.py, permissions.py, admin.py, filters.py, views.py,
  urls.py}` — a genuinely new Django app: API key issuance/rotation/
  revocation and outbound webhook signing/delivery, the project's first
  checkpoint centered on credential and secret management.
- `backend/apps/integrations/migrations/0001_initial.py` — hand-inspected;
  creates `Integration`, `APIKey`, `WebhookEndpoint`, `WebhookDelivery`
  and every declared index.
- `backend/apps/integrations/tests/{conftest, test_models, test_managers,
  test_services, test_serializers, test_permissions, test_admin,
  test_filters, test_api, test_urls, test_openapi, test_regression}.py`
  — 127 tests (80 pass with no database, 47 blocked).

### Files modified

- `backend/config/settings/base.py` — added `"apps.integrations"` to
  `LOCAL_APPS`.
- `backend/config/urls.py` — mounted `apps.integrations.urls` at
  `/api/v1/integrations/`.

No other existing file was touched. **No frontend file was read, opened,
or modified.**

### Migration

`apps/integrations/migrations/0001_initial.py` — creates all four tables
and 5 indexes. THREE index names initially exceeded PostgreSQL's
30-character limit — the `integrations` app label is longer than any
prior app's, so names that would have fit comfortably under `reports_`/
`workflows_` prefixes didn't fit under `integrations_`. Caught
immediately by `manage.py check`'s own system check (`models.E034`),
the same catch CP16 experienced once — fixed by shortening (e.g.
`integrations_integration_owner_idx` → `integrations_owner_idx`,
`integrations_delivery_status_idx` → `integ_delivery_status_idx`).
`makemigrations --check --dry-run` clean before and after. **Not
applied** — same PostgreSQL blocker as every prior checkpoint.

### Models

- **`Integration`** — `name`, `description`, `owner`, `is_active`. The
  only model here with a real `owner` FK.
- **`APIKey`** — `integration` (CASCADE), `name`, `key_prefix` (plaintext,
  unique, e.g. `clk_a1b2c3d4`), `key_hash` (a Django password hash — see
  Services), `is_active`, `last_used_at`, `expires_at`, `revoked_at`. NO
  field anywhere stores the raw key.
- **`WebhookEndpoint`** — `integration` (CASCADE), `url`, `secret`
  (PLAINTEXT — a deliberately different storage choice than `APIKey
  .key_hash`, see below), `event_types` (`JSONField` list), `is_active`.
- **`WebhookDelivery`** — `endpoint` (CASCADE), `event_type`, `payload`
  (`JSONField`), `status` (PENDING/DELIVERED/FAILED),
  `response_status_code`, `attempt_count`, `next_retry_at`,
  `delivered_at`, `error_message`. Written entirely by
  `services.deliver_webhook()` — no create endpoint (see ViewSets).

All four inherit `SoftDeleteTimeStampedModel` (CP7).
`APIKey`/`WebhookEndpoint` delegate `owner` to `integration.owner`;
`WebhookDelivery` delegates TWO levels deep to
`endpoint.integration.owner` — the same multi-level delegation chain
CP14's `Reminder.owner` established.

**Two deliberately different secret-storage strategies, for two
different kinds of secret:** `APIKey.key_hash` is a ONE-WAY hash (via
`django.contrib.auth.hashers.make_password()` — the SAME machinery CP4's
`User.set_access_code()`/`check_access_code()` already established for
the Super Admin secondary access code; no new hashing scheme
introduced) — correct because an API key is a credential presented TO
this API, which only ever needs to VERIFY it, never recover it.
`WebhookEndpoint.secret` is stored in PLAINTEXT — a genuinely different
and correct choice, because a webhook secret is used BY this API to SIGN
outbound payloads, and its owner may legitimately need to view/copy it
again later (the same UX Stripe/GitHub offer for their own webhook
signing secrets, unlike their API keys). Encrypting this field at rest
would be a real hardening improvement not built this checkpoint — see
Deferred.

### Managers

`IntegrationQuerySet` (`active()`, `by_owner(user)`), `APIKeyQuerySet`
(`active()` — not-deleted AND active AND not-revoked, a three-way
override of CP7's `active()`, not just the usual two-way "is_active"
extension), `WebhookEndpointQuerySet` (`active()`,
`subscribed_to(event_type)` — a PostgreSQL JSONField `__contains`
lookup), `WebhookDeliveryQuerySet` (`for_endpoint()`,
`due_for_retry(as_of=None)`). All four models get `objects`
(unfiltered)/`active_objects` (filtered) per CP7's convention.

### Services

`apps/integrations/services.py` re-exports CP10's `managed_user_ids()`/
`scope_queryset_for_user()` from `apps.crm.services` UNCHANGED. New
functions, in three groups:

1. **API keys** — `generate_api_key()` (returns `(api_key, raw_key)`;
   `raw_key` is the ONLY time the plaintext secret is ever available),
   `rotate_api_key()` (replaces the secret in place — the OLD raw key
   stops working immediately; rejects an already-revoked key),
   `revoke_api_key()` (permanent; rejects an already-revoked key, same
   "already closed" guard shape as CP11's `mark_won()`), `verify_api_key()`
   (looks up by `key_prefix`, verifies the hash, checks active/expired;
   NEVER raises — a bad credential is a normal outcome to report, not an
   error; updates `last_used_at` on success).
2. **Webhook signing** — `sign_payload()` (HMAC-SHA256,
   `sha256=<hex>` format, the same header convention GitHub/Stripe use),
   `verify_webhook_signature()` (constant-time comparison via
   `hmac.compare_digest()` — never a plain `==`, which would leak timing
   information about a forged signature).
3. **Webhook delivery + retry scheduling** — `deliver_webhook()`
   (injectable `send_func`, defaulting to a stdlib `urllib.request` POST
   — no new third-party HTTP client dependency; NEVER lets an exception
   propagate, the same "a failure is a recorded fact, not a crash"
   contract CP15's `send_queued_email()`/CP16's `execute_report()`/CP17's
   `run_workflow()` all established), `schedule_retry()` (a PURE
   date-math function computing `next_retry_at` via capped exponential
   backoff — "scheduling" means computing WHEN, not performing a retry;
   no background worker exists in this project, the same honest
   "abstraction, not a real scheduler" CP15's `queue_email()` already
   drew).

### Endpoints

`/api/v1/integrations/{integrations,webhook-endpoints}/` — full CRUD (no
PUT) + CP7's `restore`/`hard-delete`, plus
`webhook-endpoints/<id>/{regenerate-secret,deliver}/`.
`/api/v1/integrations/api-keys/` — full CRUD, but `POST` (create) is
overridden entirely to GENERATE a key rather than accept one, plus
`<id>/{rotate,revoke}/`. `/api/v1/integrations/webhook-deliveries/` —
**read-only** (list/retrieve only).

### ViewSets

Every viewset reuses CP10's `_CrmModelViewSet` (`apps.crm.views`)
directly — the same cross-app reuse CP12/CP14/CP15/CP16/CP17 already
established. `APIKeyViewSet.create()` is overridden entirely (an
`APIKey`'s secret is generated, never supplied by the client — the same
"input shape differs from output shape" reasoning CP15's
`EmailMessageViewSet.create()`/CP17's `WorkflowViewSet.execute` both
apply), returning `APIKeyWithSecretSerializer` — the ONLY serializer in
this app that ever carries the raw key, used exclusively by the
`create`/`rotate` responses, never by list/retrieve.
`WebhookEndpointViewSet.perform_create()` routes through
`services.create_webhook_endpoint()` for the same reason (`secret` is
read-only on the serializer; a bare `serializer.save()` would leave it
blank). `WebhookDeliveryViewSet` sets `http_method_names = ["get",
"head", "options"]` — the identical integrity-boundary technique CP15's
`CommunicationLogViewSet`/CP16's `ReportExecutionViewSet`/CP17's
`WorkflowExecutionViewSet` established.

### Filtering

`Integration`: `owner`, `is_active`. `APIKey`: `integration`,
`is_active`. `WebhookEndpoint`: `integration`, `is_active`.
`WebhookDelivery`: `endpoint`, `status`, `event_type`.

### Searching

`Integration`: `name`, `description`. `APIKey`: `name`, `key_prefix`.
`WebhookEndpoint`: `url`. `WebhookDelivery`: `event_type`.

### Ordering

`APIKey`: `created_at`, `last_used_at`. `WebhookEndpoint`: `created_at`.
`WebhookDelivery`: `created_at`, `delivered_at`, `status`.

### Pagination

CP10's project-wide `StandardPagination`, unchanged.

### Permissions

**No new comparison logic.** `IsOwnerOrSuperAdmin` (CP6) is re-exported
unchanged — every model here has an owner-shaped attribute (real field or
delegating property, including `WebhookDelivery`'s two-level delegation).

### OpenAPI

`manage.py spectacular --file schema.yaml` — zero errors, zero warnings.
One fix was needed: `APIKeyWithSecretSerializer.get_raw_key()` (a
`SerializerMethodField`) had no return-type hint, the identical
"unable to resolve type hint" warning CP14's `RelatedObjectMixin`
originally hit — fixed the same way, with `@extend_schema_field(str)`.
A dedicated test also confirms the PLAIN `APIKey` schema component (used
by list/retrieve) never documents `key_hash` or `raw_key` at all — not
merely that they're absent from a sampled response, but that the OpenAPI
contract itself makes no promise either field could ever appear.

### Tests

**No database required — genuinely executed, genuinely passing:** 80/80.
Covers every field/constraint/Meta definition (including confirming
`APIKey` has no field that could ever hold a raw key), `__str__`/property
behavior on in-memory instances (the two-level `WebhookDelivery.owner`
delegation chain), every queryset helper's compiled filter,
`sign_payload()`/`verify_webhook_signature()`'s pure HMAC logic
(deterministic for the same inputs, differs per secret, rejects a
tampered payload, rejects the wrong secret — genuinely DB-free, since
HMAC computation touches no model), `verify_api_key()`'s DB-free
short-circuits (`None`/empty input, wrong prefix — rejected before any
query would even be attempted), serializer field declarations (including
that `APIKeySerializer` has no `key_hash`/`raw_key` fields AT ALL, not
merely marked read-only), the admin registry (including that
`key_hash`/`secret` are enforced read-only in the Django admin itself),
filter class declarations, URL routing for every endpoint, and OpenAPI
schema generation.

**Requires database — blocked:** 47 tests covering real persistence and
cascade behavior; `key_prefix` uniqueness actually rejecting a collision;
the full generate → verify → rotate → verify-old-fails → verify-new-succeeds
→ revoke → verify-fails lifecycle against real rows (the actual proof
the hashing round-trips correctly, not just that the functions don't
raise); `deliver_webhook()`'s injectable `send_func` exercised for both
success and failure paths, confirming the signature it computes is
independently verifiable via `verify_webhook_signature()`;
`schedule_retry()`'s backoff timing bounds; full HTTP-level CRUD and
ownership-scoping enforcement (including that an Employee cannot see
another Employee's API keys OR webhook deliveries); search/pagination;
and full serializer validation. All error at the identical
`OperationalError` as every other DB-dependent test since CP2, zero
assertion failures.

No test-authoring mistakes this checkpoint — `WebhookEndpointQuerySet
.subscribed_to()`'s test (a PostgreSQL JSONField `__contains` lookup)
was written directly into the DB-required section from the start, the
same proactive habit CP15-CP17 have each applied to `ContentType.objects
.get_for_model()`-adjacent code.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 / CP8 / CP9 / CP10 / CP11 / CP12 / CP13 / CP14 / CP15 / CP16 / CP17 regression

**Blocked**, same pre-existing cause (not a new CP18 regression). Every
prior checkpoint's DB-backed tests still error at DB setup identically to
their own prior reports; every prior checkpoint's DB-free tests continue
to pass unchanged. CP4's `make_password()`/`check_password()` — the two
functions this checkpoint's API key hashing calls directly — explicitly
re-verified still importable and round-tripping correctly
(`test_cp4_password_hashing_helpers_still_importable`). **None of their
statuses were upgraded to VERIFIED** by CP18's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP17, re-verified (`psql` not found, no
Windows service, no Docker, no WSL).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP17 (re-verified: no `psql`, no service,
no Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs
were found in CP1–CP17's carried-forward code during Phase 1 verification
(`manage.py check`, `makemigrations --check --dry-run`, a full `pytest
-q` run, and `spectacular --file schema.yaml` all clean before any CP18
code was written).

Three index-name-length issues occurred and were fixed — see "Migration"
above; all three caught immediately by `manage.py check`'s own system
check, none discovered later. One `SerializerMethodField` type-hint
warning occurred and was fixed — see "OpenAPI" above, the same known fix
pattern CP14 first established. No test-authoring mistakes.

One design decision worth recording explicitly, beyond what's already
covered in "Models": **`APIKey` verification is deliberately allowed to
use Django's SLOW password hasher (PBKDF2/bcrypt via `make_password()`/
`check_password()`), even though API key verification could happen on
every authenticated API request in a real deployment.** This was
considered and kept deliberately, not overlooked — the hasher's
slowness is a FEATURE against offline brute-force cracking of a leaked
`key_hash`, the same reasoning GitHub/Stripe apply to their own API key
storage (both use slow, salted hashes, not fast HMAC lookups, for
exactly this credential). A future checkpoint under real production load
might introduce a fast-path cache (e.g. a short-TTL cache of
`raw_key -> verified APIKey`) to avoid re-hashing on every request, but
that is a performance optimization layered ON TOP of this checkpoint's
security posture, not a replacement for it.

### Deferred

- Field-level encryption at rest for `WebhookEndpoint.secret` — currently
  plaintext in the database (necessarily recoverable, since it's used to
  SIGN outbound payloads — see "Models"). A production hardening pass
  would add envelope encryption or a secrets-manager integration; this
  project has no KMS/encryption-at-rest layer yet, and building one was
  not requested this checkpoint. Documented as an explicit, known gap —
  the same honesty this project applied to CP4's rate limiting and
  CP15's absent SMTP configuration.
- A fast-path verification cache for `APIKey` — see "Problems
  encountered" above; not built, since this project has no request
  volume to optimize against yet.
- A background worker that automatically calls `deliver_webhook()` again
  for every `WebhookDelivery.objects.due_for_retry()` row —
  `schedule_retry()`/`due_for_retry()` are the building blocks; no
  scheduler itself was requested or built (the same gap CP15's
  `queue_email()`/CP16's async-execution item both already recorded).
- Per-event-type webhook payload SCHEMAS (validating that a
  `lead.created` payload actually has the shape a receiver would expect)
  — `WebhookEndpoint.event_types` is a plain list of strings with no
  schema enforcement; not requested.
- Inbound webhook signature verification (`verify_webhook_signature()`
  is fully built and tested, but this project has no webhook RECEIVER —
  it only ever sends). Documented in `services.py`'s own docstring as
  ready for a future receiver to use.

### Next

CP19 (blocked behind the same PostgreSQL issue affecting CP2–CP18's
DB-dependent verification)

---

## CP19 — Platform (Audit Log, Settings, Feature Flags, Background Jobs)

**Status:** PARTIAL / BLOCKED (implementation complete. `apps/system/`
totals 122 tests across 11 files — 69 genuinely pass with no database, 53
require a real database and are blocked. Project-wide: **923 passed, 731
errors** — up from CP18's 854/678, confirming zero regressions.)

### Files created

- `backend/apps/system/{__init__.py, apps.py, models.py, services.py,
  signals.py, serializers.py, permissions.py, admin.py, filters.py,
  views.py, urls.py}` — a genuinely new Django app: an immutable audit
  trail, global settings/feature flags, and background-job tracking.
  This is the first checkpoint whose `apps.py` does something besides
  declare config — its `ready()` connects `signals.py`'s audit-logging
  receivers (see Services, below).
- `backend/apps/system/migrations/0001_initial.py` — hand-inspected;
  creates `AuditLog`, `SystemSetting`, `FeatureFlag`, `BackgroundJob` and
  every declared index/constraint. `AuditLog` is notably the only table
  in the whole migration history with NO `is_deleted`/`deleted_at`
  columns.
- `backend/apps/system/tests/{conftest, test_models, test_managers,
  test_services, test_serializers, test_permissions, test_admin,
  test_filters, test_api, test_urls, test_openapi, test_regression}.py`
  — 122 tests (69 pass with no database, 53 blocked).

### Files modified

- `backend/config/settings/base.py` — added `"apps.system"` to
  `LOCAL_APPS`.
- `backend/config/urls.py` — mounted `apps.system.urls` at
  `/api/v1/system/`.

**No file in `apps.crm`/`apps.sales` — the models this checkpoint's
audit logging observes — was touched at all.** This is the literal,
verifiable answer to "integrate audit logging with existing apps...
without changing existing business behavior": zero lines changed in
either app. See Services, below, for how.

No frontend file was read, opened, or modified.

### Migration

`apps/system/migrations/0001_initial.py` — creates all four tables, 6
indexes, and 1 constraint (`FeatureFlag`'s `rollout_percentage` 0-100
range `CheckConstraint`). No index-name-length issue this checkpoint.
`makemigrations --check --dry-run` clean before and after. **Not
applied** — same PostgreSQL blocker as every prior checkpoint.

### Models

- **`AuditLog`** — `actor`, `action` (CREATE/UPDATE/DELETE/LOGIN/OTHER),
  `description`, `changes` (`JSONField`, a snapshot not a diff — see
  Deferred), `ip_address` (modeled, not yet populated — see Deferred),
  plus CP14's `content_type`/`object_id`/`related_object`. **The only
  model in this entire project that does NOT inherit
  `SoftDeleteTimeStampedModel`** — it inherits bare `TimeStampedModel`
  instead, deliberately with no soft-delete support at all. An audit
  trail a client (or even a Django admin staff user — see Admin) could
  soft-delete is not a trustworthy audit trail.
- **`SystemSetting`** — `key` (unique), `value` (`JSONField` — one column
  holds any settings value shape), `description`, `is_active`. Ordinary
  `SoftDeleteTimeStampedModel`.
- **`FeatureFlag`** — `key` (unique), `name`, `description`,
  `is_enabled` (master switch), `rollout_percentage` (0-100,
  DB-constrained). Ordinary `SoftDeleteTimeStampedModel`.
- **`BackgroundJob`** — `name`, `job_type`, `owner` (a REAL field, not
  delegated — the only model in this checkpoint with no parent record to
  delegate to), `status` (PENDING/RUNNING/COMPLETED/FAILED),
  `started_at`/`completed_at`/`result_data`/`error_message` — the FOURTH
  appearance of this exact shape after CP16's `ReportExecution`, CP17's
  `WorkflowExecution`, CP18's `WebhookDelivery`. This project has no
  actual task queue (no Celery/Redis — see `requirements.txt`'s own
  "LATER-only packages" note); `BackgroundJob` TRACKS an operation, it
  doesn't schedule or execute one.

### Managers

`AuditLogQuerySet` (`for_actor(user)`, `for_entity(entity)` — plain
`models.QuerySet`, not `SoftDeleteQuerySet`, since `AuditLog` has no
soft-delete to build on), `SystemSettingQuerySet`/`FeatureFlagQuerySet`
(`active()`), `BackgroundJobQuerySet` (`by_owner(user)`). Three of the
four models get `objects`/`active_objects` per CP7's convention;
`AuditLog` gets only a single unfiltered `objects` manager (there is no
"active" concept to filter by — every audit entry is equally real).

### Services

`apps/system/services.py` re-exports CP10's `managed_user_ids()`/
`scope_queryset_for_user()` UNCHANGED. New functions, in four groups:

1. **Audit logging** — `log_audit_event()`, the single place every
   `AuditLog` row is ever created. Called automatically by
   `signals.py`'s receivers, and directly available for events with no
   associated model save (e.g. a future LOGIN entry).
2. **Settings** — `get_setting(key, default=None)` (never raises — a
   missing key is a normal outcome), `set_setting()` (create-or-update).
3. **Feature-flag evaluation** — `is_feature_enabled(flag_key, user=None)`:
   fails closed for an unknown/disabled flag; at `rollout_percentage <
   100`, uses a DETERMINISTIC per-`(flag_key, user_id)` SHA-256 hash
   bucketed 0-99, so the same user always gets the same answer for the
   same flag (no flicker across requests) while different users spread
   roughly evenly across the rollout percentage.
4. **Background job tracking** — `create_background_job()`,
   `start_background_job()`/`complete_background_job()`/
   `fail_background_job()`, each a guarded state transition (raises
   `ValueError` on an invalid transition, e.g. completing a job that
   isn't RUNNING) — the same explicit-transition-function shape as
   CP16's `ReportExecution`/CP17's `WorkflowExecution` lifecycle, just
   split into three externally-callable steps instead of one
   all-in-one-call function, since a real background job's start/finish
   naturally happen in different requests/processes.

**`signals.py` is this checkpoint's actual "integrate audit logging"
implementation** — a `post_save` receiver connected (from `apps.py`'s
`AppConfig.ready()`) to a CURATED set of five existing models
(`Customer`, `Lead`, `Opportunity`, `Quote`, `Invoice` — the same five
CP14's `RELATABLE_ENTITY_TYPES` already recognizes). Every receiver
reads `actor` from the ALREADY-POPULATED `created_by`/`updated_by`
fields (stamped by every prior checkpoint's existing viewsets via CP7's
`stamp_audit_fields()`) rather than needing request context — no
thread-local middleware, no new cross-cutting infrastructure. Every
receiver is wrapped in a broad `try/except` that logs and swallows any
failure: audit logging must NEVER be able to break the save it's
observing, verified directly by
`test_audit_logging_failure_does_not_break_the_save_it_observes` (which
monkeypatches `log_audit_event` to raise, then confirms the `Customer`
still saves successfully).

### Endpoints

`/api/v1/system/audit-logs/` — **read-only**, Manager-or-above only.
`/api/v1/system/{settings,feature-flags}/` — full CRUD (no PUT) + CP7's
`restore`/`hard-delete`; any authenticated user reads, Manager-or-above
writes. `/api/v1/system/background-jobs/` — full CRUD + CP7's
`restore`/`hard-delete`, plus `<id>/{start,complete,fail}/`.

### ViewSets

Three different bases, matching `permissions.py`'s three shapes:
`AuditLogViewSet` is a PLAIN `rest_framework.viewsets.ReadOnlyModelViewSet`
— no CP7 mixin at all (nothing to soft-delete/restore) and no ownership
scoping (`AuditLog` has no owner; every Manager sees the SAME full trail,
confirmed by `test_manager_sees_full_audit_trail_not_just_own`).
`_SystemConfigModelViewSet` is a small local base for
`SystemSetting`/`FeatureFlag` — the THIRD appearance of this exact
judgment call after CP13's `_CatalogModelViewSet`/CP15's
`_ReferenceDataModelViewSet`. `BackgroundJobViewSet` reuses CP10's
`_CrmModelViewSet` directly (a real `owner` FK) — the same cross-app
reuse CP12/CP14/CP15/CP16/CP17/CP18 already established, with `status`/
`started_at`/`completed_at`/`result_data`/`error_message` all read-only
on the serializer — reachable only via the three lifecycle actions, the
same "state-machine fields are read-only, actions are the only way
through" pattern CP11's `Opportunity.stage` established.

### Filtering

`AuditLog`: `actor`, `action`, `content_type`, `object_id`.
`SystemSetting`: `is_active`. `FeatureFlag`: `is_enabled`.
`BackgroundJob`: `job_type`, `status`, `owner`.

### Searching

`AuditLog`: `description`. `SystemSetting`: `key`, `description`.
`FeatureFlag`: `key`, `name`, `description`. `BackgroundJob`: `name`,
`job_type`.

### Ordering

`AuditLog`: `created_at`, `action`. `SystemSetting`/`FeatureFlag`: `key`,
`created_at`, `updated_at`. `BackgroundJob`: `created_at`, `started_at`,
`completed_at`, `status`.

### Pagination

CP10's project-wide `StandardPagination`, unchanged.

### Permissions

**No new comparison logic**, but THREE different existing compositions
in one app for the first time: `IsManagerOrSuperAdmin` (CP6, bare) for
`AuditLog`; `SystemConfigWritePermission = ReadOnlyOrSuperAdmin |
IsManagerOrSuperAdmin` (the exact CP13/CP15/CP16 composition) for
`SystemSetting`/`FeatureFlag`; `IsOwnerOrSuperAdmin` (CP6) for
`BackgroundJob`.

### OpenAPI

`manage.py spectacular --file schema.yaml` — zero errors, zero warnings
on the first attempt.

### Tests

**No database required — genuinely executed, genuinely passing:** 69/69.
Covers every field/constraint/Meta definition (including confirming
`AuditLog` genuinely has no `is_deleted`/`deleted_at`/`soft_delete`),
`__str__`/property behavior, every queryset helper's compiled filter,
serializer field declarations (including that `AuditLog`'s serializer
has no soft-delete fields to expose), the `FeatureFlagSerializer
.validate_rollout_percentage()` bounds check, the admin registry
(including that `AuditLogAdmin.has_add/change/delete_permission()` all
return `False`), filter class declarations, URL routing for every
endpoint, and OpenAPI schema generation.

**Requires database — blocked:** 53 tests covering real persistence;
`FeatureFlag`'s rollout-percentage constraint actually rejecting an
out-of-range value; `is_feature_enabled()`'s full evaluation logic
against real flags (unknown/disabled/full/zero/deterministic-per-user
rollout); `BackgroundJob`'s full state-transition lifecycle (including
every invalid-transition rejection); full HTTP-level CRUD and
permission enforcement for all three access shapes; search/pagination;
full serializer validation; and — the checkpoint's centerpiece —
END-TO-END signal integration tests confirming that creating/updating a
real `Customer`/`Opportunity` genuinely writes the expected `AuditLog`
row (`test_creating_a_customer_writes_an_auditlog_entry`,
`test_updating_a_customer_writes_a_second_auditlog_entry`,
`test_creating_an_opportunity_writes_an_auditlog_entry`), that an
UNAUDITED model (`Address`) writes NOTHING
(`test_saving_an_unaudited_model_does_not_write_an_auditlog_entry` —
proving the curation is real, not accidental blanket coverage), and that
a broken audit-logging call never breaks the underlying save
(`test_audit_logging_failure_does_not_break_the_save_it_observes`). All
error at the identical `OperationalError` as every other DB-dependent
test since CP2, zero assertion failures.

No test-authoring mistakes this checkpoint.

### CP1 regression

**PASS.** `tests/test_infrastructure.py` — 3/3 passed, unchanged.

### CP2 / CP3 / CP4 / CP5 / CP6 / CP7 / CP8 / CP9 / CP10 / CP11 / CP12 / CP13 / CP14 / CP15 / CP16 / CP17 / CP18 regression

**Blocked**, same pre-existing cause (not a new CP19 regression). Every
prior checkpoint's DB-backed tests still error at DB setup identically to
their own prior reports; every prior checkpoint's DB-free tests continue
to pass unchanged.
`test_audit_signals_connect_to_exactly_the_five_curated_models_once_each`
explicitly confirms the signal wiring didn't accidentally double-connect
or sweep in an unintended model. **None of CP2-CP18's statuses were
upgraded to VERIFIED** by CP19's work.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP18, re-verified (`psql` not found, no
Windows service, no Docker, no WSL).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Problems encountered

Same PostgreSQL blocker as CP2–CP18 (re-verified: no `psql`, no service,
no Docker, no WSL). No SQLite fallback, no faked result. No genuine bugs
were found in CP1–CP18's carried-forward code during Phase 1 verification
(`manage.py check`, `makemigrations --check --dry-run`, a full `pytest
-q` run, and `spectacular --file schema.yaml` all clean before any CP19
code was written). No index-name-length issue, no test-authoring
mistakes this checkpoint.

Two design decisions worth recording explicitly, beyond what's already
covered above:

1. **`Opportunity.__str__` touches `self.customer.name` (a related-field
   access); the audit-log signal receiver's `description` deliberately
   does NOT call `str(instance)`.** Calling `str()` on an audited
   instance inside the signal would risk an extra, easy-to-miss database
   query on every single `Opportunity` save in a real deployment (if
   `customer` weren't already `select_related()`-cached at that point) —
   a genuine, if small, performance regression that would be very easy
   to introduce by reflexively using an instance's own `__str__` for a
   "human-readable" log line. `_record_save()`'s description instead
   uses only `sender.__name__`/`instance.pk`, values already in memory
   with zero query risk.
2. **The five audited models were chosen deliberately, not
   "everything."** `Address`/`ContactPerson` (CP9), `QuoteItem`/
   `InvoiceItem` (CP12), and every model in CP13-CP18's own apps are
   NOT audited — only the five top-level CRM/sales records a real
   compliance requirement would care about. Blanket-auditing every model
   in the project would multiply the number of `AuditLog` rows written
   per real user action many times over (e.g. every `QuoteItem` add
   would ALSO audit-log, on top of the `Quote` itself) for entries with
   little independent audit value, since line-item changes are already
   implied by their parent record's own audit trail.

### Deferred

- Field-level DIFFING for `AuditLog.changes` — currently unused/empty by
  the signal-based integration (the signal receivers don't populate it;
  `log_audit_event()`'s `changes` parameter exists for future direct
  callers). A real diff (old value vs. new value per changed field)
  would require capturing pre-save state, which `post_save` alone
  doesn't provide — a future checkpoint could add a paired `pre_save`
  receiver to capture the "before" snapshot. Not built this checkpoint;
  "basic audit logging only," the same scope discipline CP14's
  recurrence support and CP15's template rendering both drew.
- `AuditLog.ip_address` population — modeled but never set; capturing it
  would require request-scoped context available to a `post_save`
  signal, which Django doesn't provide natively (the standard solution
  is a thread-local-storing middleware — a genuine, if small, new piece
  of cross-cutting infrastructure not built this checkpoint, since
  `actor` capture via `created_by`/`updated_by` already works without
  it).
- A `DELETE`-action audit entry — only CREATE/UPDATE are wired
  (`post_save`); a `post_delete` receiver for the same five models would
  complete the set. Not built because CP9-CP12's own delete behavior for
  these models is SOFT delete (a `save()` with `is_deleted=True`), which
  the existing `post_save` receiver ALREADY captures as an UPDATE event
  — a genuinely separate DELETE action type would only matter for a
  future HARD delete of one of these five models, which none of their
  own viewsets currently expose without Manager-or-above's explicit
  `hard-delete` action.
- Wiring `apps.communications`/`apps.reports`/`apps.workflows`/
  `apps.integrations`'s own models into the same audit trail — the five
  audited models are deliberately the CORE CRM/sales records (see
  "Problems encountered" #2); extending audit coverage to other apps'
  models is a straightforward addition to `signals.py`'s tuple if a
  future checkpoint requests it, not a redesign.

### Next

CP20 (blocked behind the same PostgreSQL issue affecting CP2–CP19's
DB-dependent verification)

---

## CP20 — Final Project-Wide Audit (Regression, Security, Performance, Architecture)

**Status:** PARTIAL / BLOCKED. This checkpoint adds no new app — it is a
full audit of everything CP1–CP19 built. Every claim below was checked
directly against the current codebase, not recalled from memory. **Two
genuine, real bugs were found and fixed, both with zero behavior
change** (confirmed by an identical before/after full-suite test count).
`migrate` remains blocked by the same pre-existing PostgreSQL
unavailability as every prior checkpoint.

### Scope

No new models, no new endpoints, no new app. This checkpoint audited the
ENTIRE existing backend (12 apps, 45 models, 177 API paths, 14 migration
files, 1,654 total tests) for regressions, duplicated logic, circular
imports, PostgreSQL migration compatibility, security posture,
performance (N+1/indexing), and architectural consistency — then fixed
what was genuinely found, without touching anything that was already
correct.

### Files modified

- `backend/apps/core/views.py` — added `ReferenceDataModelViewSetMixin`
  (a new, small, shared base class — see "Duplicated logic," below).
- `backend/apps/catalog/views.py` — `_CatalogModelViewSet` now builds on
  the new shared mixin instead of redefining it.
- `backend/apps/communications/views.py` — `_ReferenceDataModelViewSet`
  likewise.
- `backend/apps/system/views.py` — `_SystemConfigModelViewSet` likewise.
- `backend/apps/core/permissions.py` — removed a stray `"User"` entry
  from `__all__` that referenced a name never imported in the module
  (see "Security review," below).

No model, migration, serializer, service function, or URL changed in
this checkpoint — every fix was either a pure code-organization change
(the viewset base extraction, byte-identical resulting behavior) or the
removal of dead, unreferenced code (the `__all__` entry). **No frontend
file was read, opened, or modified.**

### Regression audit

- **App registration**: all 12 `apps.*` entries in `LOCAL_APPS` confirmed
  present and correctly ordered in `INSTALLED_APPS`; `apps.core` confirmed
  to correctly have zero models (CP7 built abstract-only infrastructure,
  by design, never migrated on its own).
- **Migrations**: `MigrationLoader(connection=None)` (disk-only, no DB
  needed) confirms the FULL migration graph across all 12 apps builds
  with `validate_consistency()` passing — no missing dependencies, no
  cycles. 14 migration files total, matching the exact per-checkpoint
  history (`accounts`: 3 — CP2/CP4/CP5; `crm`: 2 — CP9/CP11; every other
  app: 1 initial migration each — CP8/CP12/CP13/CP14/CP15/CP16/CP17/
  CP18/CP19).
- **`manage.py check`**: 0 issues, silenced 0 — before AND after this
  checkpoint's two fixes.
- **`makemigrations --check --dry-run`**: "No changes detected" — before
  AND after.
- **Full test suite**: **923 passed, 731 errors, 0 failures** (1,654
  total tests) — run once BEFORE any CP20 change, and once AFTER both
  fixes; **the numbers are byte-identical in both runs**, the direct,
  measured proof that this checkpoint's fixes changed no behavior.
- **OpenAPI schema**: 0 warnings, 0 errors, 177 paths, 160 schema
  components, validates as OpenAPI 3 — generated fresh, at the end of
  this checkpoint's work, against the current (post-fix) codebase.

### Duplicated logic — found and fixed

`_CatalogModelViewSet` (CP13), `_ReferenceDataModelViewSet` (CP15), and
`_SystemConfigModelViewSet` (CP19) were three INDEPENDENTLY-written
viewset base classes, each documented at the time as a deliberate
non-reuse of the others (each hardcodes a different, domain-specific
`permission_classes` composition, so importing one into another would
have coupled unrelated apps' access rules together by coincidence — see
each checkpoint's own historical docstring, preserved verbatim in
`BACKEND_LEARNING_GUIDE.md`). That reasoning was correct for NOT
importing one INTO another. It did not extend to the six lines they
share byte-for-byte (`http_method_names`, and a `get_queryset()`
choosing the active-vs-unfiltered manager by action) — those six lines
were reimplemented identically three separate times. This project's own
established threshold (CP13's `CatalogItemQuerySet`, "three is where the
balance tips") applied here: a new `ReferenceDataModelViewSetMixin` in
`apps/core/views.py` now holds the SHARED six lines; each of the three
concrete base classes keeps its own, still-independent
`permission_classes` line, so no app depends on another app's specific
permission composition — only on `apps.core`, the same dependency
direction every other piece of shared infrastructure in this project
already has. Verified safe before refactoring (no test in the project
asserts against the exact private class name of any of the three, only
against the shared `SoftDeleteAuditModelViewSetMixin` ancestor, which
the new mixin still inherits from transitively) and verified correct
after (the four affected apps' full test suites — `catalog`,
`communications`, `system`, `core` — re-run in isolation: 252 passed, 165
errors, 0 failures, before the project-wide re-run confirmed the same
zero-diff result globally).

No other genuine duplication was found. `managed_user_ids()`/
`scope_queryset_for_user()` are imported (re-exported), not copied, by
six different apps' `services.py` — confirmed via a direct grep for the
import statement, not an assumption. The `_REPORT_COMPUTERS` (CP16) and
`_ACTION_DISPATCHERS` (CP17) dispatch tables look structurally similar
but serve genuinely different purposes (pure computation vs.
side-effecting action) and were correctly left separate, per CP17's own
chapter (§2).

### Import graph — circular dependencies

Every app's cross-app imports were extracted directly from the source
(not inferred) and assembled into a dependency graph:

```
accounts  (no dependencies)
core            -> accounts
organization    -> accounts, core
crm             -> accounts, core, organization
sales           -> accounts, core, crm
catalog         -> accounts, core
activities      -> accounts, core, crm
communications  -> accounts, core, crm, activities
reports         -> accounts, core, crm, activities
workflows       -> accounts, core, crm, activities, communications
integrations    -> accounts, core, crm
system          -> accounts, core, crm, activities, sales
```

This is a clean, strictly-layered directed acyclic graph — no app ever
imports from an app that (directly or transitively) depends on it. `django
.setup()` (which fails loudly on any real circular import at Django's own
app-loading stage) succeeded throughout every one of CP1–CP19's own
checkpoints and again here. No circular dependency exists anywhere in
this project.

### PostgreSQL migration compatibility

Every `models.Index` name across all 14 migration files was checked
against Django's own `Index.max_name_length` (confirmed via direct
introspection: `30`) — 66 total indexes, 0 over the limit, consistent
with every checkpoint's own proactive habit since CP13. Every
`UniqueConstraint`/`CheckConstraint` name was ALSO checked — 13 total
constraints, several exceeding 30 characters (the longest,
`activities_reminder_exactly_one_of_task_or_event`, is 48). This is
**not a bug**: `BaseConstraint` has no `max_name_length` attribute at
all (confirmed via direct introspection) — Django's 30-character rule is
an `Index`-specific, cross-database-portability convention (historically
for Oracle's 30-byte identifier limit), not a PostgreSQL requirement.
PostgreSQL's actual identifier limit (`NAMEDATALEN`) is 63 bytes by
default, comfortably accommodating every constraint name in this
project. The asymmetric treatment applied throughout CP9–CP19 (strict
≤30 for indexes, more relaxed for constraints) was correct all along,
not an inconsistency — this checkpoint confirms it with the actual
Django/PostgreSQL facts rather than by convention.

`JSONField` (used across 8 apps for flexible-shape data) and
`GenericIPAddressField` (CP19's `AuditLog.ip_address`) both map to
native, well-supported PostgreSQL column types (`jsonb`, `inet`) — no
compatibility concern. No SQLite-only or non-portable field usage found
anywhere in the project (consistent with this project never having used
SQLite at any point, per every checkpoint's own Database Verification
section).

### RBAC consistency

Every single `ViewSet`/`APIView` in the project was enumerated (via a
direct grep for every `class \w+View(Set)?\(` definition) and checked for
`permission_classes`. Result: **every one** either inherits
`_CrmModelViewSet` (`[IsAuthenticated, IsOwnerOrSuperAdmin]`), one of the
three reference-data bases (`[IsAuthenticated, <ComposedWritePermission>]`),
`AuditLogViewSet` (`[IsAuthenticated, IsManagerOrSuperAdmin]`), or
`apps.accounts`'s own explicitly-declared auth-flow permissions
(`AllowAny` ONLY for the three genuinely-public endpoints — login,
super-admin-verify, token refresh — every other `apps.accounts` endpoint
is `IsAuthenticated`). **Zero endpoints in the entire project rely on the
DRF project-wide default (`AllowAny`) implicitly** — every single one
makes an explicit, intentional access-control statement.

### Cross-app feature integration

Verified directly, not assumed:

- **Pagination**: zero viewsets override `pagination_class` — every list
  endpoint uses the global `StandardPagination` (CP10) uniformly.
- **Filtering/searching/ordering**: `DEFAULT_FILTER_BACKENDS` applies
  project-wide (CP7/CP10); every viewset with filterable fields declares
  its own `filterset_class`/`search_fields`/`ordering_fields`, none
  exposes a sensitive field (`key_hash`, `secret`, `password`) as
  filterable anywhere.
- **Soft delete**: every `SoftDeleteTimeStampedModel`-based viewset gets
  `restore`/`hard-delete` via `SoftDeleteAuditModelViewSetMixin`
  uniformly; the two deliberate exceptions (`AuditLog` — no soft delete
  at all; `WebhookDelivery`/`ReportExecution`/`WorkflowExecution`/
  `CommunicationLog` — read-only, no destructive actions) are each
  individually documented and were each independently re-confirmed in
  this audit's OpenAPI schema check (their `restore`/`hard-delete` paths
  are genuinely absent from the schema, not just unused).
- **Audit logging**: `apps.system.signals.register_audit_signals()`
  confirmed still connected to exactly its five curated models
  (`Customer`, `Lead`, `Opportunity`, `Quote`, `Invoice`), one receiver
  each, no duplicates, no unintended models swept in.
- **Ownership scoping**: `managed_user_ids()`/`scope_queryset_for_user()`
  (CP10) confirmed as the SOLE implementation reused by every owner-scoped
  viewset project-wide; the one documented exception
  (`ReminderViewSet`/`WebhookDeliveryViewSet`-style Q-based scoping for
  models whose ownership isn't a single ORM path) re-confirmed to apply
  the identical three-tier RULE via a different filter SHAPE, not
  different logic.

No cross-app feature was found to behave inconsistently between apps.

### Security review

Checked directly against the current code:

- **Authentication**: SimpleJWT (CP3), unchanged; every non-public
  endpoint requires it (see RBAC consistency, above).
- **Authorization**: role hierarchy (CP6) and ownership scoping (CP10)
  confirmed as the ONLY two authorization primitives in use anywhere —
  no endpoint checks `request.user.role` directly outside
  `apps.accounts.permissions`'s own definitions.
- **Password/API-key hashing**: `apps.accounts.models.User
  .set_access_code()`/`check_access_code()` and `apps.integrations
  .services.generate_api_key()`/`verify_api_key()` both confirmed to use
  Django's `make_password()`/`check_password()` — the same
  production-grade hasher, no custom cryptography anywhere in the
  project.
- **Webhook signing**: `apps.integrations.services.sign_payload()`/
  `verify_webhook_signature()` confirmed to use HMAC-SHA256 and
  `hmac.compare_digest()` (constant-time comparison) — re-verified this
  checkpoint, not just recalled from CP18's own report.
- **Audit logging**: confirmed the signal receiver's broad `try/except`
  is still in place and still prevents any audit-logging failure from
  ever propagating into the CRM operation it observes.
- **Object-level permissions**: every viewset's `get_object()` was
  checked for an override that might bypass DRF's
  `check_object_permissions()` call. Exactly one override exists in the
  entire project (`apps.accounts`'s `MeView.get_object()`, which returns
  `self.request.user` directly — safe by construction, since it can
  never return a DIFFERENT user's record regardless of any permission
  check). Every other viewset relies on DRF's own default `get_object()`,
  which always runs the object-level check.
- **Serializer exposure**: **zero serializers in the entire project use
  `fields = "__all__"` or `exclude = [...]`** (confirmed via a direct
  grep, not a sample check) — every one enumerates an explicit allowlist.
  `APIKeySerializer` confirmed to have no `key_hash`/`raw_key` field
  declared at all (not merely marked read-only). `UserSerializer`
  confirmed to exclude `password`/`is_staff`/`is_superuser`.
- **Admin permissions**: `APIKeyAdmin`/`WebhookEndpointAdmin` confirmed
  to mark `key_hash`/`secret` admin-readonly; `AuditLogAdmin` confirmed
  to disable add/change/delete entirely; `UserAdmin` confirmed to build
  on Django's own `UserAdmin` (battle-tested password-hash handling), not
  a custom implementation.
- **Secret handling**: `SECRET_KEY` confirmed to have no hardcoded
  fallback anywhere (`production.py` raises if unset); `DEBUG` confirmed
  `False` by default in `base.py`, re-asserted `False` in
  `production.py`; `CORS_ALLOWED_ORIGINS` confirmed to never combine a
  wildcard with `CORS_ALLOW_CREDENTIALS=True` — `production.py` requires
  an explicit origin list.

**One genuine bug found and fixed**: `apps/core/permissions.py`'s
`__all__` list included a stray `"User"` string with no corresponding
import anywhere in the module — `from apps.core.permissions import *`
would have raised `AttributeError: module 'apps.core.permissions' has no
attribute 'User'`. Confirmed dormant (no file in the project currently
performs that wildcard import, verified via grep), but a real, latent
bug in the module's own public contract. Fixed by removing the stray
entry; re-verified the wildcard import now succeeds and `manage.py
check` remains clean.

No other security issue was found.

### Performance review

Every viewset's `get_queryset()` was checked for `select_related`/
`prefetch_related` coverage against its serializer's actual field list.
Result: **every viewset serializing a foreign-key or reverse relationship
declares the matching `select_related`/`prefetch_related`** — 33 distinct
`select_related`/`prefetch_related` call sites found across 10 apps,
covering every FK the corresponding serializer actually reads (including
two-level chains like `"customer__owner"`/`"dashboard__owner"` for models
whose `owner` is a delegating property reaching through a parent
relation). The base `_CrmModelViewSet.get_queryset()` deliberately has
NO `select_related` of its own — correct, since it's model-agnostic; every
CONCRETE subclass adds its own on top via `super().get_queryset()
.select_related(...)`, confirmed present in every case that needs it. No
N+1 risk was found anywhere in the project's list/retrieve paths.

Indexing: every FK field gets Django's automatic index by default;
beyond that, every checkpoint added explicit composite indexes for its
own common filter/sort patterns (`(workflow, status)`,
`(content_type, object_id)`, `(key, is_read)`-shaped composites, etc.) —
66 explicit indexes total, all confirmed within Django's own naming
limit (see PostgreSQL compatibility, above).

No unnecessary queries, no missing indexes, and no pagination gaps were
found.

### Architecture review

- **Layering**: models → managers/querysets → services → serializers →
  permissions → admin/filters → views → urls, applied consistently
  across all 12 apps; verified no view ever bypasses a service function
  that has real behavior (auto-position assignment, hashing, signing,
  status-transition guards) to manipulate a model directly.
- **Service boundaries**: every app's `services.py` contains ONLY
  functions with real behavior beyond a bare `.create()`/`.save()` — thin
  wrappers exist for architectural symmetry (documented as such in each
  case), never as accidental indirection.
- **Reusable infrastructure**: CP6 (permissions)/CP7 (base models,
  timestamps, soft delete, audit stamping)/CP10 (pagination, ownership
  scoping) are the three pieces of infrastructure literally every
  subsequent checkpoint builds on — confirmed via the import graph
  (every app from CP8 onward imports at least `apps.core`, most import
  `apps.accounts.permissions`, ownership-scoped apps import
  `apps.crm.services`).
- **Dependency direction**: confirmed acyclic and strictly layered (see
  "Import graph," above) — no exceptions found.
- **App coupling**: every cross-app import is either (a) foundational
  infrastructure (`apps.core`, `apps.accounts.permissions`), (b) an
  explicitly-reused base class across a documented boundary
  (`_CrmModelViewSet`, now also `ReferenceDataModelViewSetMixin`), or (c)
  a deliberate, documented generic-relation/service reuse (CP14's
  `RelatedToEntityModel`/`RelatedObjectMixin`, CP10's
  `managed_user_ids()`). No accidental or undocumented coupling was
  found anywhere.

### OpenAPI summary

Final schema generation (run at the end of this checkpoint, against the
POST-fix codebase): **0 errors, 0 warnings, 177 paths, 160 components**,
validates as OpenAPI 3. Every resource's `restore`/`hard-delete`
availability (or deliberate absence, for the four read-only/immutable
resources) is correctly reflected in the schema.

### Testing summary

**1,654 total tests project-wide.** 923 genuinely pass with no database
(every single one of CP1–CP19's own "DB-free" test files, re-run in
full, twice — once before and once after this checkpoint's fixes, with
IDENTICAL results both times). 731 require a real database and remain
blocked, erroring at the identical `OperationalError` every DB-dependent
test in this project has hit since CP2. **Zero test failures anywhere,
in either run.**

### CP1–CP19 regression

**PASS for all.** No prior checkpoint's status changes — this audit found
two genuine, fixable issues (both now fixed), and confirmed everything
else already built was already correct. No prior checkpoint's DB-blocked
status was resolved (still blocked, same root cause) and none was
newly broken.

### Database verification

`settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"`
confirmed again. No live PostgreSQL server reachable on this machine —
identical root cause to CP2–CP19, re-verified (`psql` not found, no
Windows service, no Docker, no WSL).

### Frontend modified

**NO.** Confirmed via `git status` — only files under `backend/` changed.

### Deferred

Every item any prior checkpoint's own "Deferred" section recorded
remains deferred — this audit did not attempt to build any of them (that
was never CP20's task); it only confirmed each one is still accurately
described as deferred, not silently missing or silently built. See
CP2–CP19's own sections for the complete, itemized list (async
execution, real SMTP/webhook receivers, field-level encryption at rest,
signal wiring for automatic workflow triggers, etc.).

### Next

CP21, if commissioned — or PostgreSQL provisioning, the single blocker
standing between this project's current PARTIAL status and a genuine
COMPLETE/VERIFIED one across CP2–CP20.

---

\## Client Requirements



\- Super Admin / Manager / Employee hierarchy

\- Login / logout

\- Super Admin second secret access code

\- Employee activity tracking

\- Audit trail

\- Productivity reports

\- Lead management

\- Lead filtering/search

\- Lead age

\- Dial counts/history

\- Customer management

\- Phone number masking

\- Email masking

\- Data confidentiality

\- Desktop-only CRM / mobile-device restriction

\- Screenshot deterrence / defense-in-depth

\- Call records

\- Call recordings

\- Call transcription

\- Server-side authorization and data scope



Absolute OS-level screenshot prevention must NOT be claimed as possible.



\## Current API (updated in CP5)



\- `GET /health`

\- `GET /api/schema/`

\- `GET /api/docs/`

\- `POST /api/v1/auth/login/` (SUPER_ADMIN receives a challenge, not tokens — CP4; creates a UserSession — CP5)

\- `POST /api/v1/auth/super-admin/verify/` (CP4 — challenge + access code -> tokens; creates a UserSession — CP5)

\- `POST /api/v1/auth/refresh/` (CP5 — also updates the session's last_used_at / tracked JTI)

\- `POST /api/v1/auth/logout/` (CP5 — also deactivates the matching session)

\- `GET /api/v1/auth/me/` (requires a Bearer access token)

\- `GET /api/v1/auth/sessions/` (CP5 — requires a Bearer access token)

\- `DELETE /api/v1/auth/sessions/<id>/` (CP5 — requires a Bearer access token)

\- `POST /api/v1/auth/logout-all/` (CP5 — requires a Bearer access token)



Future domain APIs continue to be added under:



`/api/v1/`



\## Current Database (updated in CP2)



\- Engine: PostgreSQL (still the only engine configured anywhere — no SQLite

  fallback was introduced despite the blocker below)

\- Development DB (configured, not yet reachable): `crm\_db`

\- Application role (configured, not yet reachable): `crm\_dev`

\- Project domain models: `apps.accounts.User`

\- Project migrations: `apps/accounts/migrations/0001\_initial.py` (generated,

  inspected, NOT applied)

\- Built-in migrations: still unapplied (19 total now, was 18 — see Migration

  State above)

\- \*\*Live connection status: UNAVAILABLE.\*\* No PostgreSQL server exists on

  this machine (verified: no `psql`, no Windows service, no Docker, no WSL).

  `backend/.env` was created with local placeholder DB credentials so Django

  loads cleanly, but nothing is listening on port 5432 yet.



No secrets are stored in this document.



\## CP2 — Accounts + Custom User



See the full CP2 write-up below (after the CP1 section) for everything

implemented, verified, and blocked in this checkpoint.



\## CP3 — Authentication / JWT

See the full CP3 write-up below (after the CP2 section) for everything
implemented, verified, and blocked in this checkpoint. **Note:** CP3 was
explicitly authorized to proceed while CP2's `migrate`/DB-tests were still
blocked (the same missing-PostgreSQL environment issue — see both sections'
"Problems encountered"). CP3's own implementation is complete and verified
everywhere that does not require a live database, for the identical reason.

\## CP4 — Super Admin Secondary Access-Code Authentication

See the full CP4 write-up below (after the CP3 section) for everything
implemented, verified, and blocked in this checkpoint. **Note:** CP4 was
explicitly authorized to proceed while CP2/CP3's `migrate`/DB-tests were
still blocked (the same missing-PostgreSQL environment issue). CP4's own
implementation is complete and verified everywhere that does not require a
live database — and additionally, unlike CP2/CP3, a real subset of CP4's
own tests (the access-code hashing and challenge-signing logic) needed no
database at all and are genuinely passing now — see that section for exact
counts. **CP3's status is unchanged by CP4's work: it remains PARTIAL /
BLOCKED, not VERIFIED, because its PostgreSQL-backed migrate/tests still
have not actually run successfully.**

\## CP5 — Device / Session Authorization

See the full CP5 write-up below (after the CP4 section) for everything
implemented, verified, and blocked in this checkpoint. **Note:** CP5 was
explicitly authorized to proceed while CP2/CP3/CP4's `migrate`/DB-tests were
still blocked (the same missing-PostgreSQL environment issue). CP5's own
implementation is complete and verified everywhere that does not require a
live database — and, like CP4, a real subset of CP5's own tests (user-agent
parsing and IP extraction — no database involved) needed no database at all
and are genuinely passing now. **CP2/CP3/CP4's statuses are unchanged by
CP5's work: they remain PARTIAL / BLOCKED, not VERIFIED.**

\## Next — CP6 Hierarchy + RBAC (BLOCKED behind PostgreSQL)

CP2, CP3, CP4, and CP5 are all PARTIAL, not COMPLETE — their `migrate` steps
and every DB-backed test remain blocked on the same root cause: no
PostgreSQL instance exists anywhere on this machine. Per the Mandatory
Checkpoint Protocol below, CP6 should not begin until that is resolved and
CP2+CP3+CP4+CP5's remaining steps (migrate, tests, runtime verification) are
actually executed and pass.



\## Mandatory Checkpoint Protocol



Every checkpoint:



IMPLEMENT

→ CHECK

→ MIGRATION CHECK

→ MIGRATE when appropriate

→ TEST

→ VERIFY API/runtime

→ FIX

→ UPDATE `BACKEND\_PROGRESS.md`

→ UPDATE `BACKEND\_LEARNING\_GUIDE.md`

→ REPORT

→ STOP



If a checkpoint fails midway, record it as PARTIAL/BLOCKED instead of COMPLETE.

