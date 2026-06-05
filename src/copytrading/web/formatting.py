"""Pure formatting helpers for the web layer.

These functions are deliberately decoupled from FastAPI, Jinja2, and the
``Store`` so they can be unit-tested without any fixtures. The aggregate
route handlers in :mod:`copytrading.web.routes` call :func:`format_signed`
to render their numbers before passing them to a panel partial.

The dashboard never formats Decimals in the template (per design.md
"Routes" §3): strings are computed in Python so the template stays dumb
and the formatting is the single source of truth.
"""

from __future__ import annotations

from decimal import Decimal


def format_signed(value: Decimal, places: int = 2, *, signed: bool = True) -> str:
    """Format a :class:`~decimal.Decimal` for display in an aggregate card.

    The default (``signed=True``) is the contract for the two PnL cards
    (REQ-WEB-7, REQ-WEB-8):

    * ``Decimal("0")``     → ``"0.00"``   (no sign — zero is not positive)
    * ``Decimal("1.234")`` → ``"+1.23"``  (explicit leading "+")
    * ``Decimal("-0.5")``  → ``"-0.50"``  (explicit leading "-")

    Pass ``signed=False`` for the money-in-open card (REQ-WEB-6), which
    must render the same value WITHOUT a leading "+" (the spec scenario
    expects ``"3.50"``, not ``"+3.50"``):

    * ``Decimal("1.23")``, ``signed=False``  → ``"1.23"``
    * ``Decimal("-1.00")``, ``signed=False`` → ``"-1.00"``

    Args:
        value: The number to format.
        places: Number of decimal places to render. Defaults to ``2``.
        signed: When ``True`` (default) positive values get a leading
            ``"+"``. When ``False`` positive values render without a
            sign — a defensive negative sign is always preserved so
            losses are never displayed as gains.

    Returns:
        The formatted string, never ``None`` and never raising on
        ``Decimal("0")``.
    """
    if value == 0:
        return f"{value:.{places}f}"
    if not signed and value > 0:
        return f"{value:.{places}f}"
    # ``:+`` forces a sign character (``"+"`` for positive, ``"-"`` for
    # negative). This branch covers signed-positive, signed-negative, and
    # unsigned-negative.
    return f"{value:+.{places}f}"


__all__ = ["format_signed"]
