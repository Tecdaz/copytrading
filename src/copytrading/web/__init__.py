"""Read-only web dashboard for the copy-trading bot (FastAPI + HTMX + Chart.js).

Observes the live SQLite database through the existing :class:`Store`. No writes,
no auth, no mobile UI; intended to be served on ``127.0.0.1:8000`` only.
"""

from copytrading.web.app import create_app

__all__ = ["create_app"]
