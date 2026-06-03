# Spec: tooling (delta for core-infrastructure)

## MODIFIED Requirements

### REQ-TOOLING-2: Dependencies (MODIFIED)
Runtime dependencies SHALL include `httpx` instead of `py-clob-client`.

#### Scenario: httpx installed
- **Given** `uv sync` has been run
- **When** `import httpx` is executed
- **Then** the import MUST succeed

#### Scenario: py-clob-client removed
- **Given** `pyproject.toml`
- **When** inspecting dependencies
- **Then** `py-clob-client` MUST NOT be listed

### REQ-TOOLING-8: .env.example (MODIFIED)
`.env.example` SHALL contain exactly 2 keys for Google Sheets only.

#### Scenario: Two keys only
- **Given** the `.env.example` file
- **When** counting lines with `=`
- **Then** there MUST be exactly 2 keys: `GOOGLE_SHEETS_CREDENTIALS_PATH` and `GOOGLE_SHEET_ID`

## ADDED Requirements

### REQ-TOOLING-10: Test Fixtures
`tests/conftest.py` SHALL provide `FakeHTTPClient` and `FakeSheetsService` fixtures.

#### Scenario: Fixtures importable
- **Given** the test suite
- **When** `from tests.conftest import FakeHTTPClient, FakeSheetsService` is executed
- **Then** both classes MUST be importable
