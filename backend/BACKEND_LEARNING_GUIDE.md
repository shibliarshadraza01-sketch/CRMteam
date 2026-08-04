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

# Checkpoint 3 (CP3): Authentication + JWT

CP2 gave the CRM an identity — a `User` who can exist, with a hashed
password and a role. CP3 gives it a **way to prove that identity over
HTTP**: login, a token to carry on every subsequent request, a way to renew
that token without asking for the password again, and a way to log out.
Nothing about *what a role is allowed to do* is here yet — that's CP6. CP3 is
purely "who is this request from, and how do we know."

## Table of Contents (CP3)

1. What was built, in one paragraph
2. Authentication vs. authorization
3. What a JWT actually is
4. Access token vs. refresh token
5. The token lifecycle, end to end
6. Why these specific token lifetimes
7. Refresh-token rotation and blacklisting
8. `djangorestframework-simplejwt`, and why we didn't hand-roll JWT
9. `JWTAuthentication`
10. Serializers as the validation/business-logic boundary
11. The three CP3 serializers, in detail
12. The three CP3 views, in detail
13. Password verification — `authenticate()`, not manual hash comparison
14. Why `USERNAME_FIELD` has to match the `authenticate()` keyword
15. Not revealing account existence
16. Why inactive users are rejected "for free"
17. `permission_classes` vs `authentication_classes`
18. `DEFAULT_PERMISSION_CLASSES` stayed `AllowAny` — why that's still correct
19. drf-spectacular + SimpleJWT: automatic Bearer-scheme documentation
20. Testing strategy for CP3
21. API request/response examples
22. Important files/classes/functions (quick index)
23. Mistakes/pitfalls this checkpoint deliberately avoided
24. Super Admin note — what CP3 is *not*
25. What actually happened when we ran the verification sequence
26. What I should understand before CP4

---

## 1. What was built, in one paragraph

Four endpoints under `/api/v1/auth/`: `POST /login/` (email+password in,
access+refresh+safe-user-info out), `POST /refresh/` (a valid refresh token
in, a new access token — and, because rotation is on, a new refresh token —
out), `POST /logout/` (a refresh token in, blacklisted so it can never be
used again), and `GET /me/` (a valid access token in the `Authorization`
header, the caller's own safe identity info out). Token issuing/verification
is handled entirely by `djangorestframework-simplejwt`; password checking is
handled entirely by Django's own `authenticate()`. No cryptography, hashing,
or token-signing code was written by hand.

## 2. Authentication vs. authorization

These two words get used almost interchangeably in casual conversation, but
they're answering completely different questions, and CP3/CP6 deliberately
split them:

- **Authentication** ("who are you?") — CP3. Verifying a password, issuing a
  token, verifying that token on later requests. The *answer* is a `User`
  object attached to `request.user`.
- **Authorization** ("what are you allowed to do?") — CP6. Given a known,
  authenticated `User` (with a `role`, and eventually a team/hierarchy
  position), deciding whether *this specific request* should be allowed, and
  which rows a queryset should even return.

CP3 answers the first question and stops. `request.user.role` already exists
(from CP2) and CP3's `/me/` even *returns* it to the client — but nothing in
CP3 branches on it to allow or deny an action. That's intentional: there is
no domain data yet (no `Lead`, no `Customer`) for authorization rules to
protect.

## 3. What a JWT actually is

**JWT (JSON Web Token)** is a compact, URL-safe string with three
dot-separated, base64url-encoded parts:

```
<header>.<payload>.<signature>
```

- **Header** — which algorithm signed it (SimpleJWT defaults to HS256, HMAC
  with SHA-256, using `SECRET_KEY` as the shared secret).
- **Payload** — the **claims**: plain, *readable* (not encrypted!) JSON, e.g.
  `{"user_id": 7, "token_type": "access", "exp": 1234567890, ...}`. Anyone
  who has the token can decode and read this — a JWT hides nothing, it only
  *proves* it wasn't tampered with.
- **Signature** — `HMAC-SHA256(header + "." + payload, SECRET_KEY)`. The
  server recomputes this on every request; if it doesn't match, the token is
  rejected. This is what makes a JWT trustworthy without a database lookup:
  if you have `SECRET_KEY`, you can verify the signature is authentic, and
  therefore trust the claims inside, **without querying the database on
  every request** (contrast with a traditional session, which requires a
  server-side session-store lookup on every request).

The practical consequence for this CRM: an access token proves "the server
issued this to user 7, and it hasn't been tampered with, and it hasn't
expired" — all verifiable from the token alone.

## 4. Access token vs. refresh token

SimpleJWT issues **two** tokens on login, with different purposes and
different claims (`token_type: "access"` vs. `token_type: "refresh"` —
that's what stops one from being used as the other, see §17 of the CP2
section's cousin discussion, and the test
`test_refresh_token_rejected_by_protected_endpoint`):

| | Access token | Refresh token |
|---|---|---|
| Sent on | every authenticated API request (`Authorization: Bearer ...`) | only to `/api/v1/auth/refresh/` and `/api/v1/auth/logout/` |
| Lifetime here | 15 minutes | 7 days |
| Purpose | prove identity for this one request | obtain a new access token without re-entering a password |
| If stolen | usable for at most 15 minutes | usable to keep generating access tokens — much higher value target, hence the shorter *exposure surface* (sent far less often) and the rotation/blacklist protection in §7 |

## 5. The token lifecycle, end to end

```
1. POST /api/v1/auth/login/  {email, password}
       -> authenticate() verifies the password
       -> RefreshToken.for_user(user) mints BOTH tokens
       -> response: {access, refresh, user}

2. Client stores both tokens (frontend's concern, out of CP3's scope) and
   sends the access token on every subsequent request:
       Authorization: Bearer <access>

3. GET /api/v1/auth/me/  (Authorization: Bearer <access>)
       -> JWTAuthentication verifies the signature + expiry + token_type
       -> request.user is set to the matching User
       -> IsAuthenticated permission passes
       -> UserSerializer(request.user).data returned

4. Access token expires after 15 minutes. Client calls:
   POST /api/v1/auth/refresh/  {refresh}
       -> SimpleJWT's TokenRefreshView verifies the refresh token
       -> issues a brand-new access token
       -> (ROTATE_REFRESH_TOKENS=True) also issues a brand-new refresh token
          and blacklists the one that was just used
       -> response: {access, refresh}

5. POST /api/v1/auth/logout/  {refresh}
       -> the current refresh token is blacklisted immediately
       -> it can never again be exchanged for an access token, even though
          it hasn't hit its natural 7-day expiry
```

## 6. Why these specific token lifetimes

```python
"ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
"REFRESH_TOKEN_LIFETIME": timedelta(days=7),
```

This is a deliberate trade-off, not an arbitrary number:

- **15-minute access tokens** minimize the *damage window* if one leaks
  (browser XSS, a misconfigured log, a proxy that shouldn't have seen it) —
  it self-expires quickly, and it's sent on every request, so it's the token
  most exposed to interception.
- **7-day refresh tokens** avoid forcing a CRM user to re-type their
  password every 15 minutes (bad UX for an internal business tool people use
  all day, every workday), while still expiring on its own within a week if
  truly abandoned, and being individually revocable via blacklist (logout, or
  a future "log out this device" feature) well before that.
- These are reasonable **starting** values for CP3, not a claim that they're
  final/tuned for production — a real deployment might shorten the refresh
  lifetime once CP5 (device authorization) exists, since that checkpoint adds
  a complementary revocation mechanism.

## 7. Refresh-token rotation and blacklisting

```python
"ROTATE_REFRESH_TOKENS": True,
"BLACKLIST_AFTER_ROTATION": True,
```

Without rotation, a single refresh token would remain valid and reusable for
its entire 7-day lifetime — if it leaked once, it would work for an attacker
for up to a week, indistinguishably from the legitimate client. With
rotation:

- Every `/refresh/` call issues a **new** refresh token and immediately
  blacklists the one that was just spent (`BLACKLIST_AFTER_ROTATION`).
- A refresh token is therefore **single-use**. `test_rotated_refresh_token_cannot_be_reused`
  proves this directly: refreshing once succeeds; refreshing again with the
  *same original* token fails with 401.
- This also gives a **theft-detection signal** for free: if an attacker ever
  steals a refresh token and uses it, the legitimate client's *next* refresh
  attempt (with the now-superseded token) will fail — an anomaly a real
  deployment could alert on. CP3 doesn't build that alerting (no audit
  system yet — that's CP12), but the mechanism that makes it *possible*
  exists starting now.
- Blacklisting is implemented by SimpleJWT's own `token_blacklist` Django
  app (`OutstandingToken`/`BlacklistedToken` tables) — added to
  `INSTALLED_APPS`, not hand-built.

## 8. `djangorestframework-simplejwt`, and why we didn't hand-roll JWT

Writing your own JWT signing/verification code means re-implementing a
security-critical primitive (constant-time signature comparison, correct
expiry handling, algorithm confusion prevention) that a widely-used,
security-reviewed library already solves. `djangorestframework-simplejwt`
is the standard DRF-ecosystem choice: it integrates with DRF's
`authentication_classes`, understands Django's `User` model out of the box,
and ships the blacklist app CP3 needed for logout. Every checkpoint so far
has followed the same principle (Django's password hashing in CP2, now
SimpleJWT's token handling in CP3): **don't invent cryptography.**

## 9. `JWTAuthentication`

```python
"DEFAULT_AUTHENTICATION_CLASSES": [
    "rest_framework_simplejwt.authentication.JWTAuthentication",
],
```

This is a DRF **authentication class** — code that runs on *every* request
and tries to answer "who sent this?" by inspecting the `Authorization`
header. If it finds `Bearer <token>`, it verifies the signature and expiry
(via SimpleJWT), confirms `token_type == "access"`, looks up the user by the
`user_id` claim, and sets `request.user`. If there's no header, or the token
is invalid/expired/wrong-type, it either sets `request.user` to
`AnonymousUser` (no header at all) or raises `AuthenticationFailed` (a
header was present but invalid) — DRF then applies the view's
`permission_classes` to decide whether that's actually a problem for *this*
endpoint. This is why `/login/` (no header expected) and `/me/` (header
required) can share the same global authentication class but behave
completely differently — the difference is each view's `permission_classes`
(§17).

## 10. Serializers as the validation/business-logic boundary

CP1's learning guide already introduced serializers as "the contract for
what a request may send and what a response will contain." CP3 leans on that
harder: `LoginSerializer.validate()` doesn't just check that `email` looks
like an email — it actually **performs the authentication** and attaches the
resolved `User` to `validated_data`. This keeps the *view* trivial (get
serializer, validate, use `validated_data["user"]`) and keeps all the
"what makes a login request valid" logic in exactly one place, testable in
isolation from HTTP concerns.

## 11. The three CP3 serializers, in detail

**`UserSerializer`** (`ModelSerializer`) — the *only* shape of `User` ever
sent to a client:

```python
class Meta:
    model = User
    fields = ["id", "email", "first_name", "last_name", "role"]
    read_only_fields = fields
```

An explicit **allowlist** (`fields = [...]`), not `exclude = [...]` — see
§23 for why that distinction matters.

**`LoginSerializer`** (plain `Serializer`, not a `ModelSerializer` — it
doesn't map 1:1 to a model, it maps to a *request shape*):

```python
email = serializers.EmailField()
password = serializers.CharField(write_only=True, trim_whitespace=False)

def validate(self, attrs):
    user = authenticate(request=self.context.get("request"),
                         email=attrs["email"], password=attrs["password"])
    if user is None:
        raise AuthenticationFailed("Invalid email or password.")
    attrs["user"] = user
    return attrs
```

`trim_whitespace=False` on the password field is deliberate — DRF's
`CharField` strips leading/trailing whitespace by default, which is exactly
wrong for a password (a password of `" secret "` should not silently become
`"secret"`). `AuthenticationFailed` (not `ValidationError`) is raised on bad
credentials specifically so DRF returns **401**, not the 400 a normal field
validation error would produce — status code correctness matters for a
frontend deciding how to react.

**`LogoutSerializer`**:

```python
refresh = serializers.CharField(write_only=True)

def validate_refresh(self, value):
    try:
        token = RefreshToken(value)
    except TokenError as exc:
        raise serializers.ValidationError(str(exc)) from exc
    self._token = token
    return value

def save(self, **kwargs):
    self._token.blacklist()
```

`RefreshToken(value)` parses *and verifies* the token (signature, expiry,
type) — `TokenError` covers malformed, expired, and already-blacklisted
tokens uniformly, all correctly surfaced as **400** (a client error: "this
token isn't usable"), distinct from `/me/`'s 401 ("you're not
authenticated") — different endpoints, different failure semantics.

## 12. The three CP3 views, in detail

```python
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
```

`authentication_classes = []` on `LoginView`/`LogoutView` is a small but
deliberate choice: these endpoints don't need DRF to even *attempt* reading
an `Authorization` header (there usually isn't a valid one yet — that's the
whole point of logging in), so skipping that step avoids any chance of it
interfering with an unrelated, possibly stale header a client might send.

`MeView` is a `RetrieveAPIView` with `get_object()` overridden to return
`self.request.user` — there's no lookup-by-URL-parameter; "retrieve *me*"
always means "retrieve whoever the token resolved to."

`/refresh/` has **no CP3 view at all** — `apps/accounts/urls.py` points it
directly at `rest_framework_simplejwt.views.TokenRefreshView`. See §8's
principle applied again: SimpleJWT's own view already does exactly what
STEP 5 required.

## 13. Password verification — `authenticate()`, not manual hash comparison

```python
user = authenticate(request=request, email=email, password=password)
```

`django.contrib.auth.authenticate()` runs through each backend listed in
`AUTHENTICATION_BACKENDS` (just the default `ModelBackend` here) and asks it
to verify the credentials. `ModelBackend.authenticate()`:

1. Looks up the user by `USERNAME_FIELD` (`email`).
2. Calls `user.check_password(raw_password)` — which re-hashes the raw
   password with the *same* algorithm/salt stored on the user and compares
   the two hashes (never comparing raw strings, and using a
   constant-time comparison internally to resist timing attacks).
3. Calls `user.is_active` via `user_can_authenticate()` — an inactive user
   fails here, *before* `authenticate()` ever returns a user object.

CP3 never calls `check_password()` or touches `user.password` directly —
`authenticate()` is the single, correct entry point, exactly as CP2's
learning guide anticipated in "How the custom User relates to future JWT
authentication."

## 14. Why `USERNAME_FIELD` has to match the `authenticate()` keyword

```python
authenticate(request=request, email=attrs["email"], password=attrs["password"])
```

This looks like it's passing an `email` keyword, but `ModelBackend`'s real
signature is `authenticate(self, request, username=None, password=None,
**kwargs)`. Internally, if `username` is `None`, it does:

```python
username = kwargs.get(UserModel.USERNAME_FIELD)
```

Since `User.USERNAME_FIELD == "email"` (CP2), `kwargs.get("email")`
correctly retrieves the value we passed as `email=...`. This is *why* CP2's
`USERNAME_FIELD` choice directly determines what keyword CP3's login code
must use — if a future model ever used a different `USERNAME_FIELD`, this
call site would need to change too. Passing `username=email` would also have
worked here (`ModelBackend` would then skip the `kwargs.get(...)` fallback
entirely) — using `email=` instead is simply clearer to read, given this
project's actual login identity.

## 15. Not revealing account existence

`test_login_error_message_does_not_reveal_which_field_was_wrong` asserts a
wrong password and a nonexistent email produce **byte-for-byte identical**
401 responses. This matters because if "wrong password" and "no such
account" returned different messages, an attacker could enumerate valid
email addresses in this CRM one guess at a time — a real information leak
that costs nothing to avoid, since `authenticate()` already returns the same
`None` for both cases and CP3 raises the same generic error either way.

## 16. Why inactive users are rejected "for free"

`CustomUserManager`/`User` didn't need any new CP3 code to enforce "inactive
users cannot authenticate" — `ModelBackend.user_can_authenticate()` already
checks `is_active` before returning a user, so `authenticate()` simply
returns `None` for an inactive account, which `LoginSerializer` already
treats as invalid credentials. This is the payoff of building on Django's
real auth machinery instead of a hand-rolled check: the behavior we wanted
was already there.

## 17. `permission_classes` vs `authentication_classes`

Two different DRF concepts that are easy to conflate:

- **`authentication_classes`** — *how* to identify who's making the request
  (inspect a header, verify a token, resolve `request.user`). Can result in
  `AnonymousUser` with no error, if no credentials were presented at all.
- **`permission_classes`** — given whoever `authentication_classes` resolved
  (even `AnonymousUser`), *should this specific request be allowed?*
  `IsAuthenticated` says "no, unless `request.user` is a real, authenticated
  user." `AllowAny` says "yes, regardless."

`MeView` needs both defaults (`JWTAuthentication` to resolve the user) *and*
an explicit `IsAuthenticated` (to actually reject anonymous requests) —
without the permission class, an anonymous request would still be allowed
through and would crash trying to serialize `AnonymousUser` as a `User`.

## 18. `DEFAULT_PERMISSION_CLASSES` stayed `AllowAny` — why that's still correct

It would be tempting to flip the *global* default to `IsAuthenticated` now
that real authentication exists. CP3 deliberately did not do that:

- `/health`, `/api/schema/`, `/api/docs/` (CP1) must stay public — a
  monitoring probe or a new developer's first `curl` shouldn't need a
  token.
- `/login/`, `/refresh/`, `/logout/` (CP3 itself) must stay public — you
  cannot require a token to *obtain* a token.

So `AllowAny` remains the sane default, and `/me/` opts into
`IsAuthenticated` **on itself**. When CP6 introduces protected domain
endpoints (leads, customers, ...), *that* is the natural point to reconsider
whether the global default should flip — a decision explicitly left to that
checkpoint rather than made prematurely here.

## 19. drf-spectacular + SimpleJWT: automatic Bearer-scheme documentation

No extra configuration was added for this — and that was verified, not
assumed. drf-spectacular ships built-in "contrib" support for common
libraries (including SimpleJWT) that auto-registers the moment the library
is importable. Generating the schema
(`manage.py spectacular --file ...`) and inspecting it directly showed:

```yaml
components:
  securitySchemes:
    jwtAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

and each path correctly annotated — `/api/v1/auth/me/` has `security: -
jwtAuth: []`, while `/login/`, `/refresh/`, `/logout/` have `security: - {}`
(no auth required). Swagger UI (`/api/docs/`) will render this as an
"Authorize" button that lets a developer paste an access token and try
`/me/` interactively.

## 20. Testing strategy for CP3

`apps/accounts/tests/test_auth.py` follows the same shape as CP2's tests
(`pytest.mark.django_db`, DRF's `APIClient`, no mocking of Django/SimpleJWT
internals — real password hashing, real token issuance, real blacklist
writes). The organization mirrors the checkpoint's own STEP 12 requirements:
one block per endpoint (login / refresh / `/me/` / logout), plus a
role-parametrized block proving the identical flow works for `EMPLOYEE`,
`MANAGER`, and `SUPER_ADMIN` alike. Where a test needs a *sequence*
(login -> logout -> attempt refresh with the now-blacklisted token), the
test performs the real sequence through real endpoints rather than
constructing tokens by hand — this exercises the actual code path a real
client would hit, not just the unit in isolation.

## 21. API request/response examples

**Login — success:**

```
POST /api/v1/auth/login/
{"email": "employee@example.com", "password": "correct-password"}

200 OK
{
  "access": "eyJhbGciOi...",
  "refresh": "eyJhbGciOi...",
  "user": {
    "id": 7,
    "email": "employee@example.com",
    "first_name": "",
    "last_name": "",
    "role": "EMPLOYEE"
  }
}
```

**Login — invalid credentials (wrong password OR unknown email OR inactive
user — identical either way):**

```
POST /api/v1/auth/login/
{"email": "employee@example.com", "password": "wrong"}

401 Unauthorized
{"detail": "Invalid email or password."}
```

**Refresh — success (rotation enabled, so a new refresh token comes back
too):**

```
POST /api/v1/auth/refresh/
{"refresh": "eyJhbGciOi..."}

200 OK
{"access": "eyJhbGciOi...", "refresh": "eyJhbGciOi..."}
```

**`/me/` — success:**

```
GET /api/v1/auth/me/
Authorization: Bearer eyJhbGciOi...

200 OK
{"id": 7, "email": "employee@example.com", "first_name": "", "last_name": "", "role": "EMPLOYEE"}
```

**`/me/` — no/invalid token:**

```
GET /api/v1/auth/me/
(no Authorization header, or an invalid/expired one)

401 Unauthorized
{"detail": "Authentication credentials were not provided."}
```

**Logout:**

```
POST /api/v1/auth/logout/
{"refresh": "eyJhbGciOi..."}

200 OK
{"detail": "Successfully logged out."}
```

## 22. Important files/classes/functions (quick index)

| File | Contains |
|---|---|
| `apps/accounts/serializers.py` | `UserSerializer`, `LoginSerializer`, `LogoutSerializer` |
| `apps/accounts/views.py` | `LoginView`, `MeView`, `LogoutView` |
| `apps/accounts/urls.py` | the 4 routes; wires SimpleJWT's `TokenRefreshView` for `/refresh/` |
| `config/urls.py` | mounts `apps.accounts.urls` at `/api/v1/auth/` |
| `config/settings/base.py` | `SIMPLE_JWT` block, `JWTAuthentication` in `DEFAULT_AUTHENTICATION_CLASSES`, `token_blacklist` in `INSTALLED_APPS` |
| `apps/accounts/tests/test_auth.py` | all 28 CP3 tests |
| (reused, not modified) `apps/accounts/models.py` / `managers.py` | CP2's `User` / `UserManager` — unchanged |

## 23. Mistakes/pitfalls this checkpoint deliberately avoided

- **Comparing passwords manually** (`if user.password == hashlib.sha256(...)`)
  — never done; `authenticate()`/`check_password()` only.
- **`exclude`-based serializer instead of an allowlist** — `UserSerializer`
  uses `fields = [...]`, so a future field added to `User` (say, a CP4
  access-code hash) is *safe by default*, not accidentally exposed until
  someone remembers to add it to an exclude list.
- **Different error messages for "no such user" vs. "wrong password"** — one
  identical message for both (§15).
- **Trusting a refresh token as if it were an access token** — SimpleJWT's
  `token_type` claim check prevents this, and it's explicitly tested
  (`test_refresh_token_rejected_by_protected_endpoint`).
- **Reusable refresh tokens** — rotation + blacklist-after-rotation makes
  each refresh token single-use (§7).
- **Flipping `DEFAULT_PERMISSION_CLASSES` to `IsAuthenticated` globally** —
  would have broken `/health` and even `/login/` itself; left as `AllowAny`
  with `/me/` opting in individually (§18).
- **Hardcoding the JWT signing secret** — `SIMPLE_JWT` has no `SIGNING_KEY`
  entry at all; it defaults to `SECRET_KEY`, which was already
  environment-sourced since CP1.
- **Logging request bodies containing passwords** — no logging was added in
  CP3 that would capture `request.data`; Django's default logging doesn't
  log request bodies.
- **Generating a migration for `token_blacklist`** — its migrations already
  ship inside the installed package; running `makemigrations` for it would
  have been both wrong and unnecessary (confirmed: `--check --dry-run`
  reports "No changes detected").

## 24. Super Admin note — what CP3 is *not*

CP2 already gave `User` a `role` field including `SUPER_ADMIN`. CP3's login
endpoint treats a `SUPER_ADMIN` **identically** to an `EMPLOYEE` or
`MANAGER` — same serializer, same `authenticate()` call, same token
issuance. This is intentional and matches the checkpoint's instructions
precisely: the eventual production flow is

```
email/password (CP3, done)
    -> if role == SUPER_ADMIN
        -> additional secret/access-key verification (CP4, NOT built yet)
    -> final authenticated session/token
```

CP3 is only the first half of that chain for every role, `SUPER_ADMIN`
included. `test_login_works_for_every_role[SUPER_ADMIN]` proves the base
flow works for that role too — it does **not** claim, and must not be read
as claiming, that CP3 alone is a complete/secure Super Admin login. No
access-code field, challenge endpoint, or intermediate "pending
verification" state was added to `User` or anywhere else in CP3.

## 25. What actually happened when we ran the verification sequence

Same honest pattern as CP2 (see that section's §17 for the original
explanation of *why* this is how CP2/CP3 report results): every command
below was actually executed.

```
manage.py check
    System check identified no issues (0 silenced).

manage.py makemigrations --check --dry-run
    No changes detected

manage.py migrate
    django.db.utils.OperationalError: connection failed: connection to
    server at "127.0.0.1", port 5432 ...
    -> BLOCKED (no PostgreSQL reachable — identical cause as CP2)

manage.py spectacular --file <schema>
    succeeded; schema inspected directly and confirmed to contain all 4
    CP3 routes, correct security annotations, and the auto-registered
    jwtAuth Bearer scheme

pytest -v
    3 passed   <- CP1 infrastructure tests, unchanged
    43 errors  <- 28 new CP3 tests + 15 CP2 tests, all erroring at
                  pytest-django's test-database creation step (the same
                  OperationalError as migrate) — zero assertion failures

get_user_model() / settings checks (via django.setup(), no DB needed)
    <class 'apps.accounts.models.User'>
    DB engine: django.db.backends.postgresql
    DEFAULT_AUTHENTICATION_CLASSES: ['rest_framework_simplejwt.authentication.JWTAuthentication']
    SIMPLE_JWT access lifetime: 0:15:00, refresh lifetime: 7 days
```

`migrate` and the 28 CP3 tests remain the only incomplete items, blocked on
PostgreSQL exactly as CP2 already was — not a new problem CP3 introduced.

## 26. What I should understand before CP4

CP4 adds the Super Admin secondary access-code challenge — a step that sits
*between* CP3's login and final token issuance, specifically for
`SUPER_ADMIN`. Before starting it, be able to explain:

1. **Where CP4 slots into the CP3 flow** — after `authenticate()` succeeds
   and the role is checked to be `SUPER_ADMIN`, *before* `RefreshToken.for_user()`
   is called. CP3's `LoginView` will need to branch here.
2. **Why this is a second factor, not a replacement** — the base
   email/password step still has to succeed first; CP4 adds an additional
   requirement on top for one specific role, it doesn't create an alternate
   login path.
3. **The likely shape of an "in-progress" login** — a `SUPER_ADMIN` who has
   passed step one but not step two is not yet "logged in." CP4 will need to
   decide how that intermediate state is represented (a short-lived,
   narrowly-scoped token? a server-side pending record?) without
   accidentally granting a real access token before the second factor
   succeeds. This wasn't decided in CP3 - it's CP4's design job.
4. **That CP2/CP3 remain PARTIAL** — `migrate` and every DB-backed test are
   still blocked. Per the Mandatory Checkpoint Protocol, CP4 should not
   truly begin (beyond whatever the user explicitly authorizes) until
   PostgreSQL is available and CP2+CP3's remaining steps actually pass.

**Viva-style questions to test yourself:**

- Why can a stolen access token only be used for at most 15 minutes, but a
  stolen *refresh* token could be more dangerous even though it's used far
  less often?
- What specifically stops a client from sending a refresh token in the
  `Authorization: Bearer` header to access `/me/`?
- Why does `LoginSerializer` raise `AuthenticationFailed` instead of
  `ValidationError` for bad credentials — what HTTP status does each
  produce, and why does that distinction matter to a frontend?
- If `UserSerializer` used `exclude = ["password"]` instead of an explicit
  `fields = [...]` allowlist, what could go wrong the day CP4 adds a new
  field to `User`?
- Why does logging out only blacklist the *refresh* token, and not somehow
  "cancel" the access token that's still technically valid for a few more
  minutes? Is that a problem, and if so, how does the short access-token
  lifetime limit it?

---

*End of CP3. This guide will be extended at each subsequent checkpoint.*
