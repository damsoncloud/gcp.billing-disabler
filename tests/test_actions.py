"""Tests of project actions."""

from unittest.mock import MagicMock, create_autospec

import pytest
from google.api_core.exceptions import NotFound
from google.cloud import billing_v1, orgpolicy_v2

from billing_disabler.actions import DenyServiceUsage, DetachBillingAccount
from billing_disabler.projects import Project

POLICY_NAME = "projects/dc-prd-app-examplecorp-a1b2/policies/gcp.restrictServiceUsage"


@pytest.fixture
def billing_client() -> MagicMock:
    """Cloud Billing API client mock."""
    return create_autospec(billing_v1.CloudBillingClient, instance=True)


@pytest.fixture
def org_policy_client() -> MagicMock:
    """Organization Policy API client mock."""
    return create_autospec(orgpolicy_v2.OrgPolicyClient, instance=True)


def test_detach_billing_account_unlinks_billing_account(billing_client: MagicMock, project: Project) -> None:
    """Billing account is detached by setting an empty billing account name."""
    billing_client.get_project_billing_info.return_value = billing_v1.ProjectBillingInfo(
        billing_account_name="billingAccounts/012345-6789AB-CDEF01",
        billing_enabled=True,
    )

    DetachBillingAccount(billing_client).execute(project)

    billing_client.get_project_billing_info.assert_called_once_with(name=project.name)
    billing_client.update_project_billing_info.assert_called_once_with(
        name=project.name,
        project_billing_info=billing_v1.ProjectBillingInfo(billing_account_name=""),
    )


def test_detach_billing_account_skips_disabled_billing(billing_client: MagicMock, project: Project) -> None:
    """Project with billing already disabled is not modified."""
    billing_client.get_project_billing_info.return_value = billing_v1.ProjectBillingInfo(billing_enabled=False)

    DetachBillingAccount(billing_client).execute(project)

    billing_client.update_project_billing_info.assert_not_called()


def test_deny_service_usage_creates_policy(org_policy_client: MagicMock, project: Project) -> None:
    """Policy denying all services, not inheriting from parents, is created."""
    org_policy_client.delete_policy.side_effect = NotFound("policy not found")

    DenyServiceUsage(org_policy_client).execute(project)

    org_policy_client.create_policy.assert_called_once_with(
        parent=project.name,
        policy=orgpolicy_v2.Policy(
            name=POLICY_NAME,
            spec=orgpolicy_v2.PolicySpec(
                inherit_from_parent=False,
                rules=[orgpolicy_v2.PolicySpec.PolicyRule(deny_all=True)],
            ),
        ),
    )


def test_deny_service_usage_deletes_existing_policy_first(org_policy_client: MagicMock, project: Project) -> None:
    """Existing project-level policy is deleted before the new one is created."""
    DenyServiceUsage(org_policy_client).execute(project)

    org_policy_client.delete_policy.assert_called_once_with(name=POLICY_NAME)
    assert [name for name, _, _ in org_policy_client.mock_calls] == ["delete_policy", "create_policy"]
