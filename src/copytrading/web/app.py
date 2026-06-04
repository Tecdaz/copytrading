"""FastAPI application factory for the read-only web dashboard.

The factory takes the path to the SQLite database so tests can point the
app at a temp file with a known seed. The dashboard itself is bound to
``127.0.0.1:8000`` in :mod:`copytrading.web.__main__` — this module is
neutral about that.

Wiring:

* :class:`Store` is opened per request via the :func:`get_store` dependency
  (mirrors the existing context-manager pattern; cheap with WAL mode).
* ``/static`` is mounted from the ``static/`` directory next to this file.
* Jinja2 templates live in ``templates/`` and are exposed on
  ``app.state.templates`` so route handlers can grab them off the request.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles

from copytrading.store import Store

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def get_store(request: Request) -> Iterator[Store]:
    """Open a :class:`Store` per request and close it on exit.

    The :class:`Store` follows the context-manager pattern; FastAPI calls
    the generator dependency in a ``with``-like lifecycle, so the connection
    is opened, used by the route handler, and closed before the response
    is returned. The db path is cached on ``app.state.db_path`` by
    :func:`create_app`.
    """
    db_path: str = request.app.state.db_path
    with Store(db_path) as store:
        yield store


StoreDep = Annotated[Store, Depends(get_store)]


def create_app(db_path: str | Path) -> FastAPI:
    """Build a FastAPI app bound to a specific SQLite file.

    Args:
        db_path: Path to the SQLite database. The file may be a fresh
            temp path for tests or the live ``copytrading.db`` for prod.
    """
    app = FastAPI(title="copytrading dashboard", docs_url=None, redoc_url=None)
    app.state.db_path = str(db_path)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Lazy import so importing ``copytrading.web`` from test code does not
    # pull in route modules before fixtures are in place.
    from fastapi.templating import Jinja2Templates

    from copytrading.web.routes import router

    app.state.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.include_router(router)
    return app


__all__ = ["create_app", "get_store", "StoreDep"]
