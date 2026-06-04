"""Google Sheets client with OAuth2 authentication."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from copytrading.config import Settings
from copytrading.models import AccountSnapshot, PaperTrade, Wallet

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# HTTP statuses worth retrying (transient server errors + rate limits)
RETRYABLE_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}

DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF_SECONDS = 1.0
DEFAULT_BACKOFF_MULTIPLIER = 2.0


def _is_retryable(exc: BaseException) -> bool:
    """Return True if the exception represents a transient failure worth retrying."""
    if isinstance(exc, (ConnectionError, OSError, TimeoutError)):
        return True
    if isinstance(exc, httplib2.error.ServerNotFoundError):
        return True
    if isinstance(exc, HttpError):
        try:
            return int(exc.resp.status) in RETRYABLE_HTTP_STATUSES
        except (AttributeError, TypeError, ValueError):
            return False
    return False


class SheetsClientError(Exception):
    """Raised when Google Sheets API operations fail."""


class SheetsClient:
    """Client for writing data to Google Sheets using OAuth2.

    All API calls retry on transient errors (DNS, 5xx, rate limit) with
    exponential backoff. Non-transient errors (4xx) fail fast.
    """

    def __init__(
        self,
        service: Any,
        sheet_id: str,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF_SECONDS,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        sleep: Any = time.sleep,
    ) -> None:
        self._service = service
        self._sheet_id = sheet_id
        self._max_retries = max_retries
        self._initial_backoff = initial_backoff
        self._backoff_multiplier = backoff_multiplier
        self._sleep = sleep  # injectable for tests

    @classmethod
    def from_settings(cls, settings: Settings) -> SheetsClient:
        """Create a SheetsClient using OAuth2 credentials.

        Uses the client secret file from settings to authenticate.
        Tokens are cached in the path specified by settings.google_token_path.
        """
        creds = cls._get_credentials(
            settings.google_sheets_credentials_path, settings.google_token_path
        )
        try:
            service = build("sheets", "v4", credentials=creds)
        except Exception as e:
            raise SheetsClientError(f"Failed to build Sheets service: {e}") from e

        return cls(service, settings.google_sheet_id)

    @classmethod
    def _get_credentials(cls, client_secret_path: Path, token_path: Path) -> Credentials:
        """Load or refresh OAuth2 credentials.

        Args:
            client_secret_path: Path to OAuth client secret JSON (for first-time auth).
            token_path: Path to cached token JSON (used for refresh in headless envs).
        """
        creds: Credentials | None = None

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)  # type: ignore[no-untyped-call]

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # Headless: refresh without browser
                creds.refresh(Request())  # type: ignore[no-untyped-call]
            else:
                # First-time auth: requires browser
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
                creds = flow.run_local_server(port=0)

            token_path.write_text(creds.to_json())

        return creds

    def ensure_sheet_exists(self, sheet_name: str) -> None:
        """Create a tab if it doesn't exist (idempotent)."""
        try:
            meta = self._execute_with_retry(
                self._service.spreadsheets().get(spreadsheetId=self._sheet_id),
                operation="get spreadsheet metadata",
            )
            existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
            if sheet_name in existing:
                return

            self._execute_with_retry(
                self._service.spreadsheets().batchUpdate(
                    spreadsheetId=self._sheet_id,
                    body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
                ),
                operation=f"add sheet {sheet_name}",
            )
            logger.info("Created new sheet tab: %s", sheet_name)
        except Exception as e:
            # If we can't ensure, just log — the header write will fail loudly
            logger.warning("Could not ensure sheet %s exists: %s", sheet_name, e)

    def update_leaderboard(self, wallets: list[Wallet]) -> None:
        """Write wallet data to the 'leaderboard' sheet."""
        self.ensure_sheet_exists("leaderboard")
        values: list[list[str]] = [
            [
                "Rank",
                "Address",
                "Username",
                "X Username",
                "Verified",
                "Total PnL",
                "Volume",
                "Profile Image",
                "Last Checked",
                "Profile Link",
            ]
        ]
        for w in wallets:
            values.append(
                [
                    str(w.rank),
                    w.address,
                    w.username,
                    w.x_username,
                    "TRUE" if w.verified_badge else "FALSE",
                    str(w.total_pnl),
                    str(w.volume),
                    w.profile_image,
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
                    t.market_url,
                    str(t.wallet_avg_price),
                    str(t.wallet_cur_price),
                    str(t.initial_value),
                    str(t.current_value),
                    str(t.total_bought),
                    str(t.realized_pnl),
                    str(t.percent_pnl),
                    str(t.percent_realized_pnl),
                    "TRUE" if t.redeemable else "FALSE",
                    "TRUE" if t.mergeable else "FALSE",
                    t.market_title,
                    t.market_slug,
                    t.market_icon,
                    t.event_id,
                    t.event_slug,
                    t.end_date,
                    "TRUE" if t.negative_risk else "FALSE",
                    t.opposite_outcome,
                    t.opposite_asset,
                    t.asset_token_id,
                ]
            )

        self._append_range("history", values)

    def ensure_history_header(self) -> None:
        """Write the header row to the 'history' sheet if A1 is empty."""
        self.ensure_sheet_exists("history")
        result = self._execute_with_retry(
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._sheet_id, range="history!A1:A1"),
            operation="ensure_history_header.get",
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
                    "Market Link",
                    "Wallet Avg Price",
                    "Wallet Cur Price",
                    "Initial Value",
                    "Current Value",
                    "Total Bought",
                    "Realized PnL",
                    "Percent PnL",
                    "Percent Realized PnL",
                    "Redeemable",
                    "Mergeable",
                    "Market Title",
                    "Market Slug",
                    "Market Icon",
                    "Event ID",
                    "Event Slug",
                    "End Date",
                    "Negative Risk",
                    "Opposite Outcome",
                    "Opposite Asset",
                    "Asset Token ID",
                ]
            ],
        )

    def update_account(self, snapshot: AccountSnapshot) -> None:
        """Write account summary to the 'account' sheet."""
        self.ensure_sheet_exists("account")
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

    def update_live_positions(self, rows: list[list[str]]) -> None:
        """Rewrite the 'positions' tab with the latest live data.

        Overwrites the same cells every minute so prices and PnL update
        in place rather than appending new rows.
        """
        values: list[list[str]] = [
            [
                "Trade ID",
                "Opened At",
                "Wallet",
                "Market",
                "Side",
                "Size",
                "Entry Price",
                "Current Price",
                "Unrealized PnL",
                "Updated At",
                "Wallet Avg Price",
                "Asset Token ID",
            ]
        ]
        values.extend(rows)
        self._write_range("positions!A1", values)

    def ensure_positions_header(self) -> None:
        """Write the header row to the 'positions' sheet if A1 is empty."""
        self.ensure_sheet_exists("positions")
        result = self._execute_with_retry(
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._sheet_id, range="positions!A1:A1"),
            operation="ensure_positions_header.get",
        )
        existing = result.get("values", [])
        if existing and existing[0]:
            return  # header already present

        self._write_range(
            "positions!A1",
            [
                [
                    "Trade ID",
                    "Opened At",
                    "Wallet",
                    "Market",
                    "Side",
                    "Size",
                    "Entry Price",
                    "Current Price",
                    "Unrealized PnL",
                    "Updated At",
                    "Wallet Avg Price",
                    "Asset Token ID",
                ]
            ],
        )

    def _write_range(self, range_name: str, values: list[list[str]]) -> None:
        """Write values to a specific range."""
        self._execute_with_retry(
            self._service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self._sheet_id,
                range=range_name,
                valueInputOption="RAW",
                body={"values": values},
            ),
            operation=f"write {range_name}",
        )

    def _append_range(self, sheet_name: str, values: list[list[str]]) -> None:
        """Append values to the end of a sheet."""
        self._execute_with_retry(
            self._service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self._sheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body={"values": values},
            ),
            operation=f"append {sheet_name}",
        )

    def _execute_with_retry(self, request: Any, operation: str) -> dict[str, Any]:
        """Execute a Google Sheets API request with exponential backoff on transient errors.

        Retries up to max_retries times on connection errors, DNS failures,
        and HTTP 5xx / 429. Non-retryable errors (e.g. 400) fail fast.
        """
        backoff = self._initial_backoff
        attempts = self._max_retries + 1
        last_error: BaseException | None = None

        for attempt in range(1, attempts + 1):
            try:
                result: dict[str, Any] = request.execute()
                return result
            except Exception as e:
                last_error = e
                if not _is_retryable(e) or attempt == attempts:
                    break
                logger.warning(
                    "Google Sheets %s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                    operation,
                    attempt,
                    attempts,
                    e,
                    backoff,
                )
                self._sleep(backoff)
                backoff *= self._backoff_multiplier

        # Exhausted retries or non-retryable error
        if last_error is not None and _is_retryable(last_error):
            error_msg = (
                f"Google Sheets {operation} failed after {attempts} attempt(s): {last_error}"
            )
        else:
            error_msg = f"Google Sheets {operation} failed: {last_error}"
        raise SheetsClientError(error_msg) from last_error
