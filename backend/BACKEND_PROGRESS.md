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

| CP2 | Accounts + Custom User | NEXT |

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



\### Migration State



\*\*DO NOT run `migrate` yet.\*\*



18 built-in Django migrations are intentionally unapplied.



Required sequence:



CP2 accounts app

→ custom User

→ `AUTH\_USER\_MODEL = "accounts.User"`

→ accounts initial migration

→ FIRST `migrate`



This prevents changing the Django user model after initial migrations.



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



\## Current Database



\- Engine: PostgreSQL

\- Development DB: `crm\_db`

\- Application role: `crm\_dev`

\- Project domain models: NONE

\- Project migrations: NONE

\- Built-in migrations: intentionally unapplied



No secrets are stored in this document.



\## Next — CP2 Accounts + Custom User



Order:



1\. Create `accounts` app.

2\. Design custom User model.

3\. Establish role foundation.

4\. Configure `AUTH\_USER\_MODEL`.

5\. Create initial accounts migration.

6\. Inspect migration.

7\. Run Django checks.

8\. Perform project's FIRST `migrate`.

9\. Test.

10\. Update `BACKEND\_PROGRESS.md`.

11\. Update `BACKEND\_LEARNING\_GUIDE.md`.

12\. STOP.



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

