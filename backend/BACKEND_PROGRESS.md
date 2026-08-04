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

| CP3 | Authentication / JWT | TODO |

| CP4 | Super Admin Access Key | TODO |

| CP5 | Device / Mobile Restriction | TODO |

| CP6 | Hierarchy + RBAC | TODO |

| CP7 | Leads | TODO |

| CP8 | Customers | TODO |

| CP9 | Follow-ups / Communications | TODO |

| CP10 | Calls / Dials | TODO |

| CP11 | Payments | TODO |

| CP12 | Activity / Audit | TODO |

| CP13 | Reports / Productivity | TODO |

| CP14 | PII Masking | TODO |

| CP15 | Call Recordings | TODO |

| CP16 | Transcription / Async Processing | TODO |

| CP17 | Deployment / Hardening | TODO |



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



\## Current API



\- `GET /health`

\- `GET /api/schema/`

\- `GET /api/docs/`



Future domain APIs:



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



\## Next — CP3 Authentication / JWT (BLOCKED behind CP2 finishing)



CP2 is PARTIAL, not COMPLETE. Per the Mandatory Checkpoint Protocol below,

CP3 must not begin until CP2's remaining steps (migrate, tests, runtime

verification) are actually executed and pass. That requires a real

PostgreSQL instance first — see "Problems encountered" in the CP2 section.



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

