# Qualify Learn CRM

A CRM built on Django + Django REST Framework + PostgreSQL (backend) and Next.js (frontend), covering Authentication, Organization/Team management, Leads, Customers, Payments (with a real partial-payment ledger), Communication (email via SendGrid, telephony via A1 Routes), Tasks, Reports/Dashboards, Audit logging, Settings, and User/Role management. Single-company deployment — no multi-tenancy. (A WhatsApp Business API channel previously existed; it was removed in the 2026-08-23 final QA pass — explicitly descoped by the project owner — and must not be reintroduced.)

See `backend/BACKEND_LEARNING_GUIDE.md` and `backend/BACKEND_PROGRESS.md` for the full build history and architectural reasoning behind every module. For running this in production, see `backend/PRODUCTION_DEPLOYMENT_GUIDE.md` (architecture, Cloudflare/WAF, scaling, monitoring) and `backend/BACKUP_AND_RECOVERY_GUIDE.md` (backup strategy, restore runbook).

## Architecture

- **Backend**: Django 5.1 + DRF + SimpleJWT + drf-spectacular (OpenAPI schema) + django-filter, PostgreSQL only (never SQLite).
- **Frontend**: Next.js 15 (App Router) + TypeScript, talking to the backend exclusively through `lib/api.ts`'s typed REST client — no mock data, no local-only CRUD for any of the modules listed above.
- Every domain app under `backend/apps/` follows the same layering: `models.py` (soft-delete, audit-stamped) → `services.py` (business rules, the only place state transitions happen) → `serializers.py` → `views.py` (thin, delegates to services) → `urls.py`.

## Local setup

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # fill in real values — see below
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Requires a real PostgreSQL instance — create the database/role referenced by `DB_NAME`/`DB_USER`/`DB_PASSWORD` in `.env` before running `migrate`.

### Frontend

```bash
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL` in `.env.local` if the backend isn't on `http://localhost:8000`.

## Environment variables

See `backend/.env.example` for the full annotated list. Summary:

| Variable | Required | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | always | Django's cryptographic signing key |
| `DJANGO_ALLOWED_HOSTS` | always | comma-separated allowed `Host` headers |
| `DJANGO_CORS_ALLOWED_ORIGINS` | always | frontend origin(s) allowed to call the API |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | always | PostgreSQL connection |
| `DJANGO_SENDGRID_API_KEY` | production | SendGrid SMTP relay credential — emails print to the console in development when unset; production fails fast without it |
| `DJANGO_DEFAULT_FROM_EMAIL` | production | outgoing email "From" address |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | production | fails fast without it |
| `DJANGO_BEHIND_PROXY` | production, opt-in | set `true` only when an actual TLS-terminating reverse proxy sits in front |
| `REDIS_URL` | production | shared cache for distributed rate limiting across instances — fails fast without it in production; development uses Django's local in-process cache instead |
| `A1ROUTES_API_KEY` / `A1ROUTES_WEBHOOK_SECRET` / `A1ROUTES_DEFAULT_FROM_NUMBER` | optional | SIP telephony (A1 Routes) — leave unset to leave calling provider-ready-but-unverified |
| `BACKUP_*` | optional | database backup automation — see `backend/BACKUP_AND_RECOVERY_GUIDE.md` |

Never commit a real `.env` — it's gitignored, and `.env.example` must stay placeholder-only.

## Testing

```bash
# Backend — full regression suite (PostgreSQL required)
cd backend
python manage.py check
python manage.py check --deploy          # against production settings + real env vars
python manage.py makemigrations --check --dry-run
python -m pytest -v

# Frontend
npm run lint
npm run build
```

## Deployment

1. Set every "production" env var above (`.env` is never used in production — inject real environment variables through your platform).
2. `DEBUG` is hardcoded `False` in `config/settings/production.py` — there is no env var that can re-enable it.
3. Run `python manage.py migrate` against the production database before serving traffic.
4. Run `python manage.py check --deploy` as a release gate — it fails the build if `DJANGO_CSRF_TRUSTED_ORIGINS` or `DJANGO_SENDGRID_API_KEY` is missing, or if any Django security check fails.
5. `npm run build` produces the Next.js production build; serve it with `npm run start` or your platform's Next.js adapter.

## Known external dependencies / scope limits

- **SendGrid, A1 Routes (SIP telephony)**: both are wired correctly — real HTTP clients, real webhook signature verification, real audit logging — but neither has been verified against a real provider account in this environment (no credentials available). Status: implemented, external verification pending for both.
- **WhatsApp Business API**: removed (2026-08-23 final QA pass). It had been explicitly descoped by the project owner (SendGrid email + A1 Routes calling only) but was reintroduced without authorization in a later pass; it has now been fully removed (model, migration, provider client, views/serializers/filters, frontend workspace, env vars) and must not be reintroduced.
- **Meta Lead Ads**: not implemented in this codebase. Only a generic webhook/integration framework (`apps.integrations`: `Integration`, `WebhookEndpoint`, `WebhookDelivery`) and generic lead-ingestion-readiness fields on `Lead` (`external_source_id`, `source_metadata`, `received_at`) exist; there is no Meta-specific webhook handler, signature verification, or Graph API client. Lead ingestion from an external source in this codebase is via the Google Sheets import action on `LeadViewSet`, not Meta.
- **File storage/transcription**: out of scope — no feature in this project needs it (CSV/XLSX import/export are handled entirely in-request, never touching disk or object storage).
- **Calendar reminders/notes**: intentionally local-only (browser state), by design — no backend model exists for them.
- **Database backups**: automation is implemented (`python manage.py backup_database`) and unit-tested, but not verified end-to-end — no PostgreSQL client tools or S3-compatible bucket exist in this development environment. See `backend/BACKUP_AND_RECOVERY_GUIDE.md`.
