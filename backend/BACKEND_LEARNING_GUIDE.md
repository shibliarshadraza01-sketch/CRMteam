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

*End of CP1. This guide will be extended at each subsequent checkpoint.*
