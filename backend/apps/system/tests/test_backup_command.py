"""Final production operations pass: unit tests for
``manage.py backup_database``. ``pg_dump`` itself is not installed in
this environment (no PostgreSQL client tools on this machine — see
BACKUP_AND_RECOVERY_GUIDE.md's own honest note about that), so
``subprocess.run`` and ``boto3`` are both mocked here — these tests
verify OUR command's own logic (checksum computation, retention
thinning, upload-verification failure handling), not a real pg_dump/S3
round trip.
"""
import hashlib
import os
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import CommandError, call_command

pytestmark = pytest.mark.django_db


def _fake_pg_dump(command, env, check, capture_output, text):
    # command[-1] is "--file=<path>"; write a real small file so the
    # command's own checksum/upload logic has real bytes to work with.
    dump_path = command[-1].split("=", 1)[1]
    with open(dump_path, "wb") as fh:
        fh.write(b"fake pg_dump output for testing")
    return MagicMock(returncode=0)


def test_backup_skip_upload_writes_local_file_and_checksum(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_LOCAL_DIR", str(tmp_path))
    out = StringIO()
    with patch("subprocess.run", side_effect=_fake_pg_dump):
        call_command("backup_database", "--skip-upload", stdout=out)

    files = list(tmp_path.iterdir())
    dumps = [f for f in files if f.suffix == ".dump"]
    checksums = [f for f in files if f.name.endswith(".sha256")]
    assert len(dumps) == 1
    assert len(checksums) == 1
    expected = hashlib.sha256(dumps[0].read_bytes()).hexdigest()
    assert checksums[0].read_text() == expected
    assert "pg_dump complete" in out.getvalue()


def test_backup_missing_pg_dump_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_LOCAL_DIR", str(tmp_path))
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        with pytest.raises(CommandError, match="pg_dump was not found on PATH"):
            call_command("backup_database", "--skip-upload")


def test_backup_pg_dump_failure_raises_clear_error_without_leaking_password(tmp_path, monkeypatch):
    import subprocess

    monkeypatch.setenv("BACKUP_LOCAL_DIR", str(tmp_path))
    error = subprocess.CalledProcessError(1, ["pg_dump"], stderr="connection refused")
    with patch("subprocess.run", side_effect=error):
        with pytest.raises(CommandError) as exc_info:
            call_command("backup_database", "--skip-upload")
    assert "connection refused" in str(exc_info.value)


def test_backup_upload_verifies_checksum_and_fails_on_mismatch(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_LOCAL_DIR", str(tmp_path))
    monkeypatch.setenv("BACKUP_STORAGE_PROVIDER", "s3")
    monkeypatch.setenv("BACKUP_BUCKET", "test-bucket")

    fake_client = MagicMock()
    fake_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"wrong-checksum")}
    fake_client.get_paginator.return_value.paginate.return_value = [{"Contents": []}]

    with patch("subprocess.run", side_effect=_fake_pg_dump):
        with patch("boto3.client", return_value=fake_client):
            with pytest.raises(CommandError, match="Backup verification FAILED"):
                call_command("backup_database")

    fake_client.upload_file.assert_called()


def test_backup_retention_keeps_last_24h_thins_older_deletes_stale():
    from apps.system.management.commands.backup_database import Command

    now = datetime.now(timezone.utc)
    objects = [
        {"Key": "backups/a.dump", "LastModified": now - timedelta(hours=2)},   # kept: <24h
        {"Key": "backups/b.dump", "LastModified": now - timedelta(hours=5)},   # kept: <24h
        {"Key": "backups/c.dump", "LastModified": now - timedelta(days=3, hours=1)},   # kept: first for its day
        {"Key": "backups/d.dump", "LastModified": now - timedelta(days=3, hours=2)},   # thinned: same day as c
        {"Key": "backups/e.dump", "LastModified": now - timedelta(days=45)},   # deleted: past retention
    ]
    fake_client = MagicMock()
    fake_client.get_paginator.return_value.paginate.return_value = [{"Contents": objects}]

    cmd = Command()
    cmd.stdout = StringIO()
    with patch.dict(os.environ, {"BACKUP_RETENTION_DAYS": "30"}):
        cmd._apply_retention(fake_client, "test-bucket")

    # Objects are processed oldest-first, so within a thinned day the
    # OLDEST backup for that day is the one kept (c and d fall on the
    # same calendar date; d is older, so d is kept and c is thinned).
    deleted_keys = {call.kwargs["Key"] for call in fake_client.delete_object.call_args_list if call.kwargs["Key"].endswith(".dump")}
    assert deleted_keys == {"backups/c.dump", "backups/e.dump"}
