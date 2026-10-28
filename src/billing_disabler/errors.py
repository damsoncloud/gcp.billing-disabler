"""Exceptions raised while processing budget notifications."""


class NonRetryableError(Exception):
    """Error which a redelivery of the same event cannot fix, so the event must be acknowledged."""


class InvalidNotificationError(NonRetryableError):
    """Event does not conform to the budget notification format."""


class UnscopedBudgetError(NonRetryableError):
    """Budget is not scoped to explicitly listed projects."""


class BillingDisablingError(Exception):
    """Disabling billing failed for at least one project."""
