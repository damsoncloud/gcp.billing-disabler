"""Processing of budget notifications."""

import logging
from collections.abc import Sequence

from billing_disabler.actions import Action
from billing_disabler.errors import BillingDisablingError
from billing_disabler.log import LogEvent
from billing_disabler.notification import BudgetNotification
from billing_disabler.projects import ProjectResolver

logger = logging.getLogger(__name__)


class BillingDisabler:
    """Executes actions on projects whose budget has been exceeded."""

    def __init__(self, resolver: ProjectResolver, actions: Sequence[Action], *, dry_run: bool) -> None:
        """Initialise the disabler.

        Args:
            resolver: Resolver of projects affected by a notification.
            actions: Actions executed in order on each affected project.
            dry_run: When enabled, affected projects are only logged.
        """
        self._resolver = resolver
        self._actions = actions
        self._dry_run = dry_run

    def handle(self, notification: BudgetNotification) -> None:
        """Disable billing for projects in the scope of an exceeded budget.

        Projects are processed independently, so a failure on one does not prevent processing the others.

        Args:
            notification: Validated notification of an exceeded budget.

        Raises:
            BillingDisablingError: Actions failed for at least one project.
        """
        notification_fields = notification.log_fields()
        failed_projects = []
        for project in self._resolver.resolve(notification):
            fields = notification_fields | project.log_fields()
            if self._dry_run:
                logger.warning(
                    f"Dry-run: billing would be disabled for project {project.project_id}",
                    extra={"fields": fields | {"event": LogEvent.BILLING_DISABLING_SIMULATED}},
                )
                continue
            try:
                for action in self._actions:
                    action.execute(project)
            except Exception:
                logger.exception(
                    f"Failed to disable billing for project {project.project_id}",
                    extra={"fields": fields | {"event": LogEvent.BILLING_DISABLING_FAILED}},
                )
                failed_projects.append(project.project_id)
                continue
            logger.warning(
                f"Billing disabled for project {project.project_id}",
                extra={"fields": fields | {"event": LogEvent.BILLING_DISABLED}},
            )

        if failed_projects:
            raise BillingDisablingError(f"Failed to disable billing for projects: {', '.join(failed_projects)}")
