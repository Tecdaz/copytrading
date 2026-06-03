# Proposal: bootstrap-tooling

## Intent

Establish a working Python project skeleton for the `copytrading` cronjob suite. After this change lands, every subsequent change (leaderboard discovery, position copier, account tracker) can be developed, linted, type-checked, and tested with zero additional setup.

## Why now

- The repo is empty apart from `.atl/skill-registry.md` and `openspec/` skeletons.
- `openspec/config.yaml` declares pytest/ruff/mypy as "planned" and `testing.strict_tdd: false` until wired.
- `openspec/config.yaml → rules.tasks` already states: *"Always start a change with a 'bootstrap tooling' task if not yet done."*
- The detected toolchain is ready: Python 3.13.7, uv 0.10.6, SQLite 3.46.1. No system-level blockers.

## Scope

### In scope

1. **Project skeleton** — `uv init --package copytrading` to generate `pyproject.toml` and `src/` layout.
2. **Dependencies** — install runtime + dev groups declared in sdd-init:
   - Runtime: `py-clob-client`, `google-api-python-client`, `google-auth`, `python-dotenv`
   - Dev: `pytest`, `pytest-cov`, `ruff`, `mypy`
3. **Tool config (all in `pyproject.toml`)**
   - `[tool.ruff]` — line-length 100, target `src/` + `tests/`, rule set E/F/I/N/UP/B/SIM/RET.
   - `[tool.ruff.format]` — match `ruff format` defaults.
   - `[tool.mypy]` — `strict = true`, `python_version = "3.13"`.
   - `[[tool.mypy.overrides]]` for tests: relax `no-untyped-def` only.
   - `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `addopts = "-ra -q"`.
4. **Lockfile** — run `uv sync` and check in `uv.lock`.
5. **Package skeleton** — `src/copytrading/__init__.py` exposing `__version__ = "0.1.0"` and a one-line docstring.
6. **Smoke test** — `tests/test_smoke.py` that imports the package and asserts the version string.
7. **`.gitignore`** — `.venv/`, `__pycache__/`, `*.db`, `.env`, `logs/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `*.egg-info/`, `dist/`, `build/`.
8. **`.env.example`** — placeholders for `POLY_API_KEY`, `POLY_SECRET`, `POLY_PASSPHRASE`, `POLY_PRIVATE_KEY`, `GOOGLE_SHEETS_CREDENTIALS_PATH`, `GOOGLE_SHEET_ID`.
9. **`README.md`** (root) — one-paragraph description + the canonical `uv` commands.

### Out of scope

- Implementing any of the three cronjobs (leaderboard discovery, position copier, account tracker).
- CI configuration.
- SQLite schema design.
- Secrets management beyond the `.env.example` template.
- Pre-commit hooks (defer until the team requests them).

## Approach

### Step 1 — Skeleton

- `uv init --package copytrading` from the repo root.
- This creates `pyproject.toml`, `src/copytrading/__init__.py`, and a placeholder `hello.py`. Delete the placeholder after the real `__init__.py` is in place.

### Step 2 — Dependencies

- `uv add py-clob-client google-api-python-client google-auth python-dotenv`
- `uv add --dev pytest pytest-cov ruff mypy`
- Confirm `pyproject.toml → requires-python` resolves to `>=3.13,<3.14` and adjust manually if uv picks a wider range.

### Step 3 — Tool config

- Replace the generated `[project]` description with the real one.
- Add the four tool blocks listed in Scope §3.
- Add a `[[tool.mypy.overrides]]` block ignoring missing imports for the three third-party SDKs (`py_clob_client`, `googleapiclient`, `google`) — only if the strict run fails. Pre-emptively add it to keep `sdd-verify` clean.

### Step 4 — Smoke test

- `src/copytrading/__init__.py`:
  ```python
  """copytrading — Polymarket copy-trading bot."""
  from __future__ import annotations

  __version__ = "0.1.0"
  ```
- `tests/test_smoke.py`:
  ```python
  from copytrading import __version__


  def test_version_is_string() -> None:
      assert isinstance(__version__, str)
      assert __version__ == "0.1.0"
  ```

### Step 5 — `.gitignore` and `.env.example`

Author both files manually. The exact content is in the `sdd-tasks` plan (this proposal only fixes the contract).

### Step 6 — Verification

All five commands MUST exit 0 on a clean clone:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest
```

## Key decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Layout | `src/` via `uv init --package` | Forces imports through the installed package; avoids "tests import local copy" footgun. |
| Python pin | `requires-python = ">=3.13,<3.14"` | Matches the system Python (3.13.7); permits patch upgrades, blocks 3.14 surprises. |
| Linter + formatter | ruff (single tool) | Replaces black/isort/flake8; one config block, fast. |
| Type checker | mypy `strict = true` | User asked for strict; matches `rules.specs` style guidance. |
| Config location | all in `pyproject.toml` | Modern Python convention; single source of truth. |
| Test runner | pytest (no plugins beyond cov) | Matches the planned command in `openspec/config.yaml`. |
| Smoke test scope | import + version assert only | Proves the toolchain end-to-end without committing to behavior. |
| Lockfile | check `uv.lock` in | Reproducible installs; matches the uv team's recommendation. |
| Pre-commit | defer | Not requested; out of scope for a bootstrap. |

## Risks

- **`py-clob-client` API contract unverified** — this change only pins the dependency. The first change that imports it must verify the SDK surface (signing, order placement, market data).
- **Third-party stubs missing** — `google-api-python-client` ships partial stubs; `py-clob-client` and `google-auth` are usually fine but vary. Mitigation: pre-emptive `ignore_missing_imports = true` override for the three SDKs.
- **uv `init --package` flag stability** — uv 0.10.6 supports it; if behavior changes in a future uv version, fall back to `uv init` and move files manually.
- **Lockfile drift** — `uv.lock` is checked in. Future changes must run `uv lock --upgrade` deliberately, not as a side effect of `uv add`.
- **`.env.example` is not validation** — the file documents keys; it does NOT enforce presence. Real validation comes in the first change that reads the secrets.

## Rollback plan

This change creates the project skeleton only — no live data, no trading state, no external services touched. Rollback is:

- `git revert <commit>` — removes the skeleton; returns the repo to its pre-bootstrap state.
- `rm -rf .venv uv.lock` to drop the local env and lockfile if desired.
- No DB to roll back, no secrets to rotate, no cron jobs to disable.

## Acceptance criteria

- [ ] `uv sync` succeeds on a clean clone.
- [ ] `uv run pytest` runs and passes (≥ 1 test).
- [ ] `uv run ruff check .` exits 0.
- [ ] `uv run ruff format --check .` exits 0.
- [ ] `uv run mypy src tests` exits 0.
- [ ] `src/copytrading/__init__.py` exposes `__version__`.
- [ ] `.env.example` contains all six required keys.
- [ ] `.gitignore` covers every path listed in Scope §7.
- [ ] `uv.lock` is committed.

## Cronjob / risk interaction

This change does NOT touch any of the three cronjobs (`leaderboard_discovery`, `position_copier`, `account_tracker`) and does NOT interact with the 0.5% risk cap or 200 USDC starting balance. It is pure infrastructure.

## Next phase

`sdd-spec` — write the delta spec under `openspec/changes/bootstrap-tooling/specs/tooling/spec.md` capturing the smoke-test contract and tool requirements as Given/When/Then scenarios. After spec approval, `sdd-design` (lightweight — most architecture is fixed by convention) → `sdd-tasks` → `sdd-apply` → `sdd-verify` → `sdd-archive`.
