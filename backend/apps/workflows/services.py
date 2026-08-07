"""CP17: the workflow automation engine.

No Django signal is wired to any CRM model (`Customer`/`Lead`/
`Opportunity`/`Quote`/`Invoice`) by this checkpoint to fire triggers
automatically. Doing so would mean editing CP9's/CP11's/CP12's own
`save()`/`delete()` methods or attaching `post_save`/`post_delete`
receivers to models this app does not own — a cross-app side effect on
ALREADY-SHIPPED checkpoints that CP17 was not asked to make, the same
"don't widen a shared thing's behavior as a side effect of a new,
unrelated checkpoint" restraint CP15 applied to `RelatedToEntityModel`
(see that checkpoint's own "Deferred" section) and CP16 applied to not
adding entity-level access control it wasn't asked to build. `evaluate_and_run()`
below is written and fully testable today; wiring an actual signal
receiver to call it is a future checkpoint's decision, not this one's.

Ownership scoping is NOT reimplemented — CP10's `managed_user_ids()`/
`scope_queryset_for_user()` are imported directly from `apps.crm.services`.
"""
from django.utils import timezone

from apps.crm.services import managed_user_ids, scope_queryset_for_user  # noqa: F401 (re-exported)

from .models import Workflow, WorkflowAction, WorkflowExecution, WorkflowTrigger

# --------------------------------------------------------------------------
# Workflow / trigger / action management
# --------------------------------------------------------------------------


def create_workflow(name, *, owner=None, description=""):
    """Create a `Workflow`. A thin wrapper — kept as a service function for
    the same single-seam reasoning as CP9's `create_lead()`.
    """
    return Workflow.objects.create(name=name, owner=owner, description=description)


def add_trigger(workflow, trigger_type, *, content_type=None, conditions=None):
    """Add a `WorkflowTrigger` to `workflow`. A thin wrapper — kept for
    architectural symmetry with `add_action()`, below.
    """
    return WorkflowTrigger.objects.create(
        workflow=workflow, trigger_type=trigger_type, content_type=content_type, conditions=conditions or {}
    )


def add_action(workflow, action_type, *, configuration=None, position=None):
    """Add a `WorkflowAction` to `workflow`. Auto-assigns `position` (one
    past the current highest) when omitted — same auto-ordering
    convenience CP12's `add_quote_item()`/CP16's `add_widget()` established.
    """
    from django.db.models import Max

    if position is None:
        highest = WorkflowAction.objects.filter(workflow=workflow).aggregate(Max("position"))["position__max"]
        position = 0 if highest is None else highest + 1
    return WorkflowAction.objects.create(
        workflow=workflow, action_type=action_type, configuration=configuration or {}, position=position
    )


# --------------------------------------------------------------------------
# Trigger evaluation
# --------------------------------------------------------------------------


def evaluate_conditions(entity, conditions):
    """Check `entity` against a simple `{"field": ..., "equals": ...}`
    condition dict — deliberately basic (a single field-equality check,
    not a boolean expression tree), the same "basic X only, as a real
    scope boundary" discipline CP14's `generate_occurrences()`/CP15's
    `render_template()` both applied. Empty/missing `conditions` always
    matches — a trigger with no conditions fires for every entity of its
    watched type.
    """
    if not conditions:
        return True
    field = conditions.get("field")
    if not field:
        return True
    expected = conditions.get("equals")
    return getattr(entity, field, None) == expected


def trigger_matches(trigger, entity, *, event_type):
    """True if `trigger` should fire for `entity`, given `event_type`
    (one of `WorkflowTrigger.TriggerType`). Checks, in order: the trigger
    type matches the event; the entity's type matches the trigger's
    watched `content_type` (if any is set); `evaluate_conditions()`.
    """
    if trigger.trigger_type != event_type:
        return False
    if trigger.content_type_id is not None:
        from django.contrib.contenttypes.models import ContentType

        if trigger.content_type_id != ContentType.objects.get_for_model(entity).id:
            return False
    return evaluate_conditions(entity, trigger.conditions)


# --------------------------------------------------------------------------
# Action dispatch
# --------------------------------------------------------------------------

#: Every action function has the same shape: ``(action: WorkflowAction,
#: entity) -> dict`` — a small JSON-serializable summary of what happened,
#: folded into the execution's ``result_data["actions"]`` list. The same
#: "dispatch table over an if/elif chain" shape CP16's `_REPORT_COMPUTERS`
#: established, reused here for the identical reason: which code runs is
#: a runtime decision driven by stored data (`action.action_type`), not a
#: caller's choice of which function to call.
_ACTION_DISPATCHERS = {}


def _register(action_type):
    def decorator(func):
        _ACTION_DISPATCHERS[action_type] = func
        return func

    return decorator


@_register(WorkflowAction.ActionType.SEND_EMAIL)
def _run_send_email(action, entity):
    """``configuration``: ``{"template_id": <EmailTemplate pk>, "to_field":
    <attribute name on entity holding the recipient's email>}``. Routes
    through CP15's `queue_email()` — no email-sending logic duplicated
    here.
    """
    from apps.communications.models import EmailTemplate
    from apps.communications.services import queue_email

    config = action.configuration
    template = EmailTemplate.active_objects.get(pk=config["template_id"])
    to_email = getattr(entity, config.get("to_field", "email"), None)
    if not to_email:
        raise ValueError(f"Entity has no usable email at field '{config.get('to_field', 'email')}'.")

    message = queue_email(to_email, template=template, related_object=entity)
    return {"action_type": action.action_type, "email_message_id": message.id}


@_register(WorkflowAction.ActionType.CREATE_TASK)
def _run_create_task(action, entity):
    """``configuration``: ``{"title": ..., "priority": ...}`` (both
    optional — ``title`` defaults to the workflow's own name). Routes
    through CP14's `create_task()`.
    """
    from apps.activities.models import Task
    from apps.activities.services import create_task

    config = action.configuration
    title = config.get("title") or f"Follow up: {action.workflow.name}"
    priority = config.get("priority", Task.Priority.MEDIUM)

    task = create_task(title, related_object=entity, priority=priority)
    return {"action_type": action.action_type, "task_id": task.id}


@_register(WorkflowAction.ActionType.CREATE_NOTIFICATION)
def _run_create_notification(action, entity):
    """``configuration``: ``{"recipient_id": <User pk>, "title": ...,
    "message": ...}``. Routes through CP15's `create_notification()`.
    """
    from django.contrib.auth import get_user_model

    from apps.communications.models import Notification
    from apps.communications.services import create_notification

    User = get_user_model()
    config = action.configuration
    recipient = User.objects.get(pk=config["recipient_id"])
    title = config.get("title") or f"Workflow triggered: {action.workflow.name}"

    notification = create_notification(
        recipient, config.get("notification_type", Notification.NotificationType.SYSTEM), title,
        message=config.get("message", ""), related_object=entity,
    )
    return {"action_type": action.action_type, "notification_id": notification.id}


@_register(WorkflowAction.ActionType.LOG_ACTIVITY)
def _run_log_activity(action, entity):
    """``configuration``: ``{"activity_type": ..., "description": ...}``.
    Routes through CP14's `log_activity()`.
    """
    from apps.activities.models import ActivityLog
    from apps.activities.services import log_activity

    config = action.configuration
    description = config.get("description") or f"Workflow '{action.workflow.name}' ran."

    log = log_activity(entity, config.get("activity_type", ActivityLog.ActivityType.OTHER), description)
    return {"action_type": action.action_type, "activity_log_id": log.id}


# --------------------------------------------------------------------------
# Workflow execution
# --------------------------------------------------------------------------


def run_workflow(workflow, entity, *, trigger=None):
    """Run every ACTIVE `WorkflowAction` of `workflow`, in `position`
    order, against `entity`. Records one `WorkflowExecution` — COMPLETED
    with `result_data["actions"]` (one entry per action run) if every
    action succeeds, FAILED with `error_message` set on the FIRST action
    that raises (subsequent actions do not run — a workflow is a
    SEQUENCE, not an independent batch; if step 2 needs what step 1 was
    supposed to produce, running step 3 anyway would compound the
    failure). Never lets an exception propagate to the caller — same
    "a failure is a recorded fact, not a crash" contract CP15's
    `send_queued_email()`/CP16's `execute_report()` both established.
    """
    from django.contrib.contenttypes.models import ContentType

    execution = WorkflowExecution.objects.create(
        workflow=workflow,
        trigger=trigger,
        content_type=ContentType.objects.get_for_model(entity),
        object_id=entity.pk,
        status=WorkflowExecution.Status.RUNNING,
        started_at=timezone.now(),
    )

    results = []
    try:
        for action in WorkflowAction.active_objects.filter(workflow=workflow).order_by("position"):
            dispatcher = _ACTION_DISPATCHERS[action.action_type]
            results.append(dispatcher(action, entity))
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any action failure is "FAILED", not a crash
        execution.status = WorkflowExecution.Status.FAILED
        execution.error_message = str(exc)
        execution.result_data = {"actions": results}
        execution.completed_at = timezone.now()
        execution.save(update_fields=["status", "error_message", "result_data", "completed_at", "updated_at"])
        return execution

    execution.status = WorkflowExecution.Status.COMPLETED
    execution.result_data = {"actions": results}
    execution.completed_at = timezone.now()
    execution.save(update_fields=["status", "result_data", "completed_at", "updated_at"])
    return execution


def evaluate_and_run(entity, *, event_type):
    """Find every active `WorkflowTrigger` (across every active
    `Workflow`) matching `entity`/`event_type`, and `run_workflow()` each
    matched workflow once. Returns the list of resulting
    `WorkflowExecution`s (possibly empty — "no trigger matched" is not an
    error). This is the function a future signal receiver would call
    (see this module's own docstring for why none is wired up yet); it is
    ALSO exactly what a manual "run this now" caller uses, via
    `WorkflowViewSet.execute` — the same evaluation path, whether reached
    automatically in the future or manually today.
    """
    executions = []
    triggers = WorkflowTrigger.active_objects.filter(workflow__is_active=True).select_related("workflow")
    seen_workflow_ids = set()
    for trigger in triggers:
        if trigger.workflow_id in seen_workflow_ids:
            continue
        if trigger_matches(trigger, entity, event_type=event_type):
            executions.append(run_workflow(trigger.workflow, entity, trigger=trigger))
            seen_workflow_ids.add(trigger.workflow_id)
    return executions


__all__ = [
    "managed_user_ids",
    "scope_queryset_for_user",
    "create_workflow",
    "add_trigger",
    "add_action",
    "evaluate_conditions",
    "trigger_matches",
    "run_workflow",
    "evaluate_and_run",
]
