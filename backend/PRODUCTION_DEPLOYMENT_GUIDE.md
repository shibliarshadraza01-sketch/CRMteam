# Qualify Learn CRM — Production Deployment Guide

Single-company deployment. No multi-tenancy — one `Organization` row is the whole company using this system. This guide covers what's needed to run that deployment safely on the open internet.

**Read this alongside `BACKEND_PROGRESS.md`/`BACKEND_LEARNING_GUIDE.md`** (build history and architectural reasoning) — this document is deployment-focused only.

---

## 1. Architecture

```
Internet
  |
Cloudflare (DNS, TLS termination, WAF, DDoS protection, CDN for the frontend's static assets)
  |
HTTPS only (HTTP → HTTPS redirect at Cloudflare; Django's SECURE_SSL_REDIRECT as a second layer)
  |
Frontend hosting (Next.js — Vercel, or any Node host / static export + CDN)
  |
Backend hosting (Django/Gunicorn/uvicorn — any container host: Fly.io, Render, ECS, a plain VM)
  |          \
  |           -- Redis (shared cache — distributed rate limiting only, no sessions/queues today)
  |
Managed PostgreSQL (a managed provider — RDS, Cloud SQL, Supabase, etc. — not a self-hosted box)
```

**Why this shape**: the application is already stateless (JWT auth, no server-side sessions, no local file storage — see §14). The only genuinely stateful pieces are PostgreSQL (business data) and Redis (shared rate-limit counters). Everything above the database line can scale horizontally without code changes.

### Required services
| Service | Purpose | Required? |
|---|---|---|
| PostgreSQL (managed) | System of record | Yes |
| Redis | Distributed rate-limit counters | Yes (production fails fast without `REDIS_URL`) |
| SendGrid | Outbound email | Yes for email features (fails fast without `DJANGO_SENDGRID_API_KEY`) |
| Cloudflare (or equivalent) | TLS, WAF, DDoS, CDN | Recommended, not enforced by code |
| Object storage (S3/R2) | Only if file uploads/exports move off in-request processing | Not currently required — see §12 |
| Sentry (or equivalent) | Error tracking | Recommended — see §10 |

### Environment variables
See `backend/.env.example` for the full annotated list — every variable production requires is listed there with a comment. Production settings (`config/settings/production.py`) fail fast (raise on startup) if any required variable is missing: `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SENDGRID_API_KEY`, `DATABASE_URL`, `REDIS_URL`. This is intentional — a production deployment that's missing a required security-relevant variable should refuse to start, not start in a silently-degraded state.

### Networking / firewall rules
- **PostgreSQL**: not publicly reachable. Only the backend's own network/security-group may connect to it. No exception for "just for debugging" — connect through a bastion/tunnel instead.
- **Redis**: same rule — private network only, never a public IP.
- **Backend**: only Cloudflare (or your reverse proxy/load balancer) reaches it directly; nothing else on the open internet does.
- **Frontend**: served from its own hosting/CDN; talks to the backend only via `NEXT_PUBLIC_API_URL` over HTTPS.

### Secrets handling
- Every secret (`DJANGO_SECRET_KEY`, `DJANGO_SENDGRID_API_KEY`, `DATABASE_URL`, `REDIS_URL`) comes from environment variables injected by the hosting platform's own secret store (not from a file in the repo, not from a `.env` committed anywhere — confirmed absent from git history in the prior security audit pass).
- Rotate `DJANGO_SECRET_KEY` only with a plan for the consequence: it invalidates every existing session token signature. Rotate `DJANGO_SENDGRID_API_KEY` freely (no user-facing effect).

### Deployment flow
See §8 for the full flow diagram; summary: build → test → backup → migrate → deploy → health check → release.

---

## 2. Cloudflare / Edge Security

This is infrastructure configuration, not application code — the items below are **documented, not implemented**, since no Cloudflare account exists in this environment to configure.

### DNS
- `A`/`CNAME` records for the frontend and backend hostnames, proxied through Cloudflare (orange-cloud, not grey-cloud) so WAF/DDoS protection actually sits in front of them.

### HTTPS
- **SSL/TLS mode: Full (strict)** — Cloudflare validates the origin's own TLS certificate, not just encrypts the Cloudflare-to-visitor leg. Requires a real (not self-signed) certificate on the backend origin — most managed hosts provide this automatically (Let's Encrypt or equivalent).
- **Always Use HTTPS**: on, so plain HTTP requests are redirected before they ever reach the origin.
- Django's own `SECURE_SSL_REDIRECT`/HSTS (already configured — see §3) is a second, independent layer in case a request ever reaches the origin over HTTP.

### Security rules (Cloudflare-level, not duplicated in Django)
- **WAF managed rules**: enable Cloudflare's managed ruleset (blocks common SQLi/XSS/known-CVE exploit patterns) — this is exactly the kind of pattern-matching-against-huge-signature-databases work that belongs at the edge, not reimplemented in Django middleware.
- **Bot Fight Mode / Super Bot Fight Mode**: on, to filter scanner/scraper traffic before it reaches the origin.
- **Rate limiting rules**: Cloudflare rate-limiting rules on `/api/v1/auth/login/`, `/api/v1/auth/refresh/`, `/api/v1/auth/super-admin/verify/` as a first line of defense in front of Django's own per-process/per-Redis throttles (§4) — Cloudflare's edge-level limiting is the only kind that can stop a flood before it even reaches your infrastructure's bandwidth.
- **DDoS protection**: Cloudflare's standard DDoS mitigation is active by default on proxied traffic — no extra configuration needed for L3/L4; consider a paid tier if this deployment expects to be a high-value target.

### What stays in Django, not duplicated at Cloudflare
- Authorization (who can access which record) — this requires application state Cloudflare has no visibility into.
- The `expensive_operation`/`login`/`token_refresh` throttle scopes (§4) — these are per-user/per-endpoint, a finer grain than Cloudflare's edge rules are meant to operate at.
- CORS/CSRF — origin-validation logic that belongs with the application that defines "trusted origins."

---

## 3. Application Security Hardening

Verified in the prior security audit pass and re-confirmed in this one — see `config/settings/production.py` for the actual code:

| Setting | Value | Verified |
|---|---|---|
| `DEBUG` | `False`, hardcoded, no override path | ✅ |
| `ALLOWED_HOSTS` | required env var, no wildcard | ✅ |
| `CORS_ALLOWED_ORIGINS` | required env var, no wildcard | ✅ |
| `CSRF_TRUSTED_ORIGINS` | required env var | ✅ |
| Secure cookies | `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` = `True` | ✅ |
| HSTS | 1 year, includeSubDomains, preload | ✅ |
| `X_FRAME_OPTIONS` | `DENY` | ✅ |
| `SECURE_REFERRER_POLICY` | `same-origin` | ✅ |
| Secret keys | environment only, fail-fast if missing | ✅ |
| Credentials in repo | none (git history confirmed clean) | ✅ |

### Content Security Policy — strategy documented, not yet implemented
No CSP header is currently set. Recommended policy for this app once implemented (`django-csp` or an equivalent middleware):
```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';   # Tailwind's runtime style injection needs this
img-src 'self' data:;
connect-src 'self' <backend-api-origin>;
frame-ancestors 'none';             # redundant with X_FRAME_OPTIONS but explicit
```
Not implemented in this pass because it requires coordinating with the actual deployed frontend origin (unknown until a real Cloudflare/hosting setup exists) and testing against the real built frontend bundle to confirm nothing breaks — exactly the kind of "don't claim it's configured when it isn't" the security audit called for.

### Verification
```bash
python manage.py check --deploy
```
Run this as a release gate (see §8's deployment flow) — it fails the build if any of the above regresses.

---

## 4. Rate Limiting Production Readiness

**Current limitation (documented, now addressed)**: `LocMemCache` throttle counters are per-process — with more than one backend instance/worker, each has an independent counter, so a real rate limit is effectively `limit × instance_count`, not the configured limit.

**Fix implemented this pass**: production now requires `REDIS_URL` (fails fast without it — see `config/settings/production.py`) and uses `django_redis.cache.RedisCache` as `CACHES["default"]`, which DRF's `ScopedRateThrottle` automatically uses for its counters. Development keeps `LocMemCache` (Django's default) — no code change needed there, and no unnecessary Redis dependency for local work.

### Throttle scopes in effect
| Scope | Rate | Applies to |
|---|---|---|
| `login` | 10/min | `POST /api/v1/auth/login/` |
| `super_admin_verify` | 5/min | `POST /api/v1/auth/super-admin/verify/` |
| `token_refresh` | 30/min | `POST /api/v1/auth/refresh/` |
| `expensive_operation` | 20/min | Report execution, lead import/export/merge, payment recording |

All four are per-user (authenticated) or per-IP (anonymous, for `login`) — DRF's `ScopedRateThrottle` default. 20-30/min is generous enough that no legitimate single user doing normal company work should ever hit it; it exists to stop automated abuse, not to slow down real usage. If real usage patterns prove a rate too tight (e.g., a bulk-import-heavy workflow), adjust the specific scope's rate in `config/settings/base.py`'s `DEFAULT_THROTTLE_RATES` — don't remove the scope.

### Not implemented, and correctly so
Celery/background job queues, WebSocket infrastructure, or any other "while we're adding Redis" feature — none of that was requested, and adding it now would be exactly the "unnecessary infrastructure" this pass was told not to add. Redis here has exactly one job: shared throttle counters.

---

## 5. Database Production Hardening

### Already in place
- Credentials are environment-based (`DATABASE_URL` or the `DB_*` variables) — never hardcoded, never committed.
- Every model with a searchable/filterable/orderable field has an index — see the prior scalability audit pass for the full inventory (`AuditLog.created_at`, `Lead.email`/`phone`, every FK, every `status`/`owner`/`organization` field used in a filter).

### Required, infrastructure-side (document, don't claim configured)
- **Least-privilege database role**: the application's DB user should have `SELECT`/`INSERT`/`UPDATE`/`DELETE` on its own schema only — never `SUPERUSER`, never `CREATEDB`. Migrations should run under a role with `CREATE`/`ALTER` privileges (can be the same role, or a separate migration-only role if your ops process wants tighter separation).
- **SSL/TLS to the database**: set `sslmode=require` (or `verify-full` if your provider issues a CA cert you can pin) in `DATABASE_URL` — most managed PostgreSQL providers (RDS, Cloud SQL, Supabase) support this natively.
- **Connection limits**: set `CONN_MAX_AGE` in Django's `DATABASES` config to reuse connections across requests (avoids connection-per-request overhead) — a reasonable starting value is 60 seconds; tune against your managed provider's own max-connections limit.
- **Connection pooling**: for more than a couple of backend instances, put PgBouncer (or your managed provider's built-in pooler, e.g. RDS Proxy, Supabase's pooler) in front of PostgreSQL — Django + psycopg opening a fresh connection per worker per instance exhausts a typical managed instance's connection limit fast once you're running multiple instances.
- **Firewall**: PostgreSQL's security group/firewall allows inbound connections ONLY from the backend's own network (a VPC security group reference, not an IP allowlist that has to be maintained by hand). Never `0.0.0.0/0`.

### Migration safety
`python manage.py migrate` is idempotent and safe to run repeatedly — Django tracks applied migrations in its own table. Always run it as a distinct deploy step (§8), after a backup (§6), before traffic is routed to the new code.

---

## 6. Database Backups

**See `BACKUP_AND_RECOVERY_GUIDE.md` for the full strategy, environment variables, and restore runbook** — this section is now a summary only, since the final production operations pass implemented real backup automation (`python manage.py backup_database`) rather than leaving this entirely to provider configuration.

### CODE SUPPORT vs INFRASTRUCTURE CONFIGURATION
- **Code support** (this repo): `apps/system/management/commands/backup_database.py` — `pg_dump`, SHA-256 checksum, S3-compatible upload with verification, two-tier retention. Unit-tested (5 tests). **Not** verified end-to-end (no `pg_dump` binary or real bucket in this environment — see the command's own guide for the honest verification status).
- **Infrastructure configuration** (not yet done): a real S3-compatible bucket, `pg_dump`/PostgreSQL client tools installed on whatever host runs the command, and a scheduler (cron/CronJob/platform scheduled task) invoking it periodically — this command has no built-in scheduler by design.

### Strategy
| Aspect | Recommendation |
|---|---|
| Frequency | Daily full backup + continuous WAL archiving for point-in-time recovery (most managed providers — RDS, Cloud SQL, Supabase — offer this as a checkbox, not custom tooling) |
| Retention | 30 days minimum; longer if compliance/business requirements demand it |
| Storage | A separate storage system/region from the database server itself (every managed provider's automated backup already satisfies this — verify it, don't assume it) |
| Encryption | At-rest encryption on the backup storage (again, typically a checkbox on managed providers) |
| Access control | Backup access restricted to the same least-privilege principle as §5 — only automated restore tooling and specifically authorized operators, never the application's own DB role |

### Restore runbook
1. **Detect failure** — monitoring (§10) alerts on DB connectivity errors / `/ready` returning 503 across all instances.
2. **Provision database** — spin up a new managed PostgreSQL instance (or use the provider's own point-in-time-restore feature directly on the existing instance if it supports it).
3. **Restore backup** — restore the most recent full backup, then replay WAL to the desired point in time.
4. **Apply migrations** — `python manage.py migrate` (should be a no-op if the backup is recent; catches the case where the backup predates a since-applied migration).
5. **Verify data** — spot-check row counts on a few key tables (`User`, `Customer`, `Invoice`) against the last known-good snapshot; run `python manage.py check`.
6. **Bring application online** — update `DATABASE_URL` to point at the restored instance, deploy, verify `/ready` returns 200, then route real traffic back.

**RPO/RTO for this runbook**: RPO ≈ time since last WAL segment shipped (typically seconds-to-minutes with continuous archiving); RTO depends heavily on database size and the provider's restore mechanism — budget 30–60 minutes for a typical managed-provider point-in-time restore, longer for a very large database. Neither number is currently measured against a real instance — treat these as planning estimates until tested against real infrastructure.

---

## 7. Disaster Recovery Plan

| Scenario | Detection | Protection | Recovery | RPO | RTO |
|---|---|---|---|---|---|
| **Application crash** | Health check failures (§9), error-rate alerts (§10) | Multiple instances behind a load balancer (no single point of failure) | Orchestrator restarts the failed instance automatically | 0 (stateless app) | Seconds (auto-restart) |
| **Database failure** | `/ready` returns 503, connection errors in logs | Managed PostgreSQL's own HA/failover (provider-dependent — verify your plan includes it) | Provider failover to standby, or restore from backup (§6) | Seconds (with HA standby) to minutes (WAL replay) | Minutes (HA) to ~1hr (restore) |
| **Server failure** (a single backend instance's host dies) | Orchestrator's own health checks | Multiple instances across availability zones | Orchestrator reschedules onto a healthy host | 0 | Seconds–minutes |
| **Bad deployment** | Health check fails post-deploy, error rate spikes | Deployment flow (§8) never routes traffic to a failing health check | Rollback to previous release (§8) | 0 | Minutes (time to detect + rollback) |
| **Failed migration** | Migration step in the deploy pipeline exits non-zero | Backup taken immediately before migration (§8) | Restore from that pre-migration backup; investigate and fix the migration before retrying | Minutes (time since pre-deploy backup) | Time to restore (§6) |
| **Accidental deletion** | User report, or audit log review | Soft-delete on every business model (see `BACKEND_LEARNING_GUIDE.md` — nothing is hard-deleted by default; hard-delete is a separate, Manager+-gated action) | `POST .../restore/` on the soft-deleted record — no database restore needed for the common case; a database point-in-time restore only if hard-deleted | 0 (soft-delete) / minutes (hard-delete, needs DB restore) | Seconds (soft-delete) / restore time (hard-delete) |
| **Credential compromise** (leaked `DJANGO_SECRET_KEY`, SendGrid key, DB password, or a stolen JWT) | Anomalous access patterns in logs/monitoring (§10/§11); user report | Environment-variable-only secrets (never in code), short-lived JWT access tokens (see SimpleJWT config), refresh-token rotation + blacklist | Rotate the compromised credential immediately; for a JWT, `POST /api/v1/auth/logout-all/` invalidates every other session for that user | Immediate for logout-all; minutes for credential rotation + redeploy | Minutes |
| **Traffic spike** | Latency/error-rate alerts, Cloudflare analytics | Cloudflare's edge caching/DDoS mitigation absorbs a lot before it reaches origin; stateless app scales horizontally | Scale up instance count (manual or autoscaling, if configured — see §14) | N/A | Minutes (manual) / seconds (autoscaling, if set up) |
| **Third-party outage** (SendGrid down) | Email send failures logged (`apps.communications.services.send_queued_email()` records `FAILED` status + `error_message`, never crashes the request) | Email failures are recorded, not silently swallowed — see §13 | Queued emails remain in `QUEUED`/`FAILED` state for manual or automated retry once the provider recovers; core CRM operations (leads, customers, payments) are entirely unaffected by an email outage | 0 for core app; queued emails delayed until provider recovery | Depends on provider's own outage duration |

---

## 8. Deployment Safety

### Environment separation
- **Staging**: a full copy of the production architecture (separate database, separate Redis, separate `DJANGO_SECRET_KEY`) — never shares infrastructure with production. Used to verify a release before it reaches real users.
- **Production**: real data, real users, protected by everything in §§2–4.
- Never point staging's frontend at production's backend or vice versa — enforce this via `DJANGO_CORS_ALLOWED_ORIGINS`/`DJANGO_ALLOWED_HOSTS` being genuinely different per environment.

### Deployment flow
```
Build
  |  (npm run build; collect Django static files)
Tests
  |  (pytest -q, npm run lint, npm run build must all pass — see §16)
Backup
  |  (on-demand DB snapshot immediately before migration — see §6)
Migration
  |  (python manage.py migrate, against the environment's real database)
Deploy
  |  (roll out the new backend/frontend build)
Health check
  |  (GET /health and GET /ready must both return 200 on every new instance
  |   before it receives real traffic — see §9)
Release
     (traffic fully routed to the new version; old version kept warm for a
      short window in case an immediate rollback is needed)
```

**A failed deployment must not replace a working version**: this means health-check-gated rollout (the new version only receives traffic once `/ready` confirms it can reach the database) and keeping the previous version's instances running until the new version is confirmed healthy — a blue/green or rolling deployment strategy, not an in-place replace-then-hope. Which specific mechanism (blue/green, canary, rolling) depends on the chosen hosting platform; most managed container platforms (Fly.io, Render, ECS with an ALB) provide this as a built-in deployment strategy rather than custom tooling.

### Rollback plan
1. Detect the failure (health check, error-rate alert, or manual report).
2. Route traffic back to the previous known-good version (the deployment platform's own rollback mechanism — this should be a single command/click, not a rebuild).
3. If the failed deployment included a migration, **do not** automatically roll back the database schema — assess first whether the previous code version is still compatible with the new schema (Django migrations are additive by convention in this project; a rollback of application code while keeping the migration applied is usually safe, but verify case-by-case).
4. Post-incident: fix forward, re-test in staging, redeploy.

---

## 9. Health Checks

- **`GET /health`** — liveness. Confirms the process is up and serving requests. Does NOT touch the database (a DB outage shouldn't make the orchestrator think the *process* is dead and needlessly restart it).
- **`GET /ready`** (new in this pass) — readiness. Opens a real database connection and runs `SELECT 1`. Returns `503` if the database is unreachable, `200` otherwise. Use this as the check your load balancer/orchestrator gates real traffic on — a process can be alive (`/health` = 200) while still unable to serve a single real request if its DB connection is down.
- Neither endpoint requires authentication (both must be reachable by an orchestrator with no credentials) and neither ever includes connection strings, credentials, or any other secret in its response body — both return only a status string and the service name.

---

## 10. Monitoring

**Not configured in this environment** — documented recommendations only.

### Application
- **Errors**: Sentry (or an equivalent APM/error-tracking tool) wired via `SENTRY_DSN`, capturing unhandled exceptions with request context (never with the Authorization header or request body's sensitive fields — Sentry's own `before_send` scrubbing, or Django's own exception logging discipline already in place, should filter these).
- **Latency / HTTP 5xx / failed requests**: whatever your hosting platform's built-in APM provides (most managed platforms — Render, Fly.io, Vercel — expose this without extra setup), or Sentry's own performance monitoring.

### Infrastructure
- **CPU / memory / disk**: your hosting platform's built-in metrics (every managed container platform exposes these).
- **Database connections / storage**: your managed PostgreSQL provider's own dashboard (RDS/Cloud SQL/Supabase all expose connection count, storage used, and slow-query logs natively).

### Business
- **Failed payments**: query `PaymentTransaction`/`Invoice.status` — nothing to build, the data already exists; wire an alert (even a simple scheduled query + Slack webhook) if failed-payment-adjacent patterns emerge (e.g., repeated `ValueError`s from `record_payment()` in the application logs).
- **Failed emails**: `EmailMessage.status == "FAILED"` rows — already recorded by `send_queued_email()`, not new. Alert on a rising rate.
- **Failed imports**: `import_leads()`'s own summary (`failed` count per import) — already returned to the caller; log it or feed it to a dashboard.
- **Authentication failures**: `django.security` logger (now configured — see §11) captures suspicious-request-level events; a spike in `login` throttle rejections (visible in the Redis-backed counters, or by tailing logs for 429 responses on `/api/v1/auth/login/`) is the signal to watch for a credential-stuffing attempt.

### Uptime monitoring
- An external uptime checker (UptimeRobot, Better Uptime, Cloudflare's own health checks, or your hosting platform's built-in one) polling `GET /ready` from outside your infrastructure — catches the case where your internal monitoring itself is down.

---

## 11. Logging

Implemented this pass — see `config/settings/base.py`'s `LOGGING` dict:
- Structured, one line per record (`timestamp level=... logger=... message`) — parseable by any log aggregator without regex-scraping free text.
- `django.security` (disallowed-Host, CSRF failures, other suspicious-request signals) and `django.request` (server errors, 4xx warnings) are both kept at `WARNING` so they're never buried under ordinary `INFO`-level request noise.
- **Confirmed NOT logged anywhere in this codebase**: passwords, JWTs, refresh tokens, API keys, access codes, webhook secrets, or raw payment amounts tied to identifiable individuals beyond what the CRM's own audit trail (`AuditLog`, a deliberately-designed, access-controlled feature, not a log file) already records by design. This was verified as part of the prior security audit pass's secret-exposure regression test, which applies the identical discipline to serializer output — nothing in application code logs a raw secret either.
- In production, point the `console` handler's output at whatever your hosting platform aggregates automatically (most do, out of the box, for anything written to stdout/stderr — which is exactly where this configuration sends it) rather than managing log files directly.

---

## 12. File Storage

**No business file currently depends on local disk.** Verified:
- CSV/XLSX lead import: parsed entirely in-memory during the request (`apps/crm/imports.py`), never written to local disk.
- CSV/XLSX lead export: generated in-memory and streamed directly in the HTTP response, never written to local disk.
- No attachment/document-upload feature exists anywhere in this project today.

**If that changes** (e.g., a future attachment feature), the architecture to use is `django-storages` with an S3-compatible backend (AWS S3, or Cloudflare R2 for a cheaper egress profile if the frontend/API already sits behind Cloudflare) — configured via `DEFAULT_FILE_STORAGE` and never local `MEDIA_ROOT` in production, so any of the multiple stateless backend instances (§14) can serve/accept the same files. Not implemented now because nothing in this project needs it yet — adding object storage infrastructure with no feature that uses it would be exactly the "unnecessary infrastructure" this pass was told not to add.

---

## 13. Email Reliability

- **API key**: `DJANGO_SENDGRID_API_KEY`, environment-only, fails fast in production if missing (`config/settings/production.py`).
- **Failure handling**: `apps.communications.services.send_queued_email()` never lets an SMTP failure crash the request — it catches the failure, sets the `EmailMessage.status` to `FAILED` with `error_message` recorded, and returns normally. A business operation that happens to trigger an email (e.g., "Send Reminder" in the frontend) completes successfully even if the email itself fails to send — email delivery is decoupled from the operation that queued it.
- **Retry strategy**: not automated in this pass — a `FAILED` email is a fully recorded, queryable fact (§10's monitoring recommendation) that a scheduled job or manual action could retry by re-calling `send_queued_email()` on it. Building an automated retry scheduler was out of scope for this pass (would need Celery or a cron-triggered management command — neither exists yet, and adding one without a concrete retry-policy requirement would be speculative infrastructure).
- **Logging**: send attempts/failures are recorded on the `EmailMessage` row itself (queryable, access-controlled, auditable) rather than only in application logs — a better fit for "did this specific email to this specific customer succeed" than grep-ing logs.
- **No secrets exposed**: the API key is never included in any API response, log line, or error message — `error_message` on a failed `EmailMessage` contains SMTP's own failure reason (e.g., "invalid recipient"), never the credential used to attempt the send.
- **If SendGrid is unavailable**: confirmed non-corrupting. `send_queued_email()`'s failure path doesn't touch any other model — a payment record, invoice, lead, or task is entirely unaffected by an email provider outage, since none of those write paths depend on a successful send.

---

## 14. Horizontal Scaling Readiness

**No multi-tenancy work here** — this section is purely about running more than one instance of the same single-company application.

### Verified: no blocking dependency on local/process state
- **Authentication**: JWT (SimpleJWT) — no server-side session store; any instance can validate any token independent of which instance issued it (same `SECRET_KEY` across all instances, from the shared environment variable).
- **Local memory state**: only `LocMemCache` (dev) — production's `REDIS_URL` requirement (§4) replaces this specifically because it does NOT share state across instances; nothing else in this codebase reads/writes process-local memory as a source of truth.
- **Local files**: none — see §12.
- **Process state**: none — every request is handled statelessly from the database + (in production) Redis.
- **WebSocket assumptions**: none — this project has no WebSocket/real-time feature (Django Channels isn't installed, nothing in `INSTALLED_APPS` implies it).
- **Background jobs**: `BackgroundJob` (`apps.system`) is a model that RECORDS job state — it doesn't imply a queue/worker process; nothing here assumes Celery or any other job-processing infrastructure exists.

### Future scaling path (documented, not implemented — load balancing is infrastructure's job, not application code's)
```
Load balancer
  |
  +-- Django worker instance 1  --\
  +-- Django worker instance 2  ---+-- shared Redis (rate-limit counters)
  +-- Django worker instance N  --/         |
                                        Managed PostgreSQL
```
Any standard load balancer (the hosting platform's own, or a dedicated one) in front of N identical backend instances, each stateless, each connecting to the same PostgreSQL and Redis. No code change is required to go from 1 instance to N — this was true before this pass (the app was already stateless) and remains true now; §4's Redis requirement is what makes the ONE piece of state (throttle counters) that would otherwise silently diverge across instances actually correct once N > 1.

---

## 15. Owner Assignment Fix

Fixed in this pass. See `apps/crm/services.py`'s `resolve_owner_for_create()` and its docstring for the full rule:

- **Employee**: `owner` on a newly-created record must be themselves (explicit or omitted — both resolve to self).
- **Manager**: `owner` may be themselves or anyone in their own `managed_user_ids()` (their team, the same boundary already enforced for reads).
- **Super Admin**: `owner` may be anyone.

Applied consistently across every owner-having create endpoint: `Lead`, `Customer`, `Opportunity`, `Quote`, `Invoice`, `Task`, `Event`, `SavedReport`, `Dashboard`, `Workflow`, `Integration`, `BackgroundJob`. Regression tests: `apps/core/tests/test_owner_assignment_regression.py` (8 tests — Employee blocked from assigning to another user, Employee/self-assignment allowed, Manager allowed within their team, Manager blocked outside it, Super Admin allowed for anyone).

---

## 15b. Telephony (A1 Routes)

Implemented in the final production operations pass —
`apps/communications/providers/a1routes.py` (real HTTP client),
the `Call` model, `CallViewSet` (JWT-authenticated, ownership-scoped,
audit-logged, rate-limited at the `expensive_operation` scope), and one
inbound webhook (`/api/v1/webhooks/a1routes/` — authenticated by its own
HMAC signature scheme instead of JWT, since the provider has no user
account).

**CODE READY**: request/response shapes match the provider's real API,
credentials are read from environment variables only and never appear
in a response/log, webhook signatures are verified with constant-time
comparison, both failure paths (provider unreachable, provider rejects
the request) are recorded on the created row rather than raised as a
5xx. Provider calls are mocked in tests — no real account exists to
test against.

**REQUIRES CLOUD CONFIGURATION**: a real A1 Routes account (`A1ROUTES_API_KEY`,
`A1ROUTES_WEBHOOK_SECRET`, a purchased/ported `A1ROUTES_DEFAULT_FROM_NUMBER`).
Not verified against a live account in this environment — the same
"implemented, external verification pending" status SendGrid carried
until a real key existed.

**WhatsApp Business API integration was removed** (2026-08-23 final QA
pass) — it had been explicitly descoped by the project owner earlier in
the project (SendGrid email + A1 Routes calling only, no other channel)
but was reintroduced in a later "final production operations pass"
without authorization. The removal deleted the `WhatsAppMessage` model
(migration `0004_alter_communicationlog_channel_and_more.py`), the
`whatsapp.py` provider client, the `WhatsAppMessageViewSet`/
`WhatsAppWebhookView`, all WhatsApp serializers/filters/service
functions, the `can_whatsapp` contact-capability field, the frontend
WhatsApp chat workspace, and all associated env vars
(`WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_VERIFY_TOKEN`,
`WHATSAPP_APP_SECRET`). Do not reintroduce it.

---

## 16. Final Testing

Run before every release:
```bash
python manage.py check
python manage.py check --deploy      # against production settings + real env vars
python manage.py makemigrations --check --dry-run
pytest -q

npm run lint
npm run build
```
Baseline to maintain: 1755+ backend tests passing, 0 failed, 0 errors; frontend lint and build both clean.

---

## 17. Deployment Checklist

Before the first production release:

- [ ] Managed PostgreSQL provisioned, `DATABASE_URL` set, `sslmode=require`
- [ ] Redis provisioned, `REDIS_URL` set
- [ ] SendGrid account created, `DJANGO_SENDGRID_API_KEY` set, sender domain verified
- [ ] `DJANGO_SECRET_KEY` generated (never reused from development), stored in the platform's secret manager
- [ ] `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`, `DJANGO_CSRF_TRUSTED_ORIGINS` set to the real production hostnames
- [ ] Cloudflare (or equivalent) DNS + WAF + Full-strict TLS configured (§2)
- [ ] Database automated backups confirmed enabled on the managed provider, retention ≥30 days (§6)
- [ ] Staging environment stood up and a full deploy rehearsed against it (§8)
- [ ] `/health` and `/ready` both verified reachable and correct pre-launch
- [ ] Uptime monitor pointed at `/ready`
- [ ] Sentry (or equivalent) DSN configured, one test exception confirmed to arrive
- [ ] This checklist itself reviewed by whoever owns the production database credentials

---

## Final section: what this guide does NOT claim

Per this pass's own instruction not to claim infrastructure exists unless it's actually configured: **nothing in §§2, 6 (infra side), 7, 10, or parts of §5/§14 has been configured against real infrastructure in this environment.** This is a local development checkout. Everything above is the application-code readiness (verified — settings fail fast without required production configuration, `/ready` genuinely checks the database, throttling genuinely uses Redis when `REDIS_URL` is set) plus the documented plan for the infrastructure a real deployment still needs to provision.
