"""Shared fixtures."""

import base64
import json
from collections.abc import Callable
from typing import Any

import pytest
from cloudevents.http import CloudEvent

from billing_disabler.notification import BudgetNotification
from billing_disabler.projects import Project

type CloudEventFactory = Callable[..., CloudEvent]


@pytest.fixture
def notification_data() -> dict[str, Any]:
    """Budget notification data of an exceeded budget."""
    return {
        "budgetDisplayName": "examplecorp-budget",
        "alertThresholdExceeded": 1.0,
        "costAmount": 100.01,
        "costIntervalStart": "2026-10-01T07:00:00Z",
        "budgetAmount": 100.00,
        "budgetAmountType": "SPECIFIED_AMOUNT",
        "currencyCode": "EUR",
    }


@pytest.fixture
def notification_attributes() -> dict[str, str]:
    """Budget notification Pub/Sub message attributes."""
    return {
        "billingAccountId": "012345-6789AB-CDEF01",
        "budgetId": "de72f49d-779b-4945-a127-4d6ce8def0bb",
        "schemaVersion": "1.0",
    }


@pytest.fixture
def make_cloud_event(notification_data: dict[str, Any], notification_attributes: dict[str, str]) -> CloudEventFactory:
    """Factory of Pub/Sub CloudEvents, defaulting to a valid budget notification."""

    def factory(
        data: dict[str, Any] | None = None,
        attributes: dict[str, str] | None = None,
        encoded_data: str | None = None,
    ) -> CloudEvent:
        payload = data if data is not None else notification_data
        return CloudEvent(
            {
                "type": "google.cloud.pubsub.topic.v1.messagePublished",
                "source": "//pubsub.googleapis.com/projects/examplecorp/topics/budgets",
                "id": "event-id",
            },
            {
                "message": {
                    "attributes": attributes if attributes is not None else notification_attributes,
                    "data": encoded_data or base64.b64encode(json.dumps(payload).encode()).decode(),
                    "messageId": "message-id",
                    "publishTime": "2026-10-28T10:00:00Z",
                },
                "subscription": "projects/examplecorp/subscriptions/budgets",
            },
        )

    return factory


@pytest.fixture
def notification(make_cloud_event: CloudEventFactory) -> BudgetNotification:
    """Notification of an exceeded budget."""
    return BudgetNotification.from_cloud_event(make_cloud_event())


@pytest.fixture
def project() -> Project:
    """Project in the budget scope."""
    return Project(project_id="dc-prd-app-examplecorp-a1b2", project_number="123456789012", display_name="ExampleCorp")
