"""Entrypoint for the copytrading dashboard.

Run with::

    uv run python -m copytrading.web

Binds to ``127.0.0.1:8000`` by default (REQ-WEB-13): the dashboard is a
local-only v1 observer and is NEVER exposed on a public interface.

The DB path is read from the ``COPYTRADING_DB_PATH`` environment variable
(default ``copytrading.db`` in the current working directory). The
dashboard is a pure observer over the SQLite file, so it does NOT need
the Google Sheets env vars the cronjobs require — those are independent
concerns and the dashboard can launch without them.
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn


def _resolve_db_path() -> Path:
    """Read ``COPYTRADING_DB_PATH`` from env, falling back to ``copytrading.db``.

    A small pure helper so the env-var contract is unit-testable without
    touching uvicorn or the filesystem.
    """
    return Path(os.environ.get("COPYTRADING_DB_PATH", "copytrading.db"))


def main() -> None:
    """Start uvicorn on the loopback interface.

    The bind contract is fixed: ``host="127.0.0.1"``, ``port=8000`` — both
    are asserted by ``tests/unit/test_web.py::TestBindAddress``. The DB
    path comes from :func:`_resolve_db_path` (env: ``COPYTRADING_DB_PATH``).
    """
    from copytrading.web.app import create_app

    uvicorn.run(
        create_app(db_path=_resolve_db_path()),
        host="127.0.0.1",
        port=8000,
    )


if __name__ == "__main__":
    main()


__all__ = ["main", "uvicorn", "_resolve_db_path"]
