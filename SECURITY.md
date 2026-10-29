# Security Policy

## Supported versions

Only the latest release of the container image (`ghcr.io/damsoncloud/gcp.billing-disabler:latest`) receives security fixes. Fixes are published as a new release, so pin to a
version you have reviewed and upgrade promptly.

## Reporting a vulnerability

Please do not report security vulnerabilities through public GitHub issues, discussions or pull requests.

Report them privately using [GitHub private vulnerability reporting](https://github.com/damsoncloud/gcp.billing-disabler/security/advisories/new). Include:

- the affected version or image digest,
- a description of the vulnerability and its impact,
- steps to reproduce or a proof of concept, if available.

We will acknowledge the report, keep you informed about its progress and credit you in the published advisory, unless you prefer to stay anonymous.

## Scope

In scope are the source code in this repository and the published container images.

Detaching billing accounts and denying service usage for projects in the scope of an exceeded budget is the intended behaviour of this tool, not a vulnerability. Reports showing
that it can act on projects outside that scope, or that it can be triggered by events other than genuine budget notifications, are in scope.

Container images are scanned for known vulnerabilities on every build and weekly after release.
