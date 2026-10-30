# Automated GCP Project Billing Disabling

An event-driven Cloud Run function which disables billing for Google Cloud projects whose budget has been exceeded. It is triggered by
[programmatic budget notifications](https://docs.cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications) and is published as a container image to
GitHub Packages.

> [!WARNING]
> Disabling billing is destructive. Paid services in the affected projects stop and resources may be deleted irrecoverably, see
> [Disable billing for a project](https://docs.cloud.google.com/billing/docs/how-to/modify-project#disable_billing_for_a_project). Read
> [Risks and limitations](#risks-and-limitations) before enabling it, and start with the default dry-run mode.

## How it works

For every budget notification, the function:

1. Validates the event against the budget notification format. Invalid events are logged and acknowledged.
2. Compares the cost with the budget amount. Unless the cost is strictly greater, it logs the notification and stops; no Google Cloud APIs are called.
3. Reads the budget and resolves the projects listed in its project filter. Budgets not listing projects, e.g. covering a whole billing account or folder, are
   refused and logged.
4. In dry-run mode, logs each project which would be affected and stops.
5. Otherwise, for each project:
   1. detaches the project from its billing account, unless billing is already disabled,
   2. deletes any existing project-level organisation policy for the `gcp.restrictServiceUsage` constraint,
   3. creates a project-level policy for that constraint which denies all supported services and does not inherit from parents,
   4. logs the result.

Projects are processed independently. If any of them fails, the function returns an error after processing the others, so Pub/Sub redelivers the notification;
all actions are idempotent.

## Risks and limitations

* Disabling billing stops paid services and may lead to deletion of resources and data.
* Cost data and budget notifications are delayed, so spend can exceed the budget before billing is disabled. This is a cost limiting measure, not a hard cap.
* All projects in a budget's scope are affected, even when the spend comes from one of them.
* An existing project-level `gcp.restrictServiceUsage` policy is deleted without a backup. Record it before deployment if it needs restoring.
* The denying policy stays in place after billing is re-enabled, until it is deleted.
* Budgets keep notifying for the rest of the budget period. Re-enabling billing while the cost still exceeds the budget leads to billing being disabled again with
  the next notification.
* Billing cannot be disabled for projects locked to their billing account.

### Recovery

1. (OPTIONAL) Prevent repeated disabling: increase the budget amount or remove the project from the budget's scope.
2. Delete the denying policy: `gcloud org-policies delete gcp.restrictServiceUsage --project=PROJECT_ID`, and re-create any policy which existed before.
3. Link the billing account again: `gcloud billing projects link PROJECT_ID --billing-account=BILLING_ACCOUNT_ID`.

## Deployment

The image is available without authentication as `ghcr.io/damsoncloud/gcp.billing-disabler`, tagged with each release version (e.g. `1.1.2`), its `major.minor`
(`1.1`) and `major` (`1`) versions, and `latest`. Pin a reviewed version.

Deploy it as a Cloud Run function triggered by the Pub/Sub topic connected to the budgets, i.e. with an Eventarc trigger for the
`google.cloud.pubsub.topic.v1.messagePublished` event. Failed invocations are redelivered according to the subscription's retry policy, so configure its message
retention and, optionally, a dead-letter topic.

### Configuration

| Environment variable | Default | Description |
| --- | --- | --- |
| `DRY_RUN` | `true` | Only logs projects which would be affected. Set to `false` to disable billing. |
| `PORT` | `8080` | Port the function listens on; set by Cloud Run. |

### Permissions

The function's service account needs the following permissions, as documented for the
[Budget API](https://docs.cloud.google.com/billing/docs/reference/budget/rest/v1/billingAccounts.budgets/get),
[Cloud Billing API](https://docs.cloud.google.com/billing/docs/how-to/modify-project) and
[Organization Policy API](https://docs.cloud.google.com/resource-manager/docs/organization-policy/creating-managing-policies).

| Action | Permissions | Granted on | Smallest predefined role |
| --- | --- | --- | --- |
| Read budgets | `billing.budgets.get` | Billing accounts | Billing Account Viewer |
| Resolve projects and read their billing information | `resourcemanager.projects.get` | Projects | Browser |
| Detach billing accounts | `resourcemanager.projects.deleteBillingAssignment` | Projects | Project Billing Manager |
| Replace organisation policies | `orgpolicy.policies.create`, `orgpolicy.policies.delete` | Organisation | Organization Policy Administrator |

> [!IMPORTANT]
> The Organization Policy Administrator role can only be granted on the organisation, which lets the service account set any organisation policy on any resource. A
> custom role with only the two `orgpolicy.policies` permissions, granted on the affected folders or projects, may narrow this down, but has not been verified.

The identity invoking the function, e.g. the Eventarc trigger's service account, needs `roles/run.invoker` on the Cloud Run service.

## Logging and alerting

The function writes structured JSON logs, which Cloud Logging stores as `jsonPayload`. Entries relevant for alerting carry an `event` field:

| `event` | Severity | Meaning |
| --- | --- | --- |
| `billing_disabled` | `WARNING` | Billing was disabled and the denying policy created for a project. |
| `billing_disabling_simulated` | `WARNING` | Dry-run: billing would have been disabled for a project. |
| `billing_disabling_failed` | `ERROR` | Disabling billing failed for a project; the notification is redelivered. |
| `notification_discarded` | `ERROR` | The event was invalid or the budget is not scoped to projects; it is not retried. |

The entries also contain `billing_account_id`, `budget_id`, `budget_display_name`, `cost_amount`, `budget_amount`, `currency_code` and `cost_interval_start`, and
for project-related events `project_id`, `project_number` and `project_display_name`. For example, a log-based alert on disabled billing uses the filter
`jsonPayload.event="billing_disabled"`.

## Development

The repository uses [devenv](https://devenv.sh) with the shared [devenvbase](https://github.com/damsoncloud/dcp.sdlc/blob/main/devenvbase/README.md) from
[dcp.sdlc](https://github.com/damsoncloud/dcp.sdlc).

* `devenv shell` starts the shell.
* `devenv test` runs the git hooks and the unit tests, which require 100% coverage.

### Running locally

* `function_run` runs the function on `127.0.0.1:8080`, in dry-run mode unless `DRY_RUN=false` is set.
* `function_test` sends budget notification scenarios from [`tests/http/budget_notifications.http`](tests/http/budget_notifications.http) with
  [httpyac](https://httpyac.github.io): pick one interactively, or use `--all`, `-n <name>` or `-t <tag>`.
  * Scenarios tagged `offline` need neither credentials nor API access.
  * Scenarios tagged `gcp` resolve projects through Google Cloud APIs and need Application Default Credentials and real IDs:
    `BILLING_ACCOUNT_ID=<id> BUDGET_ID=<id> function_test -t gcp`.
  * A deployed, IAM-protected function is tested with
    `BASE_URL=https://<service>.run.app ID_TOKEN=$(gcloud auth print-identity-token) function_test -t offline`.

### Container image

The [`Containerfile`](Containerfile) builds the image with the Python and uv versions of the devenv environment. The devenvbase container image module provides:

* `image_build` builds the image,
* `image_test` runs the `offline` scenarios against the image, without credentials,
* `image_scan` scans the image for vulnerabilities with Trivy,
* `image_run` runs the image locally, passing `DRY_RUN` and Application Default Credentials when present.

## CI/CD and releases

The workflows call [dcp.sdlc's reusable workflows](https://github.com/damsoncloud/dcp.sdlc#reusable-workflows):

* [`cicd.yaml`](.github/workflows/cicd.yaml) tests, builds, smoke-tests and scans the image for every pull request and push to `main`.
* [`release.yaml`](.github/workflows/release.yaml), dispatched manually on `main` with the part of the version to increase, releases a new version: it publishes the
  image to GitHub Packages, creates a GitHub release and opens a pull request bumping the version in `pyproject.toml`.
* [`scan.yaml`](.github/workflows/scan.yaml) scans the `latest` published image weekly; results appear under Security, Code scanning.
* [`dcp-sdlc-check.yaml`](.github/workflows/dcp-sdlc-check.yaml) opens an issue when a newer dcp.sdlc release is available; upgrade with
  `devenv shell -- dcp_sdlc_upgrade_pr`.

Dependabot keeps Python dependencies and GitHub Actions up to date.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.
