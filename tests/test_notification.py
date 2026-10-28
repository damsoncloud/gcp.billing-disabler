"""Tests of the budget notification model."""

from decimal import Decimal
from typing import Any

import pytest

from billing_disabler.errors import InvalidNotificationError
from billing_disabler.notification import BudgetAmountType, BudgetNotification
from tests.conftest import CloudEventFactory


def test_from_cloud_event_parses_notification(make_cloud_event: CloudEventFactory) -> None:
    """Valid event is parsed into attributes and data."""
    notification = BudgetNotification.from_cloud_event(make_cloud_event())

    assert notification.attributes.billing_account_id == "012345-6789AB-CDEF01"
    assert notification.attributes.budget_id == "de72f49d-779b-4945-a127-4d6ce8def0bb"
    assert notification.data.cost_amount == Decimal("100.01")
    assert notification.data.budget_amount == Decimal("100.00")
    assert notification.data.budget_amount_type is BudgetAmountType.SPECIFIED_AMOUNT
    assert notification.data.alert_threshold_exceeded == Decimal(1)
    assert notification.data.forecast_threshold_exceeded is None


@pytest.mark.parametrize("field", ["alertThresholdExceeded", "forecastThresholdExceeded"])
def test_from_cloud_event_accepts_missing_optional_fields(
    make_cloud_event: CloudEventFactory,
    notification_data: dict[str, Any],
    field: str,
) -> None:
    """Threshold fields are optional."""
    notification_data.pop(field, None)

    BudgetNotification.from_cloud_event(make_cloud_event(notification_data))


@pytest.mark.parametrize(
    "field",
    ["budgetDisplayName", "costAmount", "costIntervalStart", "budgetAmount", "budgetAmountType", "currencyCode"],
)
def test_from_cloud_event_rejects_missing_data_field(
    make_cloud_event: CloudEventFactory,
    notification_data: dict[str, Any],
    field: str,
) -> None:
    """Required data fields must be present."""
    del notification_data[field]

    with pytest.raises(InvalidNotificationError, match=field):
        BudgetNotification.from_cloud_event(make_cloud_event(notification_data))


@pytest.mark.parametrize("attribute", ["billingAccountId", "budgetId", "schemaVersion"])
def test_from_cloud_event_rejects_missing_attribute(
    make_cloud_event: CloudEventFactory,
    notification_attributes: dict[str, str],
    attribute: str,
) -> None:
    """All attributes must be present."""
    del notification_attributes[attribute]

    with pytest.raises(InvalidNotificationError, match=attribute):
        BudgetNotification.from_cloud_event(make_cloud_event(attributes=notification_attributes))


def test_from_cloud_event_rejects_unsupported_schema_version(
    make_cloud_event: CloudEventFactory,
    notification_attributes: dict[str, str],
) -> None:
    """Only the documented schema version is accepted."""
    notification_attributes["schemaVersion"] = "2.0"

    with pytest.raises(InvalidNotificationError, match="schemaVersion"):
        BudgetNotification.from_cloud_event(make_cloud_event(attributes=notification_attributes))


def test_from_cloud_event_rejects_unknown_budget_amount_type(
    make_cloud_event: CloudEventFactory,
    notification_data: dict[str, Any],
) -> None:
    """Budget amount type must be one of the documented values."""
    notification_data["budgetAmountType"] = "UNKNOWN"

    with pytest.raises(InvalidNotificationError, match="budgetAmountType"):
        BudgetNotification.from_cloud_event(make_cloud_event(notification_data))


@pytest.mark.parametrize("encoded_data", ["not base64!", "bm90IGpzb24="])
def test_from_cloud_event_rejects_undecodable_data(make_cloud_event: CloudEventFactory, encoded_data: str) -> None:
    """Data must be base64-encoded JSON."""
    with pytest.raises(InvalidNotificationError):
        BudgetNotification.from_cloud_event(make_cloud_event(encoded_data=encoded_data))


def test_from_cloud_event_rejects_non_pubsub_event(make_cloud_event: CloudEventFactory) -> None:
    """Event data must be a Pub/Sub message envelope."""
    cloud_event = make_cloud_event()
    cloud_event.data = {"unexpected": "payload"}

    with pytest.raises(InvalidNotificationError, match="message"):
        BudgetNotification.from_cloud_event(cloud_event)


@pytest.mark.parametrize(
    ("cost_amount", "expected"),
    [(99.99, False), (100.00, False), (100.01, True)],
)
def test_is_budget_exceeded(
    make_cloud_event: CloudEventFactory,
    notification_data: dict[str, Any],
    cost_amount: float,
    expected: bool,
) -> None:
    """Budget is exceeded only when the cost is strictly greater than the budget amount."""
    notification_data["costAmount"] = cost_amount

    assert BudgetNotification.from_cloud_event(make_cloud_event(notification_data)).is_budget_exceeded is expected


def test_budget_name(notification: BudgetNotification) -> None:
    """Budget resource name is built from attributes."""
    assert (
        notification.budget_name == "billingAccounts/012345-6789AB-CDEF01/budgets/de72f49d-779b-4945-a127-4d6ce8def0bb"
    )


def test_log_fields(notification: BudgetNotification) -> None:
    """Log fields identify the notification and its spend."""
    assert notification.log_fields() == {
        "billing_account_id": "012345-6789AB-CDEF01",
        "budget_id": "de72f49d-779b-4945-a127-4d6ce8def0bb",
        "budget_display_name": "examplecorp-budget",
        "cost_amount": 100.01,
        "budget_amount": 100.00,
        "currency_code": "EUR",
        "cost_interval_start": "2026-10-01T07:00:00+00:00",
    }
