# Tasks: bootstrap-tooling

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~120 (8 files; 4 new source, 1 generated lockfile, 1 pyproject edit) |
| 400-line budget risk | Low |
| Chained PRs recommended | Yes (forced by `delivery_strategy: force-chained`) |
| Suggested split | PR 1 (skeleton + deps) → PR 2 (tool config) → PR 3 (package + smoke + docs) |
| Delivery strategy | force-chained |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Working venv with runtime + dev deps and a committed `uv.lock` | PR 1 | Base: `main`. Verifies `uv sync` and `import py_clob_client`. |
| 2 | ruff / mypy / pytest wired in `pyproject.toml` and `.gitignore` finalized | PR 2 | Base: `main`. Verifies the three tool commands exit 0 against uv stubs. |
| 3 | Real `__init__.py`, smoke test, and onboarding docs | PR 3 | Base: `main`. Verifies all five commands from the proposal exit 0. |

## Phase 1: Skeleton + Dependencies (PR 1)

- [x] 1.1 Run `uv init --package copytrading` from repo root; confirm `pyproject.toml`, `src/copytrading/__init__.py`, `src/copytrading/hello.py`, `.gitignore`, and `.python-version` are created.
- [x] 1.2 Edit `pyproject.toml`: set `requires-python = ">=3.13,<3.14"` and replace `[project]` description with `"Polymarket copy-trading bot — three cronjobs + SQLite + Google Sheets."`.
- [x] 1.3 Run `uv add py-clob-client google-api-python-client google-auth python-dotenv`; confirm runtime deps land under `[project].dependencies`.
- [x] 1.4 Run `uv add --dev pytest pytest-cov ruff mypy`; confirm dev deps land under `[dependency-groups].dev`.
- [x] 1.5 Run `uv sync`; commit `pyproject.toml`, `uv.lock`, `.python-version`, and the uv-generated files.
- [x] 1.6 Verify: `uv sync` exits 0 on a clean re-run; `uv run python -c "import py_clob_client, googleapiclient, google.auth, dotenv"` exits 0; `uv run pytest --collect-only` exits 0 (zero tests collected is acceptable here).

## Phase 2: Tool Configuration (PR 2)

- [x] 2.1 Append `[tool.ruff]` and `[tool.ruff.lint]` blocks to `pyproject.toml` per design §"Interfaces / Contracts".
- [x] 2.2 Append `[tool.mypy]` block (`strict = true`, `python_version = "3.13"`) plus two `[[tool.mypy.overrides]]` entries: one for tests relaxing `disallow_untyped_defs`, one for `py_clob_client`, `googleapiclient`, `google.oauth2` setting `ignore_missing_imports = true`.
- [x] 2.3 Append `[tool.pytest.ini_options]` block with `testpaths = ["tests"]` and `addopts = "-ra -q"`.
- [x] 2.4 Replace the uv-generated `.gitignore` with the spec contract (`.venv/`, `__pycache__/`, `*.db`, `.env`, `logs/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `*.egg-info/`, `dist/`, `build/`).
- [x] 2.5 Verify: `uv run ruff check .` exits 0; `uv run mypy src` exits 0 against the uv stubs; `uv run pytest --collect-only` exits 0; `git check-ignore .env` reports ignored.

## Phase 3: Package + Smoke Test (PR 3)

- [x] 3.1 Replace `src/copytrading/__init__.py` with the contract: docstring `"""copytrading — Polymarket copy-trading bot."""`, `from __future__ import annotations`, and `__version__ = "0.1.0"`.
- [x] 3.2 Delete `src/copytrading/hello.py` (uv placeholder; no longer needed). [no-op: file does not exist in newer uv]
- [x] 3.3 Create `tests/test_smoke.py` containing `test_version_is_string` that imports `from copytrading import __version__` and asserts it is a `str` equal to `"0.1.0"`.

## Phase 4: Developer Docs (PR 3, same branch)

- [x] 4.1 Create `.env.example` with empty placeholders for `POLY_API_KEY`, `POLY_SECRET`, `POLY_PASSPHRASE`, `POLY_PRIVATE_KEY`, `GOOGLE_SHEETS_CREDENTIALS_PATH`, `GOOGLE_SHEET_ID` (one comment line per key).
- [x] 4.2 Create `README.md` with the one-paragraph project description and the five canonical `uv` commands (`uv sync`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`, `uv run mypy src tests`).
- [x] 4.3 Verify all five commands from the proposal's Step 6 exit 0 on this PR's tip; smoke test reports `1 passed`.
