"""Tests of the Cloud Run function entry point."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from billing_disabler import main
from billing_disabler.actions import DenyServiceUsage, DetachBillingAccount
from billing_disabler.disabler import BillingDisabler
from billing_disabler.errors import BillingDisablingError, UnscopedBudgetError
from billing_disabler.log import LogEvent
from billing_disabler.notification import BudgetNotification
from tests.conftest import CloudEventFactory


@pytest.fixture
def disabler_factory() -> Iterator[MagicMock]:
    """Mock of the entry point's disabler factory."""
    with patch.object(main, "billing_disabler", return_value=MagicMock(spec=BillingDisabler)) as factory:
        yield factory


@pytest.fixture
def disabler(disabler_factory: MagicMock) -> MagicMock:
    """Disabler mock returned by the entry point's factory."""
    disabler: MagicMock = disabler_factory.return_value
    return disabler


def test_handle_budget_notification_processes_exceeded_budget(
    disabler: MagicMock,
    make_cloud_event: CloudEventFactory,
) -> None:
    """Notification of an exceeded budget is passed to the disabler."""
    cloud_event = make_cloud_event()

    main.handle_budget_notification(cloud_event)

    disabler.handle.assert_called_once_with(BudgetNotification.from_cloud_event(cloud_event))


@pytest.mark.parametrize("cost_amount", [99.99, 100.00])
def test_handle_budget_notification_ignores_budget_not_exceeded(
    disabler_factory: MagicMock,
    make_cloud_event: CloudEventFactory,
    notification_data: dict[str, Any],
    cost_amount: float,
) -> None:
    """Processing terminates without creating API clients when the budget is not exceeded."""
    notification_data["costAmount"] = cost_amount

    main.handle_budget_notification(make_cloud_event(notification_data))

    disabler_factory.assert_not_called()


def test_handle_budget_notification_discards_invalid_event(
    disabler_factory: MagicMock,
    make_cloud_event: CloudEventFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Invalid event is logged and acknowledged without creating API clients."""
    main.handle_budget_notification(make_cloud_event(encoded_data="bm90IGpzb24="))

    disabler_factory.assert_not_called()
    assert caplog.records[-1].__dict__["fields"] == {"event": LogEvent.NOTIFICATION_DISCARDED}


def test_handle_budget_notification_discards_non_retryable_error(
    disabler: MagicMock,
    make_cloud_event: CloudEventFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-retryable processing error is logged and acknowledged."""
    disabler.handle.side_effect = UnscopedBudgetError("unscoped")

    main.handle_budget_notification(make_cloud_event())

    assert caplog.records[-1].__dict__["fields"] == {"event": LogEvent.NOTIFICATION_DISCARDED}


def test_handle_budget_notification_propagates_retryable_error(
    disabler: MagicMock,
    make_cloud_event: CloudEventFactory,
) -> None:
    """Retryable error propagates, so the event is redelivered."""
    disabler.handle.side_effect = BillingDisablingError("failed")

    with pytest.raises(BillingDisablingError):
        main.handle_budget_notification(make_cloud_event())


def test_billing_disabler_wires_components(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabler executes billing detachment before service denial and honours dry-run setting."""
    monkeypatch.setenv("DRY_RUN", "false")
    main.billing_disabler.cache_clear()
    with (
        patch("google.cloud.billing.budgets_v1.BudgetServiceClient"),
        patch("google.cloud.resourcemanager_v3.ProjectsClient"),
        patch("google.cloud.billing_v1.CloudBillingClient"),
        patch("google.cloud.orgpolicy_v2.OrgPolicyClient"),
    ):
        disabler = main.billing_disabler()
    main.billing_disabler.cache_clear()

    assert [type(action) for action in disabler._actions] == [DetachBillingAccount, DenyServiceUsage]
    assert disabler._dry_run is False
