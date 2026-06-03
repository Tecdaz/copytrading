"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from copytrading.config import ConfigError, Settings


class TestSettings:
    def test_from_env_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "/tmp/creds.json")
        monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet123")

        settings = Settings.from_env()

        assert settings.google_sheets_credentials_path == Path("/tmp/creds.json")
        assert settings.google_sheet_id == "sheet123"

    def test_from_env_missing_sheet_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "/tmp/creds.json")
        monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)

        with pytest.raises(ConfigError, match="GOOGLE_SHEET_ID"):
            Settings.from_env()

    def test_from_env_missing_creds_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_SHEETS_CREDENTIALS_PATH", raising=False)
        monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet123")

        with pytest.raises(ConfigError, match="GOOGLE_SHEETS_CREDENTIALS_PATH"):
            Settings.from_env()

    def test_from_env_missing_both(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_SHEETS_CREDENTIALS_PATH", raising=False)
        monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)

        with pytest.raises(ConfigError, match="GOOGLE_SHEETS_CREDENTIALS_PATH"):
            Settings.from_env()

    def test_credentials_path_is_path_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "/some/path.json")
        monkeypatch.setenv("GOOGLE_SHEET_ID", "abc")

        settings = Settings.from_env()

        assert isinstance(settings.google_sheets_credentials_path, Path)

    def test_settings_is_frozen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "/tmp/c.json")
        monkeypatch.setenv("GOOGLE_SHEET_ID", "x")

        settings = Settings.from_env()

        with pytest.raises(AttributeError):
            settings.google_sheet_id = "other"  # type: ignore[misc]

    def test_no_poly_credentials_referenced(self) -> None:
        """Settings class should not reference any POLY_* variables."""
        import inspect

        source = inspect.getsource(Settings)
        assert "POLY_" not in source
