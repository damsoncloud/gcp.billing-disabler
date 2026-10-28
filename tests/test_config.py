"""Tests of runtime configuration."""

import pytest

from billing_disabler.config import Settings


def test_dry_run_enabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dry-run is enabled unless explicitly turned off."""
    monkeypatch.delenv("DRY_RUN", raising=False)

    assert Settings().dry_run is True


def test_dry_run_disabled_by_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dry-run is controlled by the `DRY_RUN` environment variable."""
    monkeypatch.setenv("DRY_RUN", "false")

    assert Settings().dry_run is False
