"""Tests of project resolution."""

from unittest.mock import MagicMock, create_autospec

import pytest
from google.cloud import resourcemanager_v3
from google.cloud.billing import budgets_v1

from billing_disabler.errors import UnscopedBudgetError
from billing_disabler.notification import BudgetNotification
from billing_disabler.projects import Project, ProjectResolver


@pytest.fixture
def budget_client() -> MagicMock:
    """Cloud Billing Budget API client mock."""
    return create_autospec(budgets_v1.BudgetServiceClient, instance=True)


@pytest.fixture
def projects_client() -> MagicMock:
    """Resource Manager API client mock returning a project per number."""
    client = create_autospec(resourcemanager_v3.ProjectsClient, instance=True)
    client.get_project.side_effect = lambda name: resourcemanager_v3.Project(
        name=name,
        project_id=f"project-{name.removeprefix('projects/')}",
        display_name=f"Project {name.removeprefix('projects/')}",
    )
    return client


@pytest.fixture
def resolver(budget_client: MagicMock, projects_client: MagicMock) -> ProjectResolver:
    """Resolver using client mocks."""
    return ProjectResolver(budget_client, projects_client)


def test_resolve_returns_projects_from_budget_filter(
    resolver: ProjectResolver,
    budget_client: MagicMock,
    notification: BudgetNotification,
) -> None:
    """Every project in the budget filter is resolved."""
    budget_client.get_budget.return_value = budgets_v1.Budget(
        budget_filter=budgets_v1.Filter(projects=["projects/111", "projects/222"]),
    )

    projects = resolver.resolve(notification)

    budget_client.get_budget.assert_called_once_with(name=notification.budget_name)
    assert projects == [
        Project(project_id="project-111", project_number="111", display_name="Project 111"),
        Project(project_id="project-222", project_number="222", display_name="Project 222"),
    ]


@pytest.mark.parametrize(
    "budget_filter",
    [budgets_v1.Filter(), budgets_v1.Filter(resource_ancestors=["folders/123"])],
    ids=["billing-account", "folder"],
)
def test_resolve_rejects_budget_without_projects(
    resolver: ProjectResolver,
    budget_client: MagicMock,
    projects_client: MagicMock,
    notification: BudgetNotification,
    budget_filter: budgets_v1.Filter,
) -> None:
    """Budgets not listing projects are refused."""
    budget_client.get_budget.return_value = budgets_v1.Budget(budget_filter=budget_filter)

    with pytest.raises(UnscopedBudgetError):
        resolver.resolve(notification)
    projects_client.get_project.assert_not_called()


def test_project_name(project: Project) -> None:
    """Project resource name uses the project ID."""
    assert project.name == "projects/dc-prd-app-examplecorp-a1b2"


def test_project_log_fields(project: Project) -> None:
    """Log fields identify the project."""
    assert project.log_fields() == {
        "project_id": "dc-prd-app-examplecorp-a1b2",
        "project_number": "123456789012",
        "project_display_name": "ExampleCorp",
    }
