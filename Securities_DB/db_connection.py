# Python 3.14
# created: May 13, 2026
# Shared database connection utility

import sqlite3

from runtime_config import investment_db_path, magic_formula_db_path


def get_connection(analysis: str = "investment", readonly: bool = False):
    """Connect to an existing database without implicitly creating one."""
    if analysis == 'investment':
        path = investment_db_path()
        if not path.is_file():
            raise FileNotFoundError("Investment database is missing: Securities_DB/investment.db")
        conn = sqlite3.connect(
            f"{path.as_uri()}?mode={'ro' if readonly else 'rw'}", uri=True
        )
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn
    elif analysis == 'magic_formula':
        path = magic_formula_db_path()
        if not path.is_file():
            raise FileNotFoundError("Magic Formula database is missing: Securities_DB/magic_formula_results.db")
        conn = sqlite3.connect(
            f"{path.as_uri()}?mode={'ro' if readonly else 'rw'}", uri=True
        )
        conn.row_factory = sqlite3.Row
        return conn
    else:
        raise ValueError("Invalid analysis type. Supported types are 'investment' and 'magic_formula'.")
