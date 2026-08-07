"""CP7: tests for apps/core/views.py.

These mixins are meant to be combined with a real DRF generic view/viewset
around a concrete model — since CP7 defines no concrete endpoint, the
mixins are exercised here against a minimal stand-in ``self`` exposing just
the attributes/methods DRF's own generic views would provide
(``request``, ``get_object()``, ``get_serializer()``), rather than a full
URL-routed viewset.
"""
import pytest
from rest_framework import serializers

from apps.core.tests.models import SampleRecord
from apps.core.views import AuditStampedModelMixin, SoftDeleteModelMixin

# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class _SampleRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SampleRecord
        fields = ["id", "name", "is_deleted", "deleted_at"]


class _FakeRequest:
    def __init__(self, user):
        self.user = user


class _FakeAuditView(AuditStampedModelMixin):
    def __init__(self, user, instance):
        self.request = _FakeRequest(user)
        self._instance = instance


class _FakeSerializer:
    """Stands in for the serializer DRF passes to perform_create/perform_update."""

    def __init__(self, instance):
        self._instance = instance

    def save(self):
        return self._instance


class _FakeDestroyView(SoftDeleteModelMixin):
    def __init__(self, user, instance):
        self.request = _FakeRequest(user)
        self._instance = instance

    def get_object(self):
        return self._instance

    def get_serializer(self, instance):
        return _SampleRecordSerializer(instance)


# --------------------------------------------------------------------------
# No database required — class shape
# --------------------------------------------------------------------------


def test_soft_delete_model_mixin_declares_restore_and_hard_delete_actions():
    assert hasattr(SoftDeleteModelMixin, "restore")
    assert hasattr(SoftDeleteModelMixin, "hard_delete")


def test_restore_action_is_permission_gated():
    mapping = SoftDeleteModelMixin.restore.mapping
    assert "post" in mapping


def test_hard_delete_action_uses_hyphenated_url_path():
    action = SoftDeleteModelMixin.hard_delete
    assert action.url_path == "hard-delete"


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_perform_create_stamps_created_by(core_test_tables, django_user_model):
    user = django_user_model.objects.create_user(email="creator@example.com", password="x")
    instance = SampleRecord(name="new")
    view = _FakeAuditView(user, instance)
    fake_serializer = _FakeSerializer(instance)
    instance.save()  # give it a pk so the second save() in perform_create works

    view.perform_create(fake_serializer)

    instance.refresh_from_db()
    assert instance.created_by_id == user.id
    assert instance.updated_by_id == user.id


@pytest.mark.django_db
def test_perform_update_stamps_updated_by_not_created_by(core_test_tables, django_user_model):
    creator = django_user_model.objects.create_user(email="creator2@example.com", password="x")
    editor = django_user_model.objects.create_user(email="editor@example.com", password="x")
    instance = SampleRecord.objects.create(name="existing", created_by=creator)
    view = _FakeAuditView(editor, instance)
    fake_serializer = _FakeSerializer(instance)

    view.perform_update(fake_serializer)

    instance.refresh_from_db()
    assert instance.created_by_id == creator.id
    assert instance.updated_by_id == editor.id


@pytest.mark.django_db
def test_perform_destroy_soft_deletes_instead_of_hard_deleting(core_test_tables):
    instance = SampleRecord.objects.create(name="to-delete")
    view = _FakeDestroyView(user=None, instance=instance)

    view.perform_destroy(instance)

    assert SampleRecord.objects.filter(pk=instance.pk).exists()
    instance.refresh_from_db()
    assert instance.is_deleted is True


@pytest.mark.django_db
def test_restore_action_restores_and_returns_serialized_instance(core_test_tables):
    instance = SampleRecord.objects.create(name="restorable")
    instance.soft_delete()
    view = _FakeDestroyView(user=None, instance=instance)

    response = SoftDeleteModelMixin.restore(view, request=_FakeRequest(None))

    assert response.status_code == 200
    instance.refresh_from_db()
    assert instance.is_deleted is False


@pytest.mark.django_db
def test_hard_delete_action_removes_the_row(core_test_tables):
    instance = SampleRecord.objects.create(name="permanent-removal")
    pk = instance.pk
    view = _FakeDestroyView(user=None, instance=instance)

    response = SoftDeleteModelMixin.hard_delete(view, request=_FakeRequest(None))

    assert response.status_code == 204
    assert not SampleRecord.objects.filter(pk=pk).exists()
