"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    """Raised when required configuration is missing."""


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment."""

    google_sheets_credentials_path: Path
    google_sheet_id: str
    google_token_path: Path = Path(".google_token.json")

    @classmethod
    def from_env(cls) -> Settings:
        """Load settings from .env file and environment.

        Raises ConfigError if required variables are missing.
        """
        load_dotenv()

        creds_path = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_PATH")
        sheet_id = os.environ.get("GOOGLE_SHEET_ID")
        token_path = os.environ.get("GOOGLE_TOKEN_PATH", ".google_token.json")

        missing: list[str] = []
        if not creds_path:
            missing.append("GOOGLE_SHEETS_CREDENTIALS_PATH")
        if not sheet_id:
            missing.append("GOOGLE_SHEET_ID")

        if missing:
            raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")

        # At this point both values are guaranteed non-empty
        assert creds_path is not None
        assert sheet_id is not None

        return cls(
            google_sheets_credentials_path=Path(creds_path),
            google_sheet_id=sheet_id,
            google_token_path=Path(token_path),
        )
