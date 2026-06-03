"""Google Sheets client with OAuth2 authentication."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from copytrading.config import Settings
from copytrading.models import AccountSnapshot, PaperTrade, Wallet

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TOKEN_FILE = ".google_token.json"


class SheetsClientError(Exception):
    """Raised when Google Sheets API operations fail."""


class SheetsClient:
    """Client for writing data to Google Sheets using OAuth2."""

    def __init__(self, service: Any, sheet_id: str) -> None:
        self._service = service
        self._sheet_id = sheet_id

    @classmethod
    def from_settings(cls, settings: Settings) -> SheetsClient:
        """Create a SheetsClient using OAuth2 credentials.

        Uses the client secret file from settings to authenticate.
        Tokens are cached in .google_token.json for subsequent runs.
        """
        creds = cls._get_credentials(settings.google_sheets_credentials_path)
        try:
            service = build("sheets", "v4", credentials=creds)
        except Exception as e:
            raise SheetsClientError(f"Failed to build Sheets service: {e}") from e

        return cls(service, settings.google_sheet_id)

    @classmethod
    def _get_credentials(cls, client_secret_path: Path) -> Credentials:
        """Load or refresh OAuth2 credentials."""
        creds: Credentials | None = None
        token_path = Path(TOKEN_FILE)

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)  # type: ignore[no-untyped-call]

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())  # type: ignore[no-untyped-call]
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
                creds = flow.run_local_server(port=0)

            token_path.write_text(creds.to_json())

        return creds

    def update_leaderboard(self, wallets: list[Wallet]) -> None:
        """Write wallet data to the 'leaderboard' sheet."""
        values: list[list[str]] = [["Rank", "Address", "Total PnL", "Last Checked", "Profile Link"]]
        for w in wallets:
            values.append(
                [
                    str(w.rank),
                    w.address,
                    str(w.total_pnl),
                    w.last_checked_at.isoformat() if w.last_checked_at else "",
                    w.profile_url,
                ]
            )

        self._write_range("leaderboard!A1", values)

    def append_trades(self, trades: list[PaperTrade]) -> None:
        """Append paper trades to the 'history' sheet."""
        if not trades:
            return

        values: list[list[str]] = []
        for t in trades:
            values.append(
                [
                    t.opened_at.isoformat() if t.opened_at else "",
                    t.copied_from_wallet,
                    t.market_condition_id,
                    t.side,
                    str(t.size),
                    str(t.entry_price),
                    str(t.exit_price) if t.exit_price else "",
                    t.status,
                    str(t.pnl),
                    t.closed_at.isoformat() if t.closed_at else "",
                ]
            )

        self._append_range("history", values)

    def ensure_history_header(self) -> None:
        """Write the header row to the 'history' sheet if A1 is empty."""
        result = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._sheet_id, range="history!A1:A1")
            .execute()
        )
        existing = result.get("values", [])
        if existing and existing[0]:
            return  # header already present

        self._write_range(
            "history!A1",
            [
                [
                    "Opened At",
                    "Wallet",
                    "Market",
                    "Side",
                    "Size",
                    "Entry Price",
                    "Exit Price",
                    "Status",
                    "PnL",
                    "Closed At",
                ]
            ],
        )

    def update_account(self, snapshot: AccountSnapshot) -> None:
        """Write account summary to the 'account' sheet."""
        values: list[list[str]] = [
            ["Timestamp", "Equity", "Open Trades", "Total PnL"],
            [
                snapshot.snapshot_at.isoformat()
                if snapshot.snapshot_at
                else datetime.now(UTC).isoformat(),
                str(snapshot.equity),
                str(snapshot.open_trades),
                str(snapshot.total_pnl),
            ],
        ]

        self._write_range("account!A1", values)

    def _write_range(self, range_name: str, values: list[list[str]]) -> None:
        """Write values to a specific range."""
        try:
            self._service.spreadsheets().values().update(
                spreadsheetId=self._sheet_id,
                range=range_name,
                valueInputOption="RAW",
                body={"values": values},
            ).execute()
        except HttpError as e:
            raise SheetsClientError(f"Failed to write to {range_name}: {e}") from e

    def _append_range(self, sheet_name: str, values: list[list[str]]) -> None:
        """Append values to the end of a sheet."""
        try:
            self._service.spreadsheets().values().append(
                spreadsheetId=self._sheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body={"values": values},
            ).execute()
        except HttpError as e:
            raise SheetsClientError(f"Failed to append to {sheet_name}: {e}") from e
