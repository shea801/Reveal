"""Runtime locations and credentials for Reveal.

The data directory is resolved in this order (first match wins):

1. REVEAL_DATA_ROOT environment variable (an explicit override; must exist)
2. ``data_root`` in the per-user config file, written by ``set_data_root``
3. The platform's standard per-user data directory (created on first use)

The layout under the data root is unchanged:

    <data root>/Securities_DB/investment.db
    <data root>/Securities_DB/magic_formula_results.db
"""

import json
import os
import sys
import tomllib
from pathlib import Path

APP_NAME = 'Reveal'
ENV_VAR = 'REVEAL_DATA_ROOT'

def _home_directory() -> Path:
    return Path.home()


def config_file() -> Path:
    """Per-user config file that remembers the chosen data directory"""
    if sys.platform == 'win32':
        base = Path(os.environ.get("APPDATA") or _home_directory() / "AppData" / "Roaming")
        return base / APP_NAME.lower() / "config.toml"
    if sys.platform == 'darwin':
        return _home_directory() / "Library" / "Application Support" / APP_NAME / "config.toml"
    base = Path(os.environ.get('XDG_CONFIG_HOME') or _home_directory() / ".config")
    return base / APP_NAME.lower() / "config.toml"


def default_data_root() -> Path:
    """Conventional per-user location for application data."""
    if sys.platform == 'win32':
        base = Path(os.environ.get("LOCALAPPDATA") or _home_directory() / "AppData" / "Local")
        return base / APP_NAME / "data"
    if sys.platform == "darwin":
        return _home_directory() / "Library" / "Application Support" / APP_NAME / "data"
    base = Path(os.environ.get('XDG_DATA_HOME') or _home_directory() / ".local" / "share")
    return base / APP_NAME.lower()


def _read_configured_root() -> str:
    try:
        with config_file().open("rb") as handle:
            return str(tomllib.load(handle).get("data_root", "")).strip()
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return ""


def resolve_data_root() -> tuple[Path, str]:
    """Return (path, source) where source is 'env', 'config' or 'default'."""
    value = os.environ.get(ENV_VAR, "").strip()
    if value:
        return Path(value).expanduser(), "env"
    value = _read_configured_root()
    if value:
        return Path(value).expanduser(), "config"
    return default_data_root(), "default"


def get_data_root() -> Path:
    root, source = resolve_data_root()
    if source == "default":
        # nothing chosen, so creating the standard folder is safe to do
        root.mkdir(parents=True, exist_ok=True)
        return root
    if not root.is_absolute() or not root.is_dir():
        raise RuntimeError(
            f"Reveal data directory from {source} setting does not exist or "
            f"is not an absolute path: {root}. Run set_data_root(..., "
            "create=True) to create it."
        )
    return root


def set_data_root(path: str | Path, create: bool = False) -> Path:
    """
    Attach Reveal to an existing directory or create a new one.
    ...
    Saves the choice in the per-user config file so no environment variable
    is needed. With create=False (default) the directory must already exist.
    """
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        if not create:
            raise RuntimeError(
                f"Reveal data directory {root} does not exist. Run "
                "set_data_root(..., create=True) to create it."
            )
        root.mkdir(parents=True, exist_ok=True)
    target = config_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    # A JSON string is a valid TOML string and escapes Windows backslashes.
    target.write_text(f"data_root = {json.dumps(str(root))}\n", encoding="utf-8")
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
