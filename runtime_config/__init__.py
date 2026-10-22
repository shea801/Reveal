"""Runtime locations and credentials for Reveal's existing local data layout."""

import os
from pathlib import Path


def get_data_root() -> Path:
    value = os.environ.get("REVEAL_DATA_ROOT", "").strip()
    if not value:
        raise RuntimeError("REVEAL_DATA_ROOT is not configured.")
    root = Path(value).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise RuntimeError("REVEAL_DATA_ROOT must name an existing absolute directory.")
    return root


def investment_db_path() -> Path:
    return get_data_root() / "Securities_DB" / "investment.db"


def magic_formula_db_path() -> Path:
    return get_data_root() / "Securities_DB" / "magic_formula_results.db"


def get_alphavantage_api_key() -> str:
    key = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ALPHAVANTAGE_API_KEY is not configured.")
    return key
