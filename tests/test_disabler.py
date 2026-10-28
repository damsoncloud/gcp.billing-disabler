"""Tests of budget notification processing."""

from unittest.mock import MagicMock, create_autospec

import pytest

from billing_disabler.actions import Action
from billing_disabler.disabler import BillingDisabler
from billing_disabler.errors import BillingDisablingError
from billing_disabler.log import LogEvent
from billing_disabler.notification import BudgetNotification
from billing_disabler.projects import Project, ProjectResolver

OTHER_PROJECT = Project(project_id="dc-prd-app-examplecorp-c3d4", project_number="210987654321", display_name="Other")


@pytest.fixture
def resolver(project: Project) -> MagicMock:
    """Resolver mock returning two projects."""
    resolver = create_autospec(ProjectResolver, instance=True)
    resolver.resolve.return_value = [project, OTHER_PROJECT]
    return resolver


@pytest.fixture
def actions() -> list[MagicMock]:
    """Action mocks."""
    return [create_autospec(Action, instance=True), create_autospec(Action, instance=True)]


def events(caplog: pytest.LogCaptureFixture) -> list[tuple[str, str]]:
    """Return `(event, project_id)` of captured records which carry an event."""
    return [
        (record.__dict__["fields"]["event"], record.__dict__["fields"]["project_id"])
        for record in caplog.records
        if "event" in record.__dict__.get("fields", {})
    ]


def test_handle_executes_actions_on_each_project(
    resolver: MagicMock,
    actions: list[MagicMock],
    notification: BudgetNotification,
    project: Project,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """All actions are executed on all projects and success is logged per project."""
    BillingDisabler(resolver, actions, dry_run=False).handle(notification)

    for action in actions:
        assert [c.args for c in action.execute.call_args_list] == [(project,), (OTHER_PROJECT,)]
    assert events(caplog) == [
        (LogEvent.BILLING_DISABLED, project.project_id),
        (LogEvent.BILLING_DISABLED, OTHER_PROJECT.project_id),
    ]


def test_handle_dry_run_only_logs(
    resolver: MagicMock,
    actions: list[MagicMock],
    notification: BudgetNotification,
    project: Project,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dry-run resolves projects and logs them without executing actions."""
    BillingDisabler(resolver, actions, dry_run=True).handle(notification)

    for action in actions:
        action.execute.assert_not_called()
    assert events(caplog) == [
        (LogEvent.BILLING_DISABLING_SIMULATED, project.project_id),
        (LogEvent.BILLING_DISABLING_SIMULATED, OTHER_PROJECT.project_id),
    ]


def test_handle_continues_after_project_failure(
    resolver: MagicMock,
    actions: list[MagicMock],
    notification: BudgetNotification,
    project: Project,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failure on one project stops its remaining actions, but other projects are processed before raising."""
    actions[0].execute.side_effect = [RuntimeError("API error"), None]

    with pytest.raises(BillingDisablingError, match=project.project_id):
        BillingDisabler(resolver, actions, dry_run=False).handle(notification)

    assert [c.args for c in actions[1].execute.call_args_list] == [(OTHER_PROJECT,)]
    assert events(caplog) == [
        (LogEvent.BILLING_DISABLING_FAILED, project.project_id),
        (LogEvent.BILLING_DISABLED, OTHER_PROJECT.project_id),
    ]


def test_handle_logs_notification_and_project_fields(
    resolver: MagicMock,
    actions: list[MagicMock],
    notification: BudgetNotification,
    project: Project,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Event log entries carry notification and project fields for alerting."""
    BillingDisabler(resolver, actions, dry_run=False).handle(notification)

    record = next(r for r in caplog.records if r.__dict__.get("fields", {}).get("event") == LogEvent.BILLING_DISABLED)
    assert record.levelname == "WARNING"
    assert record.__dict__["fields"] == notification.log_fields() | project.log_fields() | {
        "event": LogEvent.BILLING_DISABLED,
    }
