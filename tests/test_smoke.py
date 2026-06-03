"""Smoke test for the copytrading package.

Verifies the package is importable, exposes `__version__`, and that
`__version__` matches the contract value `"0.1.0"`.
"""

from copytrading import __version__


def test_version_is_string() -> None:
    """`__version__` MUST be a `str` equal to `"0.1.0"`."""
    assert isinstance(__version__, str)
    assert __version__ == "0.1.0"
