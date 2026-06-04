"""Entrypoint for the copytrading dashboard.

Run with::

    uv run python -m copytrading.web

Binds to ``127.0.0.1:8000`` by default (REQ-WEB-13): the dashboard is a
local-only v1 observer and is NEVER exposed on a public interface.
"""

from __future__ import annotations

import uvicorn


def main() -> None:
    """Start uvicorn on the loopback interface.

    The dashboard reads the live ``copytrading.db`` file in the current
    working directory (the same file the cronjobs write). The bind
    contract is fixed: ``host="127.0.0.1"``, ``port=8000`` — both are
    asserted by ``tests/unit/test_web.py::TestBindAddress``.
    """
    from copytrading.web.app import create_app

    uvicorn.run(
        create_app(db_path="copytrading.db"),
        host="127.0.0.1",
        port=8000,
    )


if __name__ == "__main__":
    main()


__all__ = ["main", "uvicorn"]
