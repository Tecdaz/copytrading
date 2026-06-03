# Design: bootstrap-tooling

## Technical Approach

Pure infrastructure change. Run `uv init --package`, declare runtime + dev
dependencies, wire `ruff` / `mypy` / `pytest` inside `pyproject.toml`, drop a
single smoke test, and seed the developer-facing files (`.gitignore`,
`.env.example`, `README.md`). No domain code, no live state, no trading logic.
The package will host three future cronjob modules under `src/copytrading/`
(`leaderboard/`, `copier/`, `tracker/`) plus shared infra
(`store/`, `sheets/`, `config.py`). This change reserves the namespace only.

## Architecture Decisions

| # | Decision | Choice | Alternative | Tradeoff | Rationale |
|---|----------|--------|-------------|----------|-----------|
| 1 | Layout | `src/` via `uv init --package` | Flat | Forces install-before-test; small REPL cost | Catches the "tests import local copy" footgun; standard for libraries. |
| 2 | Config location | `pyproject.toml` only | Split into `ruff.toml` / `mypy.ini` | Splits truth across files | PEP 621 + ruff/mypy/pytest all read it natively. One PR, one file. |
| 3 | Python pin | `>=3.13,<3.14` | `>=3.12` (broader), `==3.13.*` | Wider = friendlier; narrower = safer | Matches system (3.13.7); permits patches, blocks 3.14 surprises. |
| 4 | Linter + formatter | `ruff` (one tool, both roles) | `black` + `isort` + `flake8` | Less battle-tested formatters | One config, one binary, ~10× faster. Matches `openspec/config.yaml` planned entries. |
| 5 | Type checker | `mypy --strict` + per-module overrides for 3rd-party SDKs | `pyright`, ruff type rules | mypy slower than pyright | User requested strict; config already declares mypy. Pre-emptive `ignore_missing_imports = true` for `py_clob_client`, `googleapiclient`, `google` so `sdd-verify` does not fail on stub gaps. |
| 6 | Test runner | `pytest` + `pytest-cov` only | `unittest`, pytest + xdist/mock | More plugins = more config | Matches the planned command in `openspec/config.yaml`. |
| 7 | Version source | Static `__version__` string in `__init__.py` | Dynamic via `importlib.metadata` | Dynamic = single source; static = simpler | Static suffices for v0.1.0 and keeps the smoke test trivial. |
| 8 | Lockfile | Commit `uv.lock` | `.gitignore` it | No lock = non-reproducible CI | uv's own recommendation. Future changes use `uv lock --upgrade` deliberately, never as a `uv add` side effect. |
| 9 | Pre-commit | Defer | Add hooks now | Hooks = safety; cost = moving parts | Out of scope per proposal. |
| 10 | Secrets | `.env.example` lists keys; `python-dotenv` loads at runtime | Vault / SOPS | Overkill for a single-dev cron | `.env.example` documents; first reader validates presence and fails loudly. |

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Create (via `uv init --package`) then edit | Project metadata, deps, tool config. |
| `uv.lock` | Create (via `uv sync`) | Committed. |
| `src/copytrading/__init__.py` | Create | Docstring + `__version__ = "0.1.0"`. |
| `src/copytrading/hello.py` | Delete | uv-generated placeholder. |
| `tests/test_smoke.py` | Create | Imports the package, asserts version string. |
| `.gitignore` | Create | `.venv/`, `__pycache__/`, `*.db`, `.env`, `logs/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `*.egg-info/`, `dist/`, `build/`. |
| `.env.example` | Create | Six placeholder keys (Polymarket CLOB + Google Sheets). |
| `README.md` | Create | One-paragraph description + canonical `uv` commands. |

## Interfaces / Contracts

`pyproject.toml` MUST end with these four tool blocks:

- `[tool.ruff]` — `line-length = 100`, `target-version = "py313"`, `src = ["src", "tests"]`.
- `[tool.ruff.lint]` — `select = ["E", "F", "I", "N", "UP", "B", "SIM", "RET"]`.
- `[tool.mypy]` — `python_version = "3.13"`, `strict = true`, plus `[[tool.mypy.overrides]]` for `py_clob_client`, `googleapiclient`, `google` setting `ignore_missing_imports = true`.
- `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `addopts = "-ra -q"`.

`src/copytrading/__init__.py` contract:

```python
"""copytrading — Polymarket copy-trading bot."""
from __future__ import annotations

__version__ = "0.1.0"
```

## Data Flow

N/A. No runtime data flow yet; the first cronjob change owns that diagram.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Smoke | Package importable, `__version__ == "0.1.0"` | `tests/test_smoke.py`, one assertion. |
| Toolchain (implicit) | ruff / mypy / pytest exit 0 | `sdd-verify` runs the four commands from the proposal; no extra test code. |
| Domain (later) | Unit + integration per cronjob | Out of scope here; each future change ships its own tests. |

## Migration / Rollout

No migration. Rollback = `git revert <commit>` + optional `rm -rf .venv uv.lock`.
Nothing in this change touches trading state, secrets, the SQLite store, or
the cron schedule.

## Open Questions

None blocking. Two non-blockers to surface in `sdd-tasks`:

- Whether to tighten `requires-python` to `==3.13.*` once the team confirms a single CI interpreter.
- Whether to mirror the 80% coverage threshold into `pyproject.toml` (current plan: leave it to `openspec/config.yaml → verify.coverage_threshold` only).
