"""Actions taken on projects which exceeded their budget."""

import logging
from typing import Protocol

from google.api_core.exceptions import NotFound
from google.cloud import billing_v1, orgpolicy_v2

from billing_disabler.projects import Project

logger = logging.getLogger(__name__)


class Action(Protocol):
    """Idempotent action taken on a project which exceeded its budget."""

    def execute(self, project: Project) -> None:
        """Execute the action.

        Args:
            project: Project which exceeded its budget.
        """


class DetachBillingAccount:
    """Removes the link between the project and its billing account."""

    def __init__(self, client: billing_v1.CloudBillingClient) -> None:
        """Initialise the action.

        Args:
            client: Cloud Billing API client.
        """
        self._client = client

    def execute(self, project: Project) -> None:
        """Detach the billing account, unless billing is already disabled.

        Args:
            project: Project which exceeded its budget.
        """
        billing_info = self._client.get_project_billing_info(name=project.name)
        if not billing_info.billing_enabled:
            logger.info(
                f"Billing already disabled for project {project.project_id}",
                extra={"fields": project.log_fields()},
            )
            return
        self._client.update_project_billing_info(
            name=project.name,
            project_billing_info=billing_v1.ProjectBillingInfo(billing_account_name=""),
        )
        logger.info(
            f"Billing account {billing_info.billing_account_name} detached from project {project.project_id}",
            extra={"fields": project.log_fields()},
        )


class DenyServiceUsage:
    """Denies use of all services supported by the `gcp.restrictServiceUsage` constraint.

    The project-level policy does not inherit from parents, so it overrides any policy set higher in the hierarchy.
    An existing project-level policy for the constraint is deleted first.
    """

    CONSTRAINT = "gcp.restrictServiceUsage"

    def __init__(self, client: orgpolicy_v2.OrgPolicyClient) -> None:
        """Initialise the action.

        Args:
            client: Organization Policy API client.
        """
        self._client = client

    def execute(self, project: Project) -> None:
        """Replace the project-level policy with one denying all services.

        Args:
            project: Project which exceeded its budget.
        """
        policy_name = f"{project.name}/policies/{self.CONSTRAINT}"
        try:
            self._client.delete_policy(name=policy_name)
        except NotFound:
            pass
        else:
            logger.info(f"Existing policy {policy_name} deleted", extra={"fields": project.log_fields()})
        self._client.create_policy(
            parent=project.name,
            policy=orgpolicy_v2.Policy(
                name=policy_name,
                spec=orgpolicy_v2.PolicySpec(
                    inherit_from_parent=False,
                    rules=[orgpolicy_v2.PolicySpec.PolicyRule(deny_all=True)],
                ),
            ),
        )
        logger.info(f"Policy {policy_name} denying all services created", extra={"fields": project.log_fields()})
