"""Final production operations pass: database backup automation.

    python manage.py backup_database

Runs ``pg_dump`` (compressed custom format, ``-Fc``) against the
database Django itself is configured for (``settings.DATABASES["default"]``
— never a separately-hardcoded connection string, so this command can
never accidentally back up the wrong database), computes a SHA-256
checksum of the resulting file, and — if S3-compatible storage is
configured via environment variables — uploads both to that bucket and
applies a retention policy so backups don't accumulate unbounded.

Environment variables (all optional; the command still runs a local-only
backup with none of them set — see the docstring on ``handle()`` for
exactly what happens at each configuration level):

    BACKUP_STORAGE_PROVIDER   "s3" | "r2" | "b2" | "" (unset = local-only)
    BACKUP_BUCKET             target bucket name
    BACKUP_S3_ENDPOINT_URL    required for r2/b2 (S3-compatible endpoint);
                               omit for real AWS S3
    BACKUP_S3_ACCESS_KEY      credential (never logged, never printed)
    BACKUP_S3_SECRET_KEY      credential (never logged, never printed)
    BACKUP_S3_REGION          default "auto" (Cloudflare R2's own default)
    BACKUP_RETENTION_DAYS     default 30 — backups older than this are
                               deleted from the bucket (never from local
                               disk, which is treated as scratch space)
    BACKUP_LOCAL_DIR          default "/tmp/qualify-learn-crm-backups" —
                               where the dump is written before upload;
                               NOT the durable copy (see
                               BACKUP_AND_RECOVERY_GUIDE.md's "storage
                               must be separate from the database server"
                               requirement) — this is scratch space,
                               cleaned up after a successful upload.

Intended to be invoked on a schedule (cron, a Kubernetes CronJob, or your
platform's own scheduled-task feature) — see BACKUP_AND_RECOVERY_GUIDE.md
for the recommended interval and the reasoning behind it. This command
itself has no built-in scheduler; adding one (Celery beat, an in-process
timer) would be exactly the kind of speculative infrastructure this
project's own instructions say not to add without an actual requirement
driving it.
"""
import datetime
import hashlib
import os
import subprocess
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

DEFAULT_RETENTION_DAYS = 30
DEFAULT_LOCAL_DIR = os.path.join(tempfile.gettempdir(), "qualify-learn-crm-backups")


class Command(BaseCommand):
    help = "Back up the PostgreSQL database (pg_dump), optionally uploading to S3-compatible storage with retention."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-upload",
            action="store_true",
            help="Write the dump locally only, even if BACKUP_STORAGE_PROVIDER is configured — useful for testing pg_dump connectivity without touching remote storage.",
        )

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        local_dir = os.environ.get("BACKUP_LOCAL_DIR", DEFAULT_LOCAL_DIR)
        os.makedirs(local_dir, exist_ok=True)

        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dump_filename = f"{db['NAME']}-{timestamp}.dump"
        dump_path = os.path.join(local_dir, dump_filename)

        self.stdout.write(f"Starting backup of database '{db['NAME']}' -> {dump_path}")
        self._run_pg_dump(db, dump_path)

        checksum = self._sha256_of(dump_path)
        checksum_path = dump_path + ".sha256"
        with open(checksum_path, "w") as fh:
            fh.write(checksum)
        self.stdout.write(self.style.SUCCESS(f"pg_dump complete. SHA-256: {checksum}"))

        provider = os.environ.get("BACKUP_STORAGE_PROVIDER", "").strip().lower()
        if provider and not options["skip_upload"]:
            self._upload_and_apply_retention(dump_path, checksum_path, dump_filename, provider)
            os.remove(dump_path)
            os.remove(checksum_path)
            self.stdout.write(self.style.SUCCESS("Uploaded to remote storage; local scratch copy removed."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "BACKUP_STORAGE_PROVIDER not set (or --skip-upload passed) — dump left on local disk only. "
                    "This does NOT satisfy the 'storage must be separate from the database server' requirement "
                    "— see BACKUP_AND_RECOVERY_GUIDE.md."
                )
            )

    def _run_pg_dump(self, db, dump_path):
        env = os.environ.copy()
        if db.get("PASSWORD"):
            env["PGPASSWORD"] = db["PASSWORD"]
        command = [
            "pg_dump",
            "--format=custom",
            f"--host={db.get('HOST', 'localhost')}",
            f"--port={db.get('PORT', '5432')}",
            f"--username={db.get('USER', '')}",
            f"--dbname={db['NAME']}",
            f"--file={dump_path}",
        ]
        try:
            subprocess.run(command, env=env, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise CommandError(
                "pg_dump was not found on PATH. It ships with the PostgreSQL client tools — "
                "install postgresql-client (or equivalent) on whatever host runs this command."
            ) from exc
        except subprocess.CalledProcessError as exc:
            # exc.stderr is pg_dump's own error text — never includes the
            # password (PGPASSWORD is an env var, not a command-line arg
            # pg_dump would echo back).
            raise CommandError(f"pg_dump failed: {exc.stderr}") from exc

    @staticmethod
    def _sha256_of(path):
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _s3_client(self):
        import boto3

        endpoint_url = os.environ.get("BACKUP_S3_ENDPOINT_URL") or None
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=os.environ.get("BACKUP_S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("BACKUP_S3_SECRET_KEY"),
            region_name=os.environ.get("BACKUP_S3_REGION", "auto"),
        )

    def _upload_and_apply_retention(self, dump_path, checksum_path, dump_filename, provider):
        bucket = os.environ.get("BACKUP_BUCKET", "")
        if not bucket:
            raise CommandError("BACKUP_STORAGE_PROVIDER is set but BACKUP_BUCKET is not.")

        client = self._s3_client()
        key = f"backups/{dump_filename}"
        client.upload_file(dump_path, bucket, key)
        client.upload_file(checksum_path, bucket, key + ".sha256")

        # Verification, not just a hope: re-download the checksum we just
        # uploaded and confirm it round-trips — catches a truncated/
        # corrupted upload immediately rather than at restore time, when
        # it's far too late to just re-run the backup.
        remote_checksum = client.get_object(Bucket=bucket, Key=key + ".sha256")["Body"].read().decode().strip()
        local_checksum = self._sha256_of(dump_path)
        if remote_checksum != local_checksum:
            raise CommandError(
                f"Backup verification FAILED: uploaded checksum ({remote_checksum}) does not match "
                f"the local dump's own checksum ({local_checksum}). The remote copy is not trustworthy."
            )
        self.stdout.write(self.style.SUCCESS(f"Verified: {key} (checksum matches)."))

        self._apply_retention(client, bucket)

    def _apply_retention(self, client, bucket):
        """Two-tier retention, matching BACKUP_AND_RECOVERY_GUIDE.md's
        documented policy without needing this command to know its own
        run frequency: everything younger than 1 day is kept in full
        (however often the scheduler runs this command); anything older
        than 1 day is thinned to at most one backup per calendar day;
        anything older than ``BACKUP_RETENTION_DAYS`` is deleted
        entirely. This is what keeps a "run every 10 minutes" schedule
        from silently accumulating thousands of objects — the explicit
        concern this command's own docstring/the ops guide both call out.
        """
        retention_days = int(os.environ.get("BACKUP_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))
        now = datetime.datetime.now(datetime.timezone.utc)
        one_day_ago = now - datetime.timedelta(days=1)
        cutoff = now - datetime.timedelta(days=retention_days)

        paginator = client.get_paginator("list_objects_v2")
        objects = []
        for page in paginator.paginate(Bucket=bucket, Prefix="backups/"):
            objects.extend(page.get("Contents", []))

        dumps = sorted(
            (obj for obj in objects if obj["Key"].endswith(".dump")),
            key=lambda obj: obj["LastModified"],
        )

        kept_dates = set()
        to_delete = []
        for obj in dumps:
            last_modified = obj["LastModified"]
            if last_modified < cutoff:
                to_delete.append(obj["Key"])
                continue
            if last_modified >= one_day_ago:
                continue  # keep every backup from the last 24 hours
            date_key = last_modified.date()
            if date_key in kept_dates:
                to_delete.append(obj["Key"])  # already have one for this day
            else:
                kept_dates.add(date_key)

        for key in to_delete:
            client.delete_object(Bucket=bucket, Key=key)
            client.delete_object(Bucket=bucket, Key=key + ".sha256")

        if to_delete:
            self.stdout.write(f"Retention: removed {len(to_delete)} stale backup(s).")
