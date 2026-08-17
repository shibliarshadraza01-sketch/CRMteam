# Qualify Learn CRM — Backup and Recovery Guide

Companion to `PRODUCTION_DEPLOYMENT_GUIDE.md` — this document covers database backup automation, retention, and restoration specifically. Single-company deployment; no multi-tenant backup partitioning needed.

---

## 1. Requirement

**No company data loss.** The database is the single source of truth for every lead, customer, invoice, payment, task, and audit record this business depends on. A backup strategy that "should work" is not a backup strategy — this one is verified (checksummed on upload, re-downloaded and compared) rather than assumed.

---

## 2. What's implemented in code vs. what requires cloud configuration

| Piece | Status |
|---|---|
| `python manage.py backup_database` — runs `pg_dump`, computes a SHA-256 checksum, uploads to S3-compatible storage, verifies the upload, applies retention | **IMPLEMENTED** (`apps/system/management/commands/backup_database.py`) |
| Retention policy logic (last 24h kept in full, older thinned to 1/day, past `BACKUP_RETENTION_DAYS` deleted) | **IMPLEMENTED**, unit-tested (`apps/system/tests/test_backup_command.py`, 5 tests, all passing) |
| Upload verification (re-download + compare checksum, fail loudly on mismatch) | **IMPLEMENTED** |
| A real S3-compatible bucket to upload to | **REQUIRES CLOUD CONFIGURATION** — no bucket exists in this environment |
| `pg_dump`/PostgreSQL client tools on the host that runs this command | **REQUIRES INFRASTRUCTURE** — not installed on this development machine (verified: running the command without them fails with a clear `CommandError`, not a crash — see §7) |
| A scheduler that invokes this command periodically (cron, Kubernetes CronJob, your platform's scheduled-task feature) | **REQUIRES INFRASTRUCTURE CONFIGURATION** — this command has no built-in scheduler by design (see its own docstring: adding one without an actual deployment target would be speculative infrastructure) |
| Point-in-time recovery via continuous WAL archiving | **REQUIRES CLOUD CONFIGURATION** — this is a managed-PostgreSQL-provider feature (RDS, Cloud SQL, Supabase all offer it as a checkbox), not something `pg_dump`-based backups alone provide |

**Do not read "implemented in code" as "backups are happening."** Nothing backs up automatically until a real bucket + scheduler exist. This is the honest state, not an optimistic one.

---

## 3. Backup strategy

### Frequency
Two complementary mechanisms, matching the "no company data loss" requirement without overengineering:

1. **This command, scheduled frequently** — e.g. every 10 minutes (`DATABASE_BACKUP_INTERVAL=10_MINUTES` as a scheduler-side setting, not a Django setting — the interval lives in whatever cron/CronJob/scheduled-task configuration invokes `manage.py backup_database`, not in this codebase). Gives a worst-case RPO of ~10 minutes for a full logical dump.
2. **Continuous WAL archiving**, if your managed PostgreSQL provider offers it (most do) — gives point-in-time recovery to any second, not just to the last `pg_dump` snapshot. Recommended as the primary recovery mechanism; the scheduled `pg_dump` backups are the fallback/cross-check.

### Retention (implemented in `_apply_retention()`)
Exactly the tiered policy this project's own requirements describe, applied automatically on every run so a 10-minute schedule doesn't accumulate thousands of objects:

| Age | Kept |
|---|---|
| < 24 hours | Every backup (however many the 10-minute schedule produced) |
| 24 hours – `BACKUP_RETENTION_DAYS` (default 30) | Thinned to at most one per calendar day |
| > `BACKUP_RETENTION_DAYS` | Deleted entirely |

This is genuinely "keep last 24h at full granularity, last 30 days daily, older removed" — not the "weekly/monthly beyond 30 days" tier the original brief sketched as an example, because at 30 days of daily backups plus continuous WAL archiving (§3.1) for anything more precise, a THIRD tier (weekly/monthly retained indefinitely) adds real storage cost for a recovery scenario ("restore to a specific day, 6 months ago") this single-company deployment has not stated it needs. If that requirement becomes real, extending `_apply_retention()` with a third bucket is a small, contained change to one function — documented here as a deliberate scope decision, not an oversight.

### Storage location
**Must be separate from the database server** — implemented via S3-compatible object storage (AWS S3, Cloudflare R2, or Backblaze B2, chosen via `BACKUP_STORAGE_PROVIDER`), never the database host's own local disk. The command's `BACKUP_LOCAL_DIR` is explicitly scratch space, deleted immediately after a successful upload — see the command's own docstring.

### Encryption
- **In transit**: HTTPS to the S3-compatible endpoint (`boto3`'s default).
- **At rest**: enable server-side encryption on the bucket itself (a bucket-policy setting on the provider side, not something this command needs to implement — AWS S3/Cloudflare R2/Backblaze B2 all support SSE natively).

### Access control
The `BACKUP_S3_ACCESS_KEY`/`BACKUP_S3_SECRET_KEY` credential should be scoped (via the provider's own IAM/access-key permissions) to that one bucket only — write + list + delete on `backups/*`, nothing else. Never the same credential as the application's own database or SendGrid credentials.

---

## 4. Environment variables

```bash
BACKUP_STORAGE_PROVIDER=r2          # "s3" | "r2" | "b2" (documentation only — boto3 talks the same S3 API to all three)
BACKUP_BUCKET=qualify-learn-crm-backups
BACKUP_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com   # omit entirely for real AWS S3
BACKUP_S3_ACCESS_KEY=<scoped-to-this-bucket-only>
BACKUP_S3_SECRET_KEY=<scoped-to-this-bucket-only>
BACKUP_S3_REGION=auto               # R2's own default; set a real AWS region for S3
BACKUP_RETENTION_DAYS=30
BACKUP_LOCAL_DIR=/tmp/qualify-learn-crm-backups   # scratch space only, not durable storage
```

None of these are read by Django's own settings modules — they're read directly by `backup_database.py` at run time (`os.environ.get(...)`), matching every provider client this project already uses (SendGrid, A1 Routes, WhatsApp) — see each one's own module docstring for the same "environment only, read at call time, never cached into a settings constant" pattern.

---

## 5. RPO / RTO

| Recovery mechanism | RPO | RTO |
|---|---|---|
| Continuous WAL archiving (managed provider) | Seconds | Minutes — provider-dependent, budget 15–60 min for a large database |
| Scheduled `pg_dump` (this command, every 10 min) | ~10 minutes | Time to download + `pg_restore` — budget 15–60 min depending on database size |

Neither number is measured against a real production-scale database in this environment — both are planning estimates, stated as such, not claims of a tested SLA.

---

## 6. Restore procedure

1. **Detect failure** — monitoring alerts (see `PRODUCTION_DEPLOYMENT_GUIDE.md` §10), or `/ready` returning 503.
2. **Choose the recovery point**:
   - Prefer the managed provider's own point-in-time restore (WAL-based) if the target time is within its retention window — the most precise option.
   - Otherwise, pick the most recent `pg_dump` backup at or before the target time from the bucket (`backups/` prefix, filenames are `<db-name>-<UTC-timestamp>.dump`).
3. **Verify the chosen backup's integrity** before restoring: download `<filename>.sha256` alongside the dump and confirm it matches a freshly-computed SHA-256 of the downloaded dump file. Do not restore an unverified file.
4. **Provision/target a database** — a fresh managed PostgreSQL instance, or the provider's own point-in-time-restore feature directly.
5. **Restore**: `pg_restore --format=custom --dbname=<target> <dump-file>` (the `-Fc` format `backup_database.py` produces is exactly what `pg_restore` expects).
6. **Apply migrations**: `python manage.py migrate` — a no-op if the backup is recent enough to already include every applied migration; catches the case where it isn't.
7. **Verify data**: spot-check row counts on `User`, `Customer`, `Invoice` against the last known-good state; `python manage.py check`.
8. **Bring the application online**: update `DATABASE_URL`/`DB_*` env vars to point at the restored database, deploy, confirm `GET /ready` returns 200, then route real traffic back.

---

## 7. Honest verification status

- ✅ `backup_database`'s own logic (checksum computation, upload-verification failure handling, retention thinning) — unit-tested with mocked `subprocess`/`boto3`, 5/5 tests passing.
- ✅ Missing-`pg_dump` failure path — live-verified in this environment: running the command without PostgreSQL client tools installed fails with a clear, actionable `CommandError` (exit code 1), not a crash or a silently-corrupt backup.
- ❌ **NOT verified**: a real `pg_dump` run against real data, a real S3-compatible upload, or a real `pg_restore`. This development environment has no PostgreSQL client tools installed and no S3-compatible bucket provisioned. This is stated plainly rather than implied otherwise — the same "code ready, infrastructure not configured" distinction `PRODUCTION_DEPLOYMENT_GUIDE.md` draws throughout.
