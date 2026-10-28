"""Cloud Run function entry point."""

import functools
import logging

import functions_framework
from cloudevents.http import CloudEvent
from google.cloud import billing_v1, orgpolicy_v2, resourcemanager_v3
from google.cloud.billing import budgets_v1

from billing_disabler.actions import DenyServiceUsage, DetachBillingAccount
from billing_disabler.config import Settings
from billing_disabler.disabler import BillingDisabler
from billing_disabler.errors import NonRetryableError
from billing_disabler.log import LogEvent, configure_logging
from billing_disabler.notification import BudgetNotification
from billing_disabler.projects import ProjectResolver

configure_logging()
logger = logging.getLogger(__name__)


@functools.cache
def billing_disabler() -> BillingDisabler:
    """Build the disabler once per instance, so API clients are reused across events."""
    return BillingDisabler(
        resolver=ProjectResolver(budgets_v1.BudgetServiceClient(), resourcemanager_v3.ProjectsClient()),
        actions=[
            DetachBillingAccount(billing_v1.CloudBillingClient()),
            DenyServiceUsage(orgpolicy_v2.OrgPolicyClient()),
        ],
        dry_run=Settings().dry_run,
    )


@functions_framework.cloud_event
def handle_budget_notification(cloud_event: CloudEvent) -> None:
    """Handle a budget notification delivered as a Pub/Sub CloudEvent.

    API clients are only created for exceeded budgets, so invalid and not exceeded notifications need no credentials.
    Events which cannot be processed on redelivery are logged and acknowledged. Any other error propagates, so the
    event is redelivered according to the subscription's retry policy.

    Args:
        cloud_event: Pub/Sub `messagePublished` event.
    """
    try:
        notification = BudgetNotification.from_cloud_event(cloud_event)
        if not notification.is_budget_exceeded:
            logger.info(f"Budget {notification.budget_name} not exceeded", extra={"fields": notification.log_fields()})
            return
        billing_disabler().handle(notification)
    except NonRetryableError:
        logger.exception(
            f"Budget notification {cloud_event['id']} discarded",
            extra={"fields": {"event": LogEvent.NOTIFICATION_DISCARDED}},
        )
