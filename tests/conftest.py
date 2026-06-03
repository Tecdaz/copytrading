"""Shared test fixtures and fakes."""

from __future__ import annotations

from typing import Any


class FakeHTTPResponse:
    """Fake httpx response for testing."""

    def __init__(self, json_data: Any, status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def json(self) -> Any:
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(self.status_code),
            )


class FakeHTTPClient:
    """Fake httpx.Client for testing PolyClient without network calls."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self._responses = responses or {}
        self._requests: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, url: str, params: dict[str, Any] | None = None) -> FakeHTTPResponse:
        self._requests.append((url, params))
        if url in self._responses:
            data = self._responses[url]
            if isinstance(data, Exception):
                raise data
            return FakeHTTPResponse(data)
        return FakeHTTPResponse([])

    def __enter__(self) -> FakeHTTPClient:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    @property
    def requests(self) -> list[tuple[str, dict[str, Any] | None]]:
        return self._requests


class FakeSheetsService:
    """Fake Google Sheets service for testing without API calls."""

    def __init__(self) -> None:
        self._writes: list[tuple[str, list[list[str]]]] = []
        self._appends: list[tuple[str, list[list[str]]]] = []

    def spreadsheets(self) -> FakeSheetsService:
        return self

    def values(self) -> FakeSheetsService:
        return self

    def update(
        self,
        spreadsheetId: str,  # noqa: N803 - matches Google API
        range: str,  # noqa: A002
        valueInputOption: str,  # noqa: N803 - matches Google API
        body: dict[str, Any],
    ) -> FakeSheetsService:
        self._writes.append((range, body["values"]))
        return self

    def append(
        self,
        spreadsheetId: str,  # noqa: N803 - matches Google API
        range: str,  # noqa: A002
        valueInputOption: str,  # noqa: N803 - matches Google API
        body: dict[str, Any],
    ) -> FakeSheetsService:
        self._appends.append((range, body["values"]))
        return self

    def execute(self) -> dict[str, int]:
        return {"updatedRows": 1}

    @property
    def writes(self) -> list[tuple[str, list[list[str]]]]:
        return self._writes

    @property
    def appends(self) -> list[tuple[str, list[list[str]]]]:
        return self._appends
