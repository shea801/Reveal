"""Configuration and database access stay independent of private files."""

import os
from pathlib import Path
import json
import subprocess
import sys

import pytest

from runtime_config import (
    get_alphavantage_api_key,
    get_data_root,
    investment_db_path,
    magic_formula_db_path,
)
from Securities_DB.db_connection import get_connection
from Securities_DB.create_database import create_database
from Securities_DB.magic_formula_database import default_ticker_backup_path
from maintenance.adjusted_price_backfill import (
    connect_investment_db,
    historical_magic_formula_tickers,
)
from dashboard.app import create_app
from data_access.file_parsing import tickers_titles
from data_ingestion.TickerFileSearch import TickerSearch


def test_affected_modules_import_without_configuration_or_environment():
    env = os.environ.copy()
    env.pop("REVEAL_DATA_ROOT", None)
    env.pop("ALPHAVANTAGE_API_KEY", None)
    modules = (
        "analytics.MyMagicFormula", "data_access.file_parsing",
        "data_access.BalanceSheets", "data_access.CashFlow",
        "data_access.IncomeStatements", "data_ingestion.DataExtraction",
        "data_ingestion.TickerFileSearch", "Securities_DB.create_database",
        "Securities_DB.magic_formula_database", "Securities_DB.db_connection",
        "maintenance.security_updater", "maintenance.adjusted_price_backfill",
        "scripts.prepare_backtest_data", "dashboard.app", "mvp.service",
    )
    code = "\n".join(
        ["import importlib, sys", "sys.modules['configuration'] = None"]
        + [f"importlib.import_module({name!r})" for name in modules]
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_paths_follow_existing_data_root_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(tmp_path))
    assert get_data_root() == tmp_path
    assert investment_db_path() == tmp_path / "Securities_DB" / "investment.db"
    assert magic_formula_db_path() == (
        tmp_path / "Securities_DB" / "magic_formula_results.db"
    )
    assert default_ticker_backup_path() == (
        tmp_path / "notebooks" / "magic_formula_ranked_securities.csv"
    )


def test_missing_data_root_is_reported_only_when_needed(monkeypatch):
    monkeypatch.delenv("REVEAL_DATA_ROOT", raising=False)
    with pytest.raises(RuntimeError, match="REVEAL_DATA_ROOT"):
        get_connection()


def test_dashboard_starts_without_api_key_or_data_root(monkeypatch):
    monkeypatch.delenv("REVEAL_DATA_ROOT", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    app = create_app(magic_formula_rankings_provider=lambda: ())
    assert app.layout is not None


def test_missing_databases_do_not_get_created(monkeypatch, tmp_path):
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(tmp_path))
    for analysis in ("investment", "magic_formula"):
        for readonly in (False, True):
            with pytest.raises(FileNotFoundError, match="database is missing"):
                get_connection(analysis, readonly=readonly)
    with pytest.raises(FileNotFoundError):
        connect_investment_db()
    with pytest.raises(FileNotFoundError):
        historical_magic_formula_tickers()
    assert not (tmp_path / "Securities_DB").exists()


def test_explicit_database_builder_still_creates_schema(monkeypatch, tmp_path):
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(tmp_path))
    create_database()
    path = investment_db_path()
    assert path.is_file()
    conn = get_connection(readonly=True)
    try:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name = 'sec_tickers'"
        ).fetchone() is not None
    finally:
        conn.close()


def test_file_consumers_use_runtime_root_after_import(monkeypatch, tmp_path):
    payload = {"0": {"ticker": "AAA", "title": "Example Company"}}
    (tmp_path / "company_tickers.json").write_text(json.dumps(payload))
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(tmp_path))
    assert tickers_titles() == payload
    assert TickerSearch().tickers_titles() == payload


def test_alphavantage_key_is_read_only_for_a_request(monkeypatch):
    from data_ingestion import alphavantage_api

    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    calls = []
    monkeypatch.setattr(alphavantage_api.requests, "get", calls.append)
    monkeypatch.setattr(alphavantage_api, "sleep", lambda _: None)
    assert alphavantage_api.make_alphavantage_api_call("", "ohlcv") is None
    with pytest.raises(RuntimeError, match="ALPHAVANTAGE_API_KEY"):
        alphavantage_api.make_alphavantage_api_call("AAA", "ohlcv")
    assert calls == []

    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-token")
    assert get_alphavantage_api_key() == "test-token"

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    def fake_get(url):
        calls.append(url)
        return Response()

    monkeypatch.setattr(alphavantage_api.requests, "get", fake_get)
    assert alphavantage_api.make_alphavantage_api_call("AAA", "ohlcv") == {
        "ok": True,
    }
    assert calls == [
        "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED"
        "&symbol=AAA&outputsize=full&datatype=json&apikey=test-token"
    ]


def test_alphavantage_http_error_does_not_expose_key(monkeypatch):
    import requests

    from data_ingestion import alphavantage_api

    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "dummy-secret")
    monkeypatch.setattr(alphavantage_api, "sleep", lambda _: None)

    def fail_request(url):
        raise requests.HTTPError(f"Failed URL: {url}")

    monkeypatch.setattr(alphavantage_api.requests, "get", fail_request)
    with pytest.raises(RuntimeError, match="Alpha Vantage request failed") as exc:
        alphavantage_api.make_alphavantage_api_call("AAA", "ohlcv")
    assert "dummy-secret" not in str(exc.value)
    assert exc.value.__cause__ is None


@pytest.mark.parametrize(
    ("key", "function", "parameter", "extra"),
    [
        ("earnings", "EARNINGS", "symbol", ""),
        ("balance", "BALANCE_SHEET", "symbol", ""),
        ("cash", "CASH_FLOW", "symbol", ""),
        ("income", "INCOME_STATEMENT", "symbol", ""),
        ("ohlcv", "TIME_SERIES_DAILY_ADJUSTED", "symbol", "&outputsize=full&datatype=json"),
        ("company_details", "OVERVIEW", "symbol", ""),
        ("etf", "ETF_PROFILE", "symbol", "&datatype=json"),
        ("symbol_search", "SYMBOL_SEARCH", "keywords", "&datatype=json"),
    ],
)
def test_alphavantage_request_parameters_are_preserved(
    monkeypatch, key, function, parameter, extra,
):
    from data_ingestion import alphavantage_api

    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "fixture-key")
    monkeypatch.setattr(alphavantage_api, "sleep", lambda _: None)
    urls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"fixture": True}

    def fake_get(url):
        urls.append(url)
        return Response()

    monkeypatch.setattr(alphavantage_api.requests, "get", fake_get)
    assert alphavantage_api.make_alphavantage_api_call("AAA", key) == {
        "fixture": True,
    }
    assert urls == [
        f"https://www.alphavantage.co/query?function={function}"
        f"&{parameter}=AAA{extra}&apikey=fixture-key"
    ]
