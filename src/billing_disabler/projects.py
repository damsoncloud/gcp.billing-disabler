"""Resolution of projects affected by a budget notification."""

from dataclasses import dataclass
from typing import Any

from google.cloud import resourcemanager_v3
from google.cloud.billing import budgets_v1

from billing_disabler.errors import UnscopedBudgetError
from billing_disabler.notification import BudgetNotification


@dataclass(frozen=True)
class Project:
    """GCP project identity."""

    project_id: str
    project_number: str
    display_name: str

    @property
    def name(self) -> str:
        """Project resource name."""
        return f"projects/{self.project_id}"

    def log_fields(self) -> dict[str, Any]:
        """Fields identifying the project in log entries."""
        return {
            "project_id": self.project_id,
            "project_number": self.project_number,
            "project_display_name": self.display_name,
        }


class ProjectResolver:
    """Resolves projects listed in the scope of the notification's budget.

    Budget notifications do not identify projects, so the budget's project filter is looked up.
    """

    def __init__(
        self,
        budget_client: budgets_v1.BudgetServiceClient,
        projects_client: resourcemanager_v3.ProjectsClient,
    ) -> None:
        """Initialise the resolver.

        Args:
            budget_client: Cloud Billing Budget API client.
            projects_client: Resource Manager API client.
        """
        self._budget_client = budget_client
        self._projects_client = projects_client

    def resolve(self, notification: BudgetNotification) -> list[Project]:
        """Resolve projects the notification's budget is scoped to.

        Args:
            notification: Budget notification.

        Returns:
            Projects listed in the budget's project filter.

        Raises:
            UnscopedBudgetError: The budget does not list projects, e.g. it covers the whole billing account or
                a folder. Acting on such budgets is refused to avoid disabling billing beyond the intended scope.
        """
        budget = self._budget_client.get_budget(name=notification.budget_name)
        project_names = list(budget.budget_filter.projects)
        if not project_names:
            raise UnscopedBudgetError(f"Budget {notification.budget_name} is not scoped to specific projects")
        return [self._get_project(project_name) for project_name in project_names]

    def _get_project(self, project_name: str) -> Project:
        project = self._projects_client.get_project(name=project_name)
        return Project(
            project_id=project.project_id,
            project_number=project.name.removeprefix("projects/"),
            display_name=project.display_name,
        )
