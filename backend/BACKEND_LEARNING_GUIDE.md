# Qualify Learn CRM — Backend Learning Guide

This document is one half of the project's two deliverables. The other half is
the working backend itself. The goal here is that **you can explain how this
backend works in your own words** — in an assignment, viva, interview, or
technical discussion — not just that the code runs.

It grows one checkpoint at a time. This first section covers **Checkpoint 1
(CP1): the backend foundation.** Nothing about leads, users, authentication,
or calls exists yet — and that is deliberate. CP1 is only the skeleton that
everything else will hang on.

---

## Table of Contents (CP1)

1. What Django is and why this CRM uses it
2. Django project vs Django app
3. The current backend structure, file by file
4. Why settings are split (base / development / production)
5. Environment variables and secret management
6. PostgreSQL: the only database
7. The Django ORM (introduction)
8. Django REST Framework (DRF)
9. django-filter
10. django-cors-headers and why CORS is needed
11. drf-spectacular, OpenAPI, schema, and docs
12. The `/health` endpoint
13. WSGI vs ASGI
14. pytest, pytest-django, and the DRF APIClient
15. The three infrastructure tests explained
16. Verified CP1 results
17. Why we have NOT run `migrate` yet
18. CP1 security foundations
19. What CP1 intentionally does NOT contain
20. Common development commands
21. What I should understand before CP2

---

## 1. What Django is and why this CRM uses it

**Django** is a mature, "batteries-included" web framework written in Python.
"Batteries-included" means it ships with the pieces most web applications need,
already built and tested: an ORM (database layer), a URL router, a request/
response cycle, an authentication system, an admin site, a migration system,
security protections (CSRF, SQL-injection-safe queries, password hashing), and
a management-command runner.

**Why Django for this CRM specifically:**

- The CRM's core is *structured relational data* — users, teams, leads,
  customers, payments, calls — with strict ownership and permission rules.
  Django's ORM plus PostgreSQL is an excellent fit for that.
- The security requirements (role-based access, data-scoping, PII masking,
  audit logging, password/secret hashing) map directly onto Django primitives
  that already exist and are widely reviewed. We are told **not to invent
  custom cryptography**; Django lets us lean on established, audited tools.
- **Django REST Framework (DRF)** turns Django into a clean JSON API backend,
  which is exactly what a separate Next.js frontend needs to talk to.
- The migration system gives us a reliable, versioned history of every database
  schema change — important for a system that must be explainable and auditable.

In this project Django is used as a **pure API backend**. It does not render
the product's user interface — the existing Next.js app does. Django's own HTML
pages (like the admin site and the Swagger docs) are internal tools only.

---

## 2. Django project vs Django app

This is one of the most important mental models in Django.

- A **project** is the whole deployable thing — the configuration and the entry
  points. There is exactly **one** project. In our code the project is the
  `config/` package (settings, root URLs, WSGI/ASGI entry points) plus
  `manage.py`. The project doesn't usually contain business models itself; it
  *wires together* the apps that do.

- An **app** is a self-contained module of related functionality — its own
  models, views, serializers, and migrations. A project is composed of many
  apps. Later checkpoints add apps like `accounts`, `leads`, `customers`,
  `payments`, and so on. Each app owns one bounded slice of the domain.

Analogy: the **project** is the building's wiring, plumbing, and address; the
**apps** are the individual rooms, each with its own purpose. You can move a
well-designed app into another project the way you could reuse a room's design.

**In CP1 there are zero domain apps yet.** We have only the project skeleton.
The first real app (`accounts`) arrives in CP2.

---

## 3. The current backend structure, file by file

```
backend/
├── manage.py                     # command-line entry point
├── requirements.txt              # pinned Python dependencies (CP1 set)
├── pytest.ini                    # test runner configuration
├── .env                          # REAL secrets (gitignored, never committed)
├── .env.example                  # placeholder template (safe to commit)
├── BACKEND_LEARNING_GUIDE.md     # this document
├── config/                       # the Django PROJECT package
│   ├── __init__.py
│   ├── urls.py                   # root URL routing
│   ├── wsgi.py                   # WSGI entry point (sync servers)
│   ├── asgi.py                   # ASGI entry point (async servers)
│   └── settings/                 # split settings package
│       ├── __init__.py
│       ├── base.py               # shared settings
│       ├── development.py        # local-dev overrides
│       └── production.py         # deployment overrides
└── tests/
    └── test_infrastructure.py    # CP1 smoke tests
```

**What each piece is for:**

- **`manage.py`** — the administrative entry point. Every command you run
  (`check`, `makemigrations`, `migrate`, `runserver`, `test`) goes through it.
  It sets a default `DJANGO_SETTINGS_MODULE` of `config.settings.development`,
  so local commands use development settings unless you override that variable.

- **`config/`** — the project package. It holds *configuration and entry
  points*, not business logic.

- **`config/settings/base.py`** — settings that are true in **every**
  environment: installed apps, middleware, the DRF configuration, the database
  wiring (read from environment variables), drf-spectacular options, and the
  time/locale settings. Both other settings modules import from it.

- **`config/settings/development.py`** — local development overrides. Turns
  `DEBUG` on, provides a safe insecure fallback secret key so the project runs
  immediately after checkout, and allows the local Next.js origins for CORS.
  `manage.py` loads this module by default.

- **`config/settings/production.py`** — deployment overrides. Forces
  `DEBUG = False`, **requires** the secret key / allowed hosts / CORS origins to
  be supplied by the real environment (it raises an error if they are missing —
  no insecure fallbacks), and switches on HTTPS/secure-cookie/HSTS settings.

- **`config/urls.py`** — the root **URLconf**. It maps URL paths to the code
  that handles them. In CP1 it maps `/admin/`, `/health`, `/api/schema/`, and
  `/api/docs/`. Domain routes under `/api/v1/...` are added later.

- **`config/asgi.py` / `config/wsgi.py`** — the two entry points a web server
  uses to talk to Django. See section 13 for the difference. Both default to
  the **production** settings module, because they are what real servers load.

- **`.env`** — the real local secrets and database credentials (DB password,
  secret key, etc.). **Gitignored. Never read, printed, or committed.**

- **`.env.example`** — a committed *template* of the same variable names with
  **placeholder** values only. It tells a new developer which variables to set,
  without leaking any real value.

- **`pytest.ini`** — configures the test runner (which settings module to use,
  how to discover test files). See section 14.

- **`tests/`** — the automated tests. CP1 contains only infrastructure smoke
  tests.

---

## 4. Why settings are split (base / development / production)

A single `settings.py` file forces one configuration to serve two very
different worlds: your laptop and a hardened production server. Those worlds
have opposite needs:

| Concern            | Development           | Production                          |
|--------------------|-----------------------|-------------------------------------|
| `DEBUG`            | `True` (rich errors)  | `False` (no internal detail leaked) |
| Secret key         | insecure fallback OK  | must be a real secret, required     |
| Allowed hosts      | localhost is fine     | explicit real domains only          |
| HTTPS / secure cookies | off (plain http)  | on (SSL redirect, HSTS, secure cookies) |
| CORS origins       | localhost:3000        | explicit real frontend origin(s)    |

The **split settings pattern** solves this cleanly:

- `base.py` holds everything common.
- `development.py` and `production.py` each do `from .base import *` and then
  override only what differs.

This keeps the shared configuration in one place (no duplication/drift) while
letting each environment be exactly as safe as it should be. It also makes the
security contract obvious: a reviewer can open `production.py` and see, in a few
lines, that debug is off and secrets are mandatory.

---

## 5. Environment variables and secret management

**The rule: secrets live in the environment, not in code.**

Hard-coding a database password or secret key into a settings file means it
ends up in version control, visible to anyone with repo access, and identical
across every environment. That is exactly the kind of leak the CRM's security
requirements forbid.

Instead:

- Real values are stored as **environment variables**.
- In local development they are kept in **`backend/.env`**, which is loaded at
  startup by **python-dotenv** (`load_dotenv(...)` in `base.py`).
- `base.py` reads each value with a small `env()` helper (a thin wrapper around
  `os.environ.get`). If a value is absent, the settings decide what to do —
  development supplies safe fallbacks; production refuses to start.

**`.env` vs `.env.example`:**

- **`.env`** = the *real* values. It is **gitignored** so it can never be
  committed. This guide never reads or prints it.
- **`.env.example`** = a *template* with the same keys but placeholder values
  (e.g. `DB_PASSWORD=` left blank). It is safe to commit and documents what a
  developer must configure.

**Why `.env` is gitignored:** a committed secret is a leaked secret — git keeps
history forever, so even deleting it later doesn't undo the exposure. Keeping
`.env` out of git entirely is the only safe default. The repository `.gitignore`
ignores `backend/.env` (and `.env.*`) while explicitly *un-ignoring*
`.env.example` so the template stays tracked.

---

## 6. PostgreSQL: the only database

**PostgreSQL is the sole database for this project — there is no SQLite
fallback, by design.**

- **`crm_db`** — the dedicated development database for this CRM.
- **`crm_dev`** — the dedicated application database *user* that Django connects
  as. Its credentials live in `.env`.
- **psycopg** — the PostgreSQL driver (the `psycopg[binary]` package). It is the
  library Django uses to actually speak PostgreSQL's wire protocol. Django's
  `django.db.backends.postgresql` engine sits on top of it.

**Why a dedicated `crm_dev` user instead of the `postgres` superuser:**

The `postgres` superuser can do anything on the entire server — drop any
database, read any other database, create/destroy roles. An application should
run with the **least privilege** it needs: rights on its own database and
nothing more. If the app (or a leaked credential) is ever compromised, the blast
radius is limited to `crm_db`, not the whole PostgreSQL instance. Using a
scoped application user is a standard production-hygiene practice, and we adopt
it from day one so development mirrors production.

**Why no SQLite fallback:**

SQLite behaves differently from PostgreSQL in ways that matter to this CRM:
constraint enforcement, transaction semantics, data types (e.g. real `DECIMAL`
handling for money), case sensitivity, and advanced features we will rely on
later (proper indexing, `FILTER`-clause aggregates, partial unique constraints).
If we developed on SQLite and deployed on PostgreSQL, code could pass locally and
break in production — the worst kind of bug. Developing on the *same* database
engine we deploy on removes that entire class of surprise. So if PostgreSQL is
unavailable, the correct response is to **fix PostgreSQL**, never to silently
switch to SQLite.

---

## 7. The Django ORM (introduction)

The **ORM (Object-Relational Mapper)** lets you work with database rows as
Python objects instead of writing raw SQL. You define a **model** (a Python
class), and Django maps it to a database table; each instance is a row, each
attribute a column.

Two big benefits for this project:

1. **Safety.** ORM queries are parameterized, which prevents SQL injection by
   default — a direct hit on one of the CRM's security requirements.
2. **Migrations.** When you change a model, Django generates a *migration* — a
   versioned, replayable description of the schema change. The database schema
   becomes a tracked, reviewable history rather than a pile of manual SQL.

**Important for CP1:** we have **not created any domain models yet.** There is
no `User`, `Lead`, `Customer`, or `Call` model in our code. The only tables that
*would* exist are Django's own built-in ones (auth, sessions, admin, content
types) — and even those are **not created yet**, because we have intentionally
not run `migrate` (see section 17). The ORM is configured and ready; we simply
have not defined anything for it to map. That begins in CP2.

---

## 8. Django REST Framework (DRF)

**DRF** is the library that turns Django into a clean JSON API backend. It adds
the building blocks an API needs on top of Django:

- **Serializers** — translate between Python/Django model objects and JSON, and
  validate incoming data. Think of a serializer as the contract for what a
  request may send and what a response will contain. (This is also where
  server-side PII masking will live later — the serializer decides what a given
  user is allowed to see.)
- **Views / ViewSets** — the code that handles a request: fetch data, apply
  permissions, call a serializer, return a response. ViewSets bundle the common
  list/create/retrieve/update/delete actions together.
- **Permissions** — reusable classes that decide *who* may perform an action.
  This is one of the layers that will enforce role- and hierarchy-based access.

**The DRF foundation configured in CP1** (in `base.py`, `REST_FRAMEWORK`):

- **Schema class** set to drf-spectacular's, so the OpenAPI schema can be
  generated automatically.
- **Pagination** — a default `PageNumberPagination` with a page size, so that
  *no* list endpoint can ever return an unbounded result set. Large tables of
  leads/customers must always be paged.
- **Filtering / search / ordering** — the default filter backends are wired up
  (`DjangoFilterBackend`, `SearchFilter`, `OrderingFilter`). These are the tools
  that later power lead filtering, search, and sorting.
- **Authentication / permissions** — deliberately minimal in CP1. The only
  endpoints that exist are public infrastructure endpoints, so authentication
  classes are empty and the default permission is `AllowAny`. **Real
  authentication and permission enforcement are introduced in CP3 and CP6** and
  will replace these defaults.

**Future `/api/v1/` structure:** all domain endpoints will be mounted under a
versioned prefix, e.g. `/api/v1/leads/`, `/api/v1/customers/`. Versioning in the
URL means we can evolve the API later (a hypothetical `/api/v2/`) without
breaking existing clients. CP1 establishes the `/api/` prefix (for schema and
docs); the `/v1/` domain groups arrive with the first real endpoints.

---

## 9. django-filter

**django-filter** provides declarative, server-side filtering for list
endpoints. Instead of hand-parsing query-string parameters and building
querysets by hand, you declare which fields are filterable and django-filter
translates URL parameters like `?status=HOT&source=WEBSITE` into safe ORM
queries.

Why it matters for this CRM: the client explicitly wants rich lead filtering —
by status, source, owner, date range, lead age bucket, and more. django-filter
is the standard, well-tested way to express that cleanly and safely (the
generated queries are parameterized, so filtering can't be abused for
injection). In CP1 it is only *registered* as a default filter backend; it does
real work starting at CP7 when the `Lead` list endpoint appears.

---

## 10. django-cors-headers and why CORS is needed

**CORS (Cross-Origin Resource Sharing)** is a browser security mechanism. By
default, a web page served from one origin (say `http://localhost:3000`, the
Next.js frontend) is **not** allowed to make JavaScript requests to a different
origin (say the Django API on another port/domain). The browser blocks it unless
the server explicitly says "I permit that origin."

Because our frontend and backend are **separate applications on separate
origins**, every API call the Next.js app makes is a cross-origin request. Without
CORS configuration those calls would be blocked by the browser.

**django-cors-headers** adds the response headers that tell the browser which
origins are allowed. Our configuration:

- `CORS_ALLOWED_ORIGINS` is an **explicit list** (never a wildcard) — in
  development it defaults to the local Next.js origins; in production it must be
  set explicitly and the app refuses to start without it.
- `CORS_ALLOW_CREDENTIALS = True` because later the refresh token is delivered
  in an HttpOnly cookie, and credentialed cross-origin requests require both this
  flag and a specific (non-wildcard) origin list.
- The `CorsMiddleware` is placed **before** `CommonMiddleware` so the CORS
  headers are attached early in the response cycle.

---

## 11. drf-spectacular, OpenAPI, schema, and docs

**OpenAPI** is a standard, machine-readable format for describing a REST API —
its endpoints, parameters, request/response shapes, and auth. An OpenAPI
document lets tools generate documentation, client SDKs, and test stubs
automatically.

**drf-spectacular** generates an OpenAPI 3 document from our DRF code by
inspecting the views and serializers. It gives us two endpoints:

- **`/api/schema/`** — returns the raw OpenAPI schema document itself
  (consumed by tools, or by the docs UI).
- **`/api/docs/`** — serves **Swagger UI**, an interactive HTML page that reads
  the schema and lets you browse and try every endpoint from the browser.

The value: the API documentation is **generated from the real code**, so it
can't silently drift out of sync with what the API actually does. As we add
domain endpoints, they appear in the docs automatically.

---

## 12. The `/health` endpoint

`GET /health` returns, with HTTP 200:

```json
{"status": "healthy", "service": "crm-backend"}
```

It is a **liveness probe** — the simplest possible "is the application process
up and able to serve a request?" check. Load balancers, container orchestrators,
and uptime monitors hit endpoints like this to decide whether the service is
alive.

**Why CP1's health check does NOT query PostgreSQL:** a *liveness* check should
answer only "is the web application itself running?" If we made `/health` query
the database, then a database hiccup would make the app *look* dead even though
the process is fine — and an orchestrator might needlessly kill/restart it. The
distinction is deliberate:

- **Liveness** ("is the process up?") — what `/health` does now, no dependencies.
- **Readiness** ("can it serve real traffic, including its database?") — a
  separate, DB-aware check we can add later if a deployment needs it.

Keeping them separate is a standard operational pattern.

---

## 13. WSGI vs ASGI

Both are standard interfaces between a **web server** and a **Python web
application** — they define how the server hands an incoming request to Django
and gets a response back.

- **WSGI (Web Server Gateway Interface)** — the long-established *synchronous*
  standard. One request is handled to completion at a time per worker. It is
  perfect for a conventional request/response JSON API like ours. `wsgi.py`
  exposes the WSGI `application` object.
- **ASGI (Asynchronous Server Gateway Interface)** — the newer *asynchronous*
  standard. It supports long-lived connections and concurrency primitives that
  WSGI can't, such as **WebSockets** and streaming. `asgi.py` exposes the ASGI
  `application` object.

For this CRM's current needs, **WSGI is entirely sufficient** — it's a standard
REST API. We provide `asgi.py` as well because Django generates it and it costs
nothing to keep the door open for a future async feature (for example,
real-time notifications) without restructuring the project. Both entry points
default to the production settings module, since they are what real servers load.

---

## 14. pytest, pytest-django, and the DRF APIClient

- **pytest** is a popular Python test framework. Compared with the standard
  library's `unittest`, it uses plain functions and plain `assert` statements,
  which makes tests short and readable.
- **pytest-django** is the plugin that teaches pytest how to work with Django —
  it sets up the settings module, manages a **temporary test database**, and
  provides Django-aware fixtures. Our `pytest.ini` points it at
  `config.settings.development` and defines the test-discovery patterns.
- **DRF's `APIClient`** is a test client for making fake HTTP requests to the
  API inside a test — `client.get("/health")` — and inspecting the response
  (status code, JSON body) without running a real server.

Together they let us **actually verify behavior** rather than assume it. The
project's guiding rule is *never claim something works without running it*;
these tools are how we honor that for the API.

> Note: pytest-django creates a throwaway test database. Because we have not yet
> defined our custom `User` model, CP1's tests are written to exercise only the
> stateless infrastructure endpoints and do not depend on domain tables.

---

## 15. The three infrastructure tests explained

File: `tests/test_infrastructure.py`. Three smoke tests, one per CP1 endpoint:

1. **`test_health_returns_healthy_json`** — sends `GET /health`, asserts the
   status is `200`, and asserts the JSON body equals **exactly**
   `{"status": "healthy", "service": "crm-backend"}`. This pins down the health
   contract so it can't change accidentally.

2. **`test_schema_returns_non_empty_openapi`** — sends `GET /api/schema/`,
   asserts `200`, asserts the body is non-empty, and checks it looks like an
   OpenAPI document (contains `openapi`). This proves drf-spectacular is wired
   up and producing a real schema.

3. **`test_docs_returns_swagger_page`** — sends `GET /api/docs/`, asserts `200`
   and that the returned HTML is the Swagger UI page (contains `swagger`). This
   proves the interactive docs render.

They are **smoke tests**: fast, shallow checks that the plumbing is connected.
They intentionally do not test business logic, because there is no business
logic yet.

---

## 16. Verified CP1 results

These are the **actual** results from running the verification steps (not
assumed — executed):

```
manage.py check
    System check identified no issues (0 silenced).

PostgreSQL connection
    PostgreSQL connection successful
    Database engine: postgresql
    Database name: crm_db

manage.py makemigrations --check --dry-run
    No changes detected

pytest
    3 passed

Runtime HTTP verification
    GET /health       -> 200
    GET /api/schema/  -> 200
    GET /api/docs/    -> 200
```

Interpretation:

- **`check` clean** — no configuration or wiring problems.
- **PostgreSQL confirmed** — Django connects to the real `crm_db` on the
  `postgresql` engine (not SQLite).
- **`makemigrations --check --dry-run` → "No changes detected"** — there are no
  un-generated model changes; because we have defined no models, there is
  nothing to migrate *from our code*. (This is separate from the *built-in*
  migrations that remain unapplied — see the next section.)
- **`pytest` 3 passed** — all three infrastructure endpoints behave correctly.
- **Runtime 200s** — the endpoints also work against a live `runserver`, not
  just in tests.

---

## 17. Why we have NOT run `migrate` yet

This is a deliberate, important architectural decision.

Right now Django reports **18 unapplied built-in migrations** (from
`auth`, `admin`, `sessions`, `contenttypes`, etc.). We are **intentionally not
applying them yet.**

**The reason: the custom `User` model.** This CRM will use a *custom* user model
(`accounts.User`) configured via:

```python
AUTH_USER_MODEL = "accounts.User"
```

Django has a hard rule here: **`AUTH_USER_MODEL` must be set before the very
first migration is applied.** The built-in `auth` migrations create the user
table. If we run `migrate` now, Django creates the *default* user table, and the
whole database becomes tied to that default user. Switching to a custom user
model *after* that point is notoriously painful — it typically requires wiping
and rebuilding the database, because foreign keys throughout the system would
already point at the wrong user table.

By **not** migrating in CP1, we keep the database completely clean, so CP2 can
introduce the custom `User` model *first* and then run the first migration with
`AUTH_USER_MODEL` already in place.

**Intended sequence:**

```
CP1  backend infrastructure (no migrate)
  -> CP2  create the accounts app
  -> define the custom User model
  -> set AUTH_USER_MODEL = "accounts.User"
  -> generate the initial accounts migration
  -> FIRST migrate (built-in + accounts together, in the right order)
```

So the 18 unapplied migrations are not a problem to fix — they are a door we are
holding open on purpose.

---

## 18. CP1 security foundations

CP1 has no authentication yet, but it already lays several security foundations:

- **Secrets in the environment** — the secret key and database password are read
  from environment variables via `.env`, never hard-coded.
- **`.env` protection** — `.env` is gitignored (verified) so real secrets can't
  be committed; only the placeholder `.env.example` is tracked.
- **Dedicated database user** — Django connects as the least-privilege `crm_dev`
  user against `crm_db`, not as the `postgres` superuser.
- **Production settings hardened** — `production.py` forces `DEBUG = False`,
  *requires* the secret key / allowed hosts / CORS origins (no insecure
  fallbacks), and turns on SSL redirect, secure cookies, and HSTS.
- **CORS restricted** — allowed origins are an explicit list, never a wildcard,
  and are mandatory in production.
- **Injection-safe by default** — using the Django ORM (once models exist) means
  queries are parameterized.

What is **not** here yet (correctly): no authentication, no JWT, no role checks,
no PII masking. Those are the subject of later checkpoints.

---

## 19. What CP1 intentionally does NOT contain

To keep each checkpoint verifiable and the architecture sequencing correct, CP1
deliberately excludes all of the following. Their absence is by design, not an
oversight:

- Custom `User` model (CP2)
- Authentication / JWT / login-logout / sessions (CP3)
- Super Admin access key + intermediate verification state (CP4)
- Device authorization / desktop-only enforcement (CP5)
- Hierarchy / RBAC / data-scope / capability registry (CP6)
- Leads (CP7)
- Customers, conversion, duplicates/merge (CP8)
- Tasks, follow-ups, communications (CP9)
- Calls / dial history (CP10)
- Payments (CP11)
- Employee activity + audit log (CP12)
- Reports / productivity (CP13)
- PII masking wired into the frontend (CP14)
- Call recordings + storage (CP15)
- Call transcription, Celery, Redis (CP16)
- External providers (calling / STT / storage SDKs) — none installed
- Any AI analysis — explicitly out of scope for the whole project

---

## 20. Common development commands

Run these from `backend/` using the project's virtual environment
(`./.venv/Scripts/python.exe` on this Windows machine):

```
# Validate project configuration (no DB write)
./.venv/Scripts/python.exe manage.py check

# Show whether models would require new migrations (no write)
./.venv/Scripts/python.exe manage.py makemigrations --check --dry-run

# Apply migrations  (NOT run during CP1 — see section 17)
./.venv/Scripts/python.exe manage.py migrate

# Run the test suite
./.venv/Scripts/python.exe -m pytest -v

# Start the local development server
./.venv/Scripts/python.exe manage.py runserver
```

Reminder: `manage.py` defaults to development settings. Production servers load
`config.settings.production` via `wsgi.py` / `asgi.py`.

---

## 21. What I should understand before CP2

Before moving to CP2, make sure you can explain, in your own words:

1. **Project vs app** — why `config/` is the project and why `accounts` will be
   the first app.
2. **The settings split** — what belongs in `base` vs `development` vs
   `production`, and why production refuses to start without real secrets.
3. **Secret management** — the role of `.env` vs `.env.example`, and why `.env`
   is gitignored.
4. **Why PostgreSQL only** — why there is no SQLite fallback and why we use the
   scoped `crm_dev` user.
5. **What DRF adds** — serializers, views, permissions, pagination, and where
   PII masking will eventually live.
6. **Why CORS exists** — because the frontend and backend are separate origins.
7. **The single most important CP2 prerequisite:** *the custom `User` model must
   be defined and `AUTH_USER_MODEL` set **before** the first `migrate`.* Be able
   to explain why changing it afterward is so costly. This is the reason CP1
   ends with migrations intentionally unapplied.

**Viva-style questions to test yourself:**

- Why can't we just add a custom user model later, after migrating?
- What would break if we developed on SQLite and deployed on PostgreSQL?
- Why does `/health` not touch the database?
- What is the difference between WSGI and ASGI, and which does this API need?
- Why is `DEBUG = False` important in production, and what could `DEBUG = True`
  leak?
- What does "No changes detected" from `makemigrations --check` actually tell
  you, and how is it different from the 18 unapplied built-in migrations?

---

# Checkpoint 2 (CP2): Accounts + Custom User

CP1 was the skeleton. CP2 puts the first bone on it: **identity**. Every
future checkpoint — login, the Super Admin access key, hierarchy, RBAC,
row-level data scope, employee activity, audit logging — depends on *who a
request is coming from*. That's what a `User` model answers. Get it wrong (or
add it too late) and everything built on top inherits the mistake.

## Table of Contents (CP2)

1. Why a custom User model must be created early
2. `AbstractBaseUser`
3. `PermissionsMixin`
4. `UserManager`
5. `USERNAME_FIELD`
6. `REQUIRED_FIELDS`
7. Django password hashing
8. Why `set_password()` matters
9. `create_user` vs `create_superuser`
10. Django `is_staff` vs `is_superuser` vs the CRM `role`
11. `TextChoices`
12. `AUTH_USER_MODEL`
13. `get_user_model()`
14. Why direct imports of `User` can be problematic
15. Migration dependency concepts
16. Why we delayed the first `migrate` until CP2
17. What actually happened when we tried the first `migrate`
18. How the custom User relates to future JWT authentication
19. Why RBAC is NOT fully implemented yet
20. Why hierarchy is NOT fully implemented yet
21. Security lessons from CP2
22. Tests introduced in CP2
23. Commands actually executed and their actual results
24. Problems encountered and how they were fixed
25. What I should understand before CP3

---

## 1. Why a custom User model must be created early

Django ships a *default* `User` model (`django.contrib.auth.models.User`)
that uses `username` as the login field and has a fixed set of columns. The
moment you run `migrate` for the first time, Django creates that table (or
your custom one, if configured) and — critically — every other app's
`ForeignKey(User)` and the built-in `auth`/`admin` migrations bake in a
reference to *that specific table*.

Swapping the user model after that point is not a settings change; it's a
data migration nightmare, because:

- Every foreign key pointing at the old user table needs to point at the new
  one instead.
- Django's own migration history assumes the user table's identity never
  changes.
- In practice, teams that hit this mid-project usually end up dropping and
  rebuilding the database, which is unacceptable once real data exists.

So the rule (stated directly in Django's own documentation) is: **decide your
user model before the first `migrate`, or accept a very painful migration
later.** CP1 deliberately left 18 built-in migrations unapplied specifically
so CP2 could define `accounts.User` and set `AUTH_USER_MODEL` *before* that
first `migrate` ever runs.

## 2. `AbstractBaseUser`

`AbstractBaseUser` is Django's minimal building block for a custom user
model. It provides only:

- a `password` field (always a hash, via `set_password()`/`check_password()`)
- a `last_login` field
- the machinery Django's authentication backends call (`check_password`,
  `set_password`, `get_session_auth_hash`, etc.)

It does **not** provide `is_active`, `is_staff`, `email`, or any identity
field — you add exactly what your project needs. That's the point: instead of
inheriting Django's default `User` (username, first/last name, email as an
optional extra) and fighting its shape, you build the shape the CRM actually
needs — email-first, with a `role`.

## 3. `PermissionsMixin`

`PermissionsMixin` is a separate, optional mixin that adds Django's
*built-in* permission system:

- `is_superuser`
- `groups` (a `ManyToManyField` to `auth.Group`)
- `user_permissions` (a `ManyToManyField` to `auth.Permission`)
- `has_perm()`, `has_perms()`, `has_module_perms()`

We include it for one concrete reason: **the Django admin site requires it**
to know who can log in and what they can do there. We are *not* using
Django's groups/permissions system as the CRM's actual RBAC engine — that's a
purpose-built system arriving in CP6. `PermissionsMixin` is here so the admin
site works correctly today, not because groups/permissions are our long-term
authorization model.

## 4. `UserManager`

A **manager** is the object you call `.objects` through — `User.objects.all()`,
`User.objects.create_user(...)`. Django's default manager assumes a
`username`-based `create_user(username, email, password)` signature, which
doesn't fit an email-only model. `apps/accounts/managers.py` defines a
`UserManager(BaseUserManager)` with an email-first signature:

```python
create_user(email, password=None, **extra_fields)
create_superuser(email, password=None, **extra_fields)
```

Both funnel through a private `_create_user()` that normalizes the email,
hashes the password, validates the instance, and saves it — so the two public
methods stay short and the actual creation logic exists in exactly one place.

## 5. `USERNAME_FIELD`

`USERNAME_FIELD` tells Django's auth system which field is the login
identity — the thing a user types into the "username" box (even though, for
us, that box is labeled "email"). We set:

```python
USERNAME_FIELD = "email"
```

This affects `authenticate()`, the admin login form, `createsuperuser`'s
prompts, and anywhere Django needs to say "look this user up by their login
identity."

## 6. `REQUIRED_FIELDS`

`REQUIRED_FIELDS` lists the fields (besides `USERNAME_FIELD` and the
always-implicitly-required `password`) that `createsuperuser` must prompt
for. Since `first_name`/`last_name` are `blank=True` (optional) on our model
and nothing else is mandatory, ours is:

```python
REQUIRED_FIELDS = []
```

A common mistake is putting `"email"` itself into `REQUIRED_FIELDS` — that's
wrong; `USERNAME_FIELD` is already implicitly required and must never be
repeated in this list.

## 7. Django password hashing

Django never stores a password as plain text. `AUTH_PASSWORD_VALIDATORS`
(already configured in `base.py` since CP1) enforces password *quality*
rules (length, similarity to user attributes, common-password rejection,
not-all-numeric) before a password is accepted. Separately, Django's
`PASSWORD_HASHERS` setting (using sensible defaults we haven't overridden —
PBKDF2 with SHA256, a well-audited, industry-standard algorithm) controls how
the accepted password is *stored*. The stored value looks like:

```
pbkdf2_sha256$<iterations>$<salt>$<hash>
```

Algorithm, iteration count, and salt are all stored alongside the hash so
Django can verify a password later and — if the algorithm is ever
upgraded — automatically re-hash on next successful login. We never invented
our own hashing; that would be a serious, unnecessary security risk. Django's
hashing is exactly what the checkpoint required us to use.

## 8. Why `set_password()` matters

`set_password(raw_password)` is the *only* correct way to set a user's
password. It runs the raw string through the configured hasher and assigns
the result to `self.password` — it does not save the record. If you instead
did `user.password = "hunter2"` directly, you would store the literal
plaintext string in the database, and every future login attempt would fail
(because `check_password()` expects a hash, not plaintext) *and* the raw
password would be sitting in the database and in every backup. `UserManager`
calls `set_password()` inside `_create_user()` for exactly this reason — it's
the one and only path a password ever takes into the database.

## 9. `create_user` vs `create_superuser`

Two different intents, so two different methods, both funneling through the
same private helper:

|                          | `create_user()`                | `create_superuser()`                  |
|--------------------------|---------------------------------|-----------------------------------------|
| Typical caller           | signup / seed script / admin "add user" | `manage.py createsuperuser`, bootstrapping |
| `is_staff` default       | `False`                         | `True` (required)                       |
| `is_superuser` default   | `False`                         | `True` (required)                       |
| Passing `is_staff=True`  | **rejected** (`ValueError`)     | allowed only as `True`                  |
| Passing `is_superuser=True` | **rejected** (`ValueError`)  | allowed only as `True`                  |
| Resulting CRM `role`     | whatever caller passes, default `EMPLOYEE` | forced to `SUPER_ADMIN` (see §10)  |

The rejections are deliberate: `create_user()` must never be a backdoor to
Django admin-site access. If code ever calls
`create_user(..., is_staff=True)` by mistake, it fails loudly instead of
silently creating a normal-looking "employee" who can actually log into
`/admin/`.

## 10. Django `is_staff` vs `is_superuser` vs the CRM `role`

These are **three separate concepts** that are easy to conflate:

- **`is_staff`** — can this user log into the Django admin site at all? (A
  purely Django-admin-UI gate.)
- **`is_superuser`** — does this user bypass Django's permission checks
  entirely? (A purely Django-permission-system concept, relevant mostly to
  `django.contrib.admin` and `PermissionsMixin.has_perm()`.)
- **`role`** (`SUPER_ADMIN` / `MANAGER` / `EMPLOYEE`) — the CRM's *own*
  business-level identity label. This is what CP6's RBAC/data-scope engine
  and CP4's Super Admin access-key flow will actually read. It has nothing to
  do with Django's admin site.

Left alone, these three could disagree in confusing ways — e.g. a Django
superuser who is (per the CRM's own `role` field) merely an `EMPLOYEE`. CP2
establishes one deliberate, simple invariant to prevent that specific
contradiction (see `User.save()`):

```python
if self.is_superuser:
    self.role = self.Role.SUPER_ADMIN
```

This is intentionally **one-directional**. It only ever *promotes* toward
`SUPER_ADMIN`; it never touches `role` for a non-superuser. A `MANAGER` or
`EMPLOYEE` with zero Django admin privileges — the normal case for almost
every real CRM user — is completely unaffected.

## 11. `TextChoices`

`models.TextChoices` is Django's clean, type-safe way to define an
enumerated set of string choices for a field:

```python
class Role(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", _("Super Admin")
    MANAGER = "MANAGER", _("Manager")
    EMPLOYEE = "EMPLOYEE", _("Employee")
```

Compared to a bare list of `(value, label)` tuples, `TextChoices` gives you:

- `User.Role.SUPER_ADMIN` as an importable, IDE-autocompletable constant
  (instead of a "magic string" `"SUPER_ADMIN"` scattered through the
  codebase)
- `.choices` (for the model field), `.values`, `.labels` derived
  automatically
- A real `Enum` under the hood, so comparisons (`user.role == User.Role.MANAGER`)
  are checked, not just string-matched by convention

## 12. `AUTH_USER_MODEL`

A single setting, in `config/settings/base.py`:

```python
AUTH_USER_MODEL = "accounts.User"
```

This is the string `"<app_label>.<ModelName>"` — note it's the app's
**label** (`"accounts"`, set explicitly in `AccountsConfig`), not its full
Python dotted path (`apps.accounts`). It tells every part of Django
(`django.contrib.auth`, the admin site, `ForeignKey(settings.AUTH_USER_MODEL)`
in future apps, migration generation) which model *is* "the" user. It lives
in `base.py`, not duplicated in `development.py`/`production.py`, because
which model represents a user is a project-wide identity decision, true in
every environment — exactly like the reasoning in §4 of the CP1 section for
why shared config belongs in `base.py`.

## 13. `get_user_model()`

Anywhere Django code needs "the current project's user model," it should call:

```python
from django.contrib.auth import get_user_model
User = get_user_model()
```

This resolves `AUTH_USER_MODEL` at *runtime* and returns whatever model is
actually configured — `apps.accounts.User` in our case. We confirmed this
directly in CP2:

```
get_user_model() -> <class 'apps.accounts.models.User'>
```

## 14. Why direct imports of `User` can be problematic

You *could* write `from apps.accounts.models import User` anywhere you need
the user model. The problem: that hard-codes a specific model class into
code that should really mean "whatever `AUTH_USER_MODEL` is." If a future
project (or a future you, refactoring) ever changes which app owns the user
model, every direct import silently breaks or points at the wrong class,
while `get_user_model()`-based code keeps working because it re-resolves the
setting. The same reasoning applies to `ForeignKey`s: prefer
`models.ForeignKey(settings.AUTH_USER_MODEL, ...)` over
`models.ForeignKey(User, ...)` in model definitions, for the same
future-proofing reason. (There is one narrow exception: inside
`accounts/models.py` itself, direct reference is fine and unavoidable — you
have to define the class somewhere.)

## 15. Migration dependency concepts

Every Django migration can declare `dependencies` — other migrations that
must be applied *before* it. Our generated `0001_initial.py` declares:

```python
dependencies = [
    ("auth", "0012_alter_user_first_name_max_length"),
]
```

Why does an `accounts` migration depend on an `auth` migration? Because
`PermissionsMixin` gives our `User` model `groups` and `user_permissions`
fields, which are `ManyToManyField`s pointing at `auth.Group` and
`auth.Permission`. Those tables must exist (i.e. that `auth` migration must
already be applied) before our `User` table's M2M "through" tables can be
created. Django's migration autodetector figured this out and added the
dependency automatically — we didn't write it by hand, but understanding
*why* it's there is the point: migrations form a dependency graph, and
`migrate` applies them in the order that graph requires, not file order.

## 16. Why we delayed the first `migrate` until CP2

Covered in the CP1 section already (§17 there), restated briefly because it's
the single most important CP2 prerequisite: **`AUTH_USER_MODEL` must be set
before the first `migrate`**, because the built-in `auth`/`admin` migrations
create the user table, and once created, its identity is effectively frozen.
CP1 ended with 18 unapplied built-in migrations *specifically* so that CP2
could define `accounts.User`, set `AUTH_USER_MODEL`, generate the `accounts`
migration, and only then let `migrate` run — applying the built-in migrations
and the `accounts` migration together, in the correct dependency order, with
the custom user model already wired in from the very first table Django ever
creates.

## 17. What actually happened when we tried the first `migrate`

This is where CP2 diverges from a "textbook" run: **the first `migrate` was
attempted and failed, for an environment reason, not a code reason.**

This machine has no PostgreSQL server reachable anywhere — no local install,
no Windows service, no Docker, no WSL distribution (all checked directly,
not assumed). Running `manage.py migrate` produced a real
`psycopg.OperationalError` — connection refused on `127.0.0.1:5432` — before
Django could even inspect which migrations were already applied.

Per the project's rules ("never claim a command/test passed unless it was
actually executed", "never introduce a SQLite fallback"), this was **reported
as a blocker**, not worked around. Everything that does *not* require a live
database connection was still completed and verified in CP2:

- `manage.py check` → clean
- `manage.py makemigrations accounts` → generated `0001_initial.py`
- the migration was inspected by hand (see the CP2 section of
  `BACKEND_PROGRESS.md` for exactly what it contains)
- `manage.py makemigrations --check --dry-run` → **No changes detected**
- `get_user_model()` and `settings.DATABASES[...]["ENGINE"]` were both
  confirmed via `django.setup()`, which needs Django's app registry but not a
  live database connection

`migrate` itself, the 15 new model tests (which need pytest-django's
temporary test database), and live HTTP verification via `runserver` all
remain blocked until a real PostgreSQL instance exists. `backend/.env` is
already configured with the coordinates it will connect to
(`crm_db`/`crm_dev`/`localhost:5432`) the moment one is available — no further
code changes are expected to be needed at that point.

## 18. How the custom User relates to future JWT authentication

CP3 will add JWT-based login. None of that exists yet — but the *reason* CP2
had to come first is that JWT authentication needs something to authenticate
*as*. Conceptually, CP3's login flow will be:

```
POST /api/v1/auth/login  (email + password)
    -> UserManager-created User row is looked up by email (USERNAME_FIELD)
    -> check_password() verifies the hash CP2's set_password() produced
    -> a JWT is issued encoding (at minimum) the user's id
    -> later requests carry that JWT; Django resolves it back to this same
       apps.accounts.User row via get_user_model()
```

Every piece CP3 needs — the lookup field, the hashed password, the resolvable
model — was established in CP2. CP2 intentionally stops *before* actually
issuing or verifying a token; that's CP3's job.

## 19. Why RBAC is NOT fully implemented yet

The `role` field is a **label**, not an enforcement mechanism. Nothing in the
codebase yet reads `request.user.role` to decide whether a view should allow
an action or which rows a queryset should return. That's deliberate: building
permission logic before there's anything to protect (no `Lead`, `Customer`,
or other domain model exists yet) would mean designing RBAC in a vacuum,
against imagined requirements instead of real ones. CP6 ("Hierarchy + RBAC")
is scheduled specifically after enough domain models exist to design
permissions against real, concrete data shapes.

## 20. Why hierarchy is NOT fully implemented yet

For the same reason, `User` has **no** `manager_id`, `team_id`,
`assigned_leads`, or permissions-JSON field. Adding those now, before CP6's
hierarchy design, risks guessing wrong about the actual shape needed (does a
`MANAGER` need one team or many? Is hierarchy strictly two levels, or could
it grow deeper?) and then having to migrate away from a bad guess later. CP2
keeps `User` scoped to pure identity; CP6 is where hierarchy relationships
are designed deliberately, with the full picture available.

## 21. Security lessons from CP2

- **Never invent cryptography.** `set_password()`/`check_password()` and
  Django's hasher configuration were used exactly as-is — no custom hashing
  scheme was written.
- **Case-insensitive email uniqueness needs a real answer, not an assumption.**
  A plain `unique=True` on `EmailField` is case-*sensitive* at the database
  level. We normalize email to lowercase in two independent places
  (`UserManager._create_user()` and `User.save()`) *and* enforce it at the
  database layer with `models.UniqueConstraint(Lower("email"))` — so the
  guarantee holds even if some future code path bypassed the normalization.
- **A manager should refuse contradictory input, not "fix" it silently.**
  `create_user()` raising on `is_staff=True`/`is_superuser=True`, and
  `create_superuser()` raising on an explicit `False` for either, means
  programmer mistakes fail immediately and loudly at the call site — not
  quietly, three checkpoints later, as a mysterious permissions bug.
- **`.env` stays out of every document and every command's echoed output.**
  This guide, `BACKEND_PROGRESS.md`, and every command run during CP2 avoided
  printing `.env`'s contents; only its *existence* and which keys it defines
  are ever mentioned.
- **No premature secrets.** No Super Admin access-code field, no JWT secret
  handling, no session/device token — none of that belongs on `User` yet, and
  none was added, even though it will obviously exist soon.

## 22. Tests introduced in CP2

`apps/accounts/tests/test_user_model.py` — 15 tests, all `@pytest.mark.django_db`
(meaning they need a real database, which is why all 15 currently error rather
than pass or fail — see §17 and §24):

1. `test_create_user_with_valid_email` — a normal user is created with sane
   defaults (`is_active=True`, `is_staff=False`, `role=EMPLOYEE`)
2. `test_email_is_normalized_to_lowercase` — mixed-case email is stored
   lowercase
3. `test_password_is_hashed_not_stored_raw` — stored value differs from the
   raw password, uses `pbkdf2_sha256$`, and `check_password()` round-trips
   correctly
4. `test_duplicate_email_rejected` — a second user with the same email raises
   `IntegrityError`
5. `test_duplicate_email_rejected_case_insensitively` — same, but with a
   differently-cased duplicate (`DUP2@EXAMPLE.COM` vs `dup2@example.com`) —
   proves the `Lower(email)` constraint actually does its job
6. `test_create_user_without_email_rejected` — blank email raises `ValueError`
7. `test_create_superuser` — results in `is_staff=True`, `is_superuser=True`,
   and `role=SUPER_ADMIN` (the invariant from §10)
8. `test_create_superuser_rejects_is_staff_false` — explicit `False` is
   rejected, not silently overridden
9. `test_create_superuser_rejects_is_superuser_false` — same, for
   `is_superuser`
10. `test_create_user_rejects_is_superuser_true` — `create_user()` cannot be
    used as a superuser backdoor
11. `test_create_user_rejects_is_staff_true` — same, for `is_staff`
12. `test_username_field_is_email` — `USERNAME_FIELD == "email"`,
    `REQUIRED_FIELDS == []`
13. `test_default_role_for_normal_user_is_employee` — the default role
    assertion the checkpoint explicitly asked for
14. `test_role_can_be_set_to_manager_or_super_admin_without_django_privileges`
    — proves `role` is independent from `is_staff`/`is_superuser` for
    non-superusers
15. `test_str_returns_email` — `__str__` returns the email, useful in the
    admin site and shell debugging

The original 3 CP1 infrastructure tests (`tests/test_infrastructure.py`) were
re-run unchanged alongside these and remain green — see §23.

## 23. Commands actually executed and their actual results

Every command below was actually run in this environment during CP2 (none of
this is assumed or predicted):

```
python -m venv .venv                         -> created (Python 3.13.7)
pip install -r requirements.txt               -> all pinned versions installed successfully

manage.py check
    System check identified no issues (0 silenced).

manage.py makemigrations accounts
    Migrations for 'accounts':
      apps\accounts\migrations\0001_initial.py
        + Create model User
    (RuntimeWarning: could not check migration-history consistency against
    the DB — expected with no PostgreSQL reachable; does not block file
    generation)

manage.py makemigrations --check --dry-run
    No changes detected

manage.py migrate
    django.db.utils.OperationalError: connection failed: connection to
    server at "127.0.0.1", port 5432 failed: could not receive data from
    server: Socket is not connected (0x00002749/10057)
    -> FAILED (blocked on missing PostgreSQL, not a code defect)

manage.py runserver 8010
    Same OperationalError during runserver's own startup
    check_migrations() step.
    -> live HTTP verification of /health, /api/schema/, /api/docs/ against
       a running server was not possible; the pytest-based check of the
       same 3 endpoints (below) is the available substitute evidence.

pytest -v
    3 passed   (tests/test_infrastructure.py — unchanged CP1 tests)
    15 errors  (apps/accounts/tests/test_user_model.py — all erroring at
                pytest-django's test-database creation step; zero due to
                assertion failures)

python -c "django.setup(); get_user_model()"
    <class 'apps.accounts.models.User'>
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    Role.choices = [('SUPER_ADMIN', 'Super Admin'), ('MANAGER', 'Manager'),
                     ('EMPLOYEE', 'Employee')]

python -c "django.setup(); settings.DATABASES['default']"
    ENGINE: django.db.backends.postgresql
    NAME:   crm_db
    HOST:   localhost
```

## 24. Problems encountered and how they were fixed

**Problem:** No PostgreSQL server exists anywhere on this machine (checked:
no `psql`, no Windows `postgresql*` service, no `docker` command, no WSL
distribution).

**How it was handled:** This is an *environment* problem, not a *code*
problem, and the project's rules are explicit that migration failures must be
diagnosed and reported rather than bypassed (no SQLite fallback; no faking
success). The user was asked directly how to proceed before any further work,
with three options: install PostgreSQL system-wide via `winget`, point at an
existing instance, or complete every non-DB-dependent step now and report the
rest as blocked. **The chosen option was the third.** As a direct result:

- Everything achievable without a live database connection was completed and
  actually verified (see §17, §23): the app, model, manager, admin
  registration, `AUTH_USER_MODEL`, the generated + inspected migration, and
  the `makemigrations --check --dry-run` clean result.
- `migrate`, the 15 new tests, and live-server HTTP verification are recorded
  as **blocked**, not passing — this checkpoint's status is **PARTIAL /
  BLOCKED**, not COMPLETE, exactly per the "Mandatory Checkpoint Protocol"
  rule in `BACKEND_PROGRESS.md`: *"If a checkpoint fails midway, record it as
  PARTIAL/BLOCKED instead of COMPLETE."*
- `backend/.env` was created (values never printed or committed) with the
  coordinates a local PostgreSQL instance would need
  (`crm_db`/`crm_dev`/`localhost:5432`), so no further configuration is
  needed once PostgreSQL exists — only running the already-verified
  `migrate` → `pytest` → runtime-check sequence.

A secondary, smaller issue: the venv was initially created with the system's
default Python (3.14.0), which is newer than Django 5.1.4's officially
supported range and newer than published `psycopg[binary]` wheels for at the
time of this checkpoint. It was recreated with Python 3.13.7 (also available
on this machine) before installing dependencies, avoiding a class of
"technically installs but unsupported" problems before they could occur.

---

## What I Should Understand Before CP3

CP3 introduces authentication/JWT — the first checkpoint where a request will
actually *prove* who it's from. Before starting it, be able to explain, in
your own words:

1. **How login will work end-to-end**, conceptually: email/password in ->
   `UserManager`/`check_password()` verifies it -> a token is issued ->
   later requests present that token -> Django resolves it back to a
   specific `apps.accounts.User` row. (§18 above.)
2. **Why `USERNAME_FIELD = "email"` matters for CP3** — it's the field
   Django's authentication backend will look the user up by.
3. **The difference between authentication and authorization** — CP3
   (JWT) answers *"who is this?"*; CP6 (RBAC) later answers *"what are they
   allowed to do?"*. CP2's `role` field is a label CP6 will read, not an
   enforcer itself.
4. **Why passwords are never compared as plaintext** — `check_password()`
   re-hashes the attempt with the stored salt/algorithm and compares hashes,
   never raw strings. (§7–§8.)
5. **What a JWT is, at a conceptual level** — a signed token that encodes
   claims (at minimum, which user), which the server can verify without a
   database round-trip on every single request, versus a traditional session
   cookie which requires a server-side session lookup. You do not need the
   exact library/implementation yet — just the shape of the problem CP3
   solves.
6. **Why the Super Admin access key (CP4) comes *after* basic auth
   (CP3), not instead of it** — the intended flow is `email/password` first,
   *then*, only if `role == SUPER_ADMIN`, an additional secret/access-key
   verification step, before a final session/token is issued. CP3 builds the
   first half of that chain; CP4 adds the second half on top.
7. **That CP2 is not finished** — before treating CP2 as a solved
   prerequisite, remember `migrate` and the 15 new tests are still blocked
   pending a real PostgreSQL instance. CP3 should not begin in this
   environment until that is resolved, per the project's Mandatory
   Checkpoint Protocol.

**Viva-style questions to test yourself:**

- Why does `create_user()` refuse `is_staff=True` instead of just ignoring
  the argument?
- What would happen to existing data if you changed `AUTH_USER_MODEL` after
  running `migrate` once?
- Why is `role` on `User` *not* the same thing as Django's `is_superuser`?
- Why does the `accounts` migration depend on an `auth` migration, given that
  `accounts.User` doesn't obviously "use" anything from `auth`?
- What's the difference between a migration *failing to generate* and a
  migration *failing to apply* — which one happened in CP2, and why does
  that distinction matter?
- Why is a `UniqueConstraint(Lower("email"))` more correct than relying on
  `unique=True` alone, given that the code already lowercases every email
  before saving?

---

*End of CP2. This guide will be extended at each subsequent checkpoint.*
