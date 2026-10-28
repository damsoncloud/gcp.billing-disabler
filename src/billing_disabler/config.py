"""Runtime configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = SettingsConfigDict(use_attribute_docstrings=True)

    dry_run: bool = True
    """Only log exceeded budgets without modifying projects; enabled by default as disabling billing is destructive."""
