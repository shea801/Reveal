"""Test-only safeguards for sanitized checkouts."""

from __future__ import annotations

import importlib.util
import types
import sys


def pytest_configure():
    _install_db_connection_stub_if_missing()


def _install_db_connection_stub_if_missing():
    try:
        db_connection_spec = importlib.util.find_spec(
            "Securities_DB.db_connection"
        )
    except ModuleNotFoundError:
        db_connection_spec = None

    if db_connection_spec is not None:
        return

    securities_db = types.ModuleType("Securities_DB")
    db_connection = types.ModuleType("Securities_DB.db_connection")

    def get_connection(*args, **kwargs):
        raise RuntimeError(
            "Unit tests must mock database access; real SQLite access is disabled."
        )

    db_connection.get_connection = get_connection
    securities_db.db_connection = db_connection
    sys.modules["Securities_DB"] = securities_db
    sys.modules["Securities_DB.db_connection"] = db_connection
