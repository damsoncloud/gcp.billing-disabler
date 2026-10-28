"""Budget notification model.

See https://docs.cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications for the format.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal, Self

from cloudevents.http import CloudEvent
from pydantic import Base64Bytes, BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from billing_disabler.errors import InvalidNotificationError


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)


class _CamelCaseModel(_Model):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)


class BudgetAmountType(StrEnum):
    """Way the budget amount is defined."""

    SPECIFIED_AMOUNT = "SPECIFIED_AMOUNT"
    LAST_MONTH_COST = "LAST_MONTH_COST"
    LAST_PERIODS_COST = "LAST_PERIODS_COST"


class BudgetNotificationAttributes(_CamelCaseModel):
    """Pub/Sub message attributes of a budget notification."""

    billing_account_id: str
    """ID of the Cloud Billing account owning the budget."""
    budget_id: str
    """ID of the budget within the billing account."""
    schema_version: Literal["1.0"]
    """Version of the notification schema."""


class BudgetNotificationData(_CamelCaseModel):
    """Decoded Pub/Sub message data of a budget notification."""

    budget_display_name: str
    """Human-readable name of the budget."""
    cost_amount: Decimal
    """Costs accrued since the start of the budget period."""
    cost_interval_start: datetime
    """Start of the budget period."""
    budget_amount: Decimal
    """Amount allocated in the budget."""
    budget_amount_type: BudgetAmountType
    """Way the budget amount is defined."""
    currency_code: str
    """Currency of the cost and budget amounts."""
    alert_threshold_exceeded: Decimal | None = None
    """Highest exceeded actual-cost threshold as a fraction, absent if none is exceeded."""
    forecast_threshold_exceeded: Decimal | None = None
    """Highest exceeded forecasted-cost threshold as a fraction, absent if none is exceeded."""


class _PubSubMessage(_Model):
    attributes: BudgetNotificationAttributes
    """Message attributes."""
    data: Base64Bytes
    """Base64-decoded message data."""


class _PubSubEnvelope(_Model):
    message: _PubSubMessage
    """Pub/Sub message carried by the CloudEvent."""


class BudgetNotification(_Model):
    """Validated budget notification."""

    attributes: BudgetNotificationAttributes
    """Pub/Sub message attributes."""
    data: BudgetNotificationData
    """Decoded Pub/Sub message data."""

    @classmethod
    def from_cloud_event(cls, cloud_event: CloudEvent) -> Self:
        """Validate a Pub/Sub `messagePublished` CloudEvent carrying a budget notification.

        Args:
            cloud_event: Event delivered by Eventarc.

        Returns:
            Validated notification.

        Raises:
            InvalidNotificationError: The event does not conform to the budget notification format.
        """
        try:
            message = _PubSubEnvelope.model_validate(cloud_event.get_data()).message
            data = BudgetNotificationData.model_validate_json(message.data)
        except ValidationError as error:
            raise InvalidNotificationError(str(error)) from error
        return cls(attributes=message.attributes, data=data)

    @property
    def budget_name(self) -> str:
        """Budget resource name."""
        return f"billingAccounts/{self.attributes.billing_account_id}/budgets/{self.attributes.budget_id}"

    @property
    def is_budget_exceeded(self) -> bool:
        """Whether the accrued cost exceeds the budget amount."""
        return self.data.cost_amount > self.data.budget_amount

    def log_fields(self) -> dict[str, Any]:
        """Fields identifying the notification in log entries."""
        return {
            "billing_account_id": self.attributes.billing_account_id,
            "budget_id": self.attributes.budget_id,
            "budget_display_name": self.data.budget_display_name,
            "cost_amount": float(self.data.cost_amount),
            "budget_amount": float(self.data.budget_amount),
            "currency_code": self.data.currency_code,
            "cost_interval_start": self.data.cost_interval_start.isoformat(),
        }
