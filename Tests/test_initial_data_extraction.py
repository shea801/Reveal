import json
import sqlite3
import datetime as dt

import pytest

from data_ingestion.DataExtraction import (
    AlphaVantageRateLimit, DataExtraction, _PacedAlphaVantage,
    download_initial_ticker, main,
)


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def call(self, ticker, key):
        self.calls.append((ticker, key))
        return self.responses.get(key)


def _registry(tmp_path, ticker, title):
    (tmp_path / "company_tickers.json").write_text(json.dumps({
        "0": {"ticker": ticker, "title": title, "cik_str": 1234},
    }))


def _daily_prices():
    return {"2026-09-01": {
        "1. open": "10", "2. high": "11", "3. low": "9", "4. close": "10",
        "5. adjusted close": "9.5", "6. volume": "100",
        "7. dividend amount": "0", "8. split coefficient": "1",
    }}


def test_initial_equity_download_creates_importer_layout_and_resumes(monkeypatch, tmp_path):
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(tmp_path))
    _registry(tmp_path, "AAA", "Alpha Inc")
    reports = [{"fiscalDateEnding": "2025-12-31", "totalAssets": "100"}]
    client = FakeClient({
        "symbol_search": {"bestMatches": [
            {"1. symbol": "AAAX", "3. type": "Equity"},
            {"1. symbol": "AAA", "3. type": "Equity"},
        ]},
        "ohlcv": {"Meta Data": {"2. Symbol": "AAA"}, "Time Series (Daily)": _daily_prices()},
        "company_details": {"Symbol": "AAA", "Name": "Alpha Inc"},
        **{key: {"symbol": "AAA", annual: reports, quarterly: reports}
           for key, annual, quarterly in (
               ("balance", "annualReports", "quarterlyReports"),
               ("cash", "annualReports", "quarterlyReports"),
               ("income", "annualReports", "quarterlyReports"),
               ("earnings", "annualEarnings", "quarterlyEarnings"),
           )},
    })

    assert download_initial_ticker("aaa", client) == 12
    base = tmp_path / "Securities" / "AAA__Alpha Inc"
    assert json.loads((base / "OHLCV" / "AAAohlcv.json").read_text()) == _daily_prices()
    assert (base / "OHLCV" / "AAAmeta.json").is_file()
    assert json.loads((base / "current_company_details.json").read_text())["Symbol"] == "AAA"
    for folder, stem in (("Balance", "Balance"), ("Cash_Flow", "Cash_Flow"),
                         ("Income", "Income"), ("Earnings", "Earnings")):
        for period, suffix in (("Annual", "Reports" if folder != "Earnings" else "Earnings"),
                               ("Quarterly", "Reports" if folder != "Earnings" else "Earnings")):
            assert (base / "Financial_Statements" / folder / f"{stem}{period}{suffix}.json").is_file()
    assert download_initial_ticker("AAA", client) == 0
    assert len(client.calls) == 7


def test_cli_resumes_ticker_with_search_file_but_missing_prices(monkeypatch, tmp_path):
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(tmp_path))
    _registry(tmp_path, "AAA", "Alpha Inc")
    search_dir = tmp_path / "All_Tickers_Searched"
    search_dir.mkdir()
    (search_dir / "AAA_ticker_search_info.json").write_text(json.dumps({
        "1. symbol": "AAA", "3. type": "Equity",
    }))
    client = FakeClient({
        "ohlcv": {"Meta Data": {"2. Symbol": "AAA"}, "Time Series (Daily)": _daily_prices()},
    })
    monkeypatch.setattr("data_ingestion.DataExtraction.get_alphavantage_api_key", lambda: "test")
    monkeypatch.setattr("data_ingestion.DataExtraction._PacedAlphaVantage", lambda _: client)

    assert main(["AAA"]) == 0
    assert ("AAA", "ohlcv") in client.calls
    assert (tmp_path / "Securities" / "AAA__Alpha Inc" / "OHLCV" / "AAAohlcv.json").is_file()


def test_initial_etf_download_and_unavailable_data(monkeypatch, tmp_path):
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(tmp_path))
    _registry(tmp_path, "ETF", "Example Fund")
    client = FakeClient({
        "symbol_search": {"bestMatches": [{"1. symbol": "ETF", "3. type": "ETF"}]},
        "ohlcv": {"Information": "Premium endpoint unavailable"},
        "etf": {"symbol": "ETF", "net_assets": "1000"},
    })

    assert download_initial_ticker("ETF", client) == 2
    base = tmp_path / "ETF_Securities" / "ETF__Example Fund"
    assert json.loads((base / "ETF_etf_profile.json").read_text())["net_assets"] == "1000"
    assert not (base / "OHLCV" / "ETFohlcv.json").exists()
    assert client.calls == [("ETF", "symbol_search"), ("ETF", "ohlcv"), ("ETF", "etf")]


def test_initial_download_skips_inexact_match(monkeypatch, tmp_path):
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(tmp_path))
    _registry(tmp_path, "AAA", "Alpha Inc")
    client = FakeClient({
        "symbol_search": {"bestMatches": [{"1. symbol": "AAAX", "3. type": "Equity"}]},
    })

    assert download_initial_ticker("AAA", client) == 0
    assert not (tmp_path / "All_Tickers_Searched" / "AAA_ticker_search_info.json").exists()
    assert client.calls == [("AAA", "symbol_search")]


def test_cli_rejects_ticker_outside_sec_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(tmp_path))
    _registry(tmp_path, "AAA", "Alpha Inc")
    try:
        main(["ZZZ"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected invalid ticker to be rejected")
    assert not (tmp_path / "Securities").exists()


def test_etf_prices_are_importable_into_investment_db(monkeypatch, tmp_path):
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(tmp_path))
    _registry(tmp_path, "ETF", "Example Fund")
    client = FakeClient({
        "symbol_search": {"bestMatches": [{"1. symbol": "ETF", "3. type": "ETF"}]},
        "ohlcv": {"Meta Data": {"2. Symbol": "ETF"}, "Time Series (Daily)": _daily_prices()},
        "etf": {"symbol": "ETF", "net_assets": "1000"},
    })
    assert download_initial_ticker("ETF", client) == 4

    from Securities_DB.create_database import create_database, populate_sec_tickers, populate_ohlcv

    create_database()
    populate_sec_tickers()
    populate_ohlcv()
    with sqlite3.connect(tmp_path / "Securities_DB" / "investment.db") as conn:
        assert conn.execute(
            "SELECT adjusted_close FROM ohlcv_daily WHERE ticker = ? AND date = ?",
            ("ETF", "2026-09-01"),
        ).fetchone() == (9.5,)


def test_provider_rate_limit_stops_initial_download(monkeypatch, tmp_path):
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(tmp_path))
    _registry(tmp_path, "AAA", "Alpha Inc")
    monkeypatch.setattr(
        "data_ingestion.DataExtraction.make_alphavantage_api_call",
        lambda ticker, key: {"Note": "Our standard API rate limit is reached."},
    )
    try:
        download_initial_ticker("AAA", _PacedAlphaVantage(5))
    except AlphaVantageRateLimit:
        pass
    else:
        raise AssertionError("Expected the API limit to stop the download")
    assert not (tmp_path / "All_Tickers_Searched" / "AAA_ticker_search_info.json").exists()


@pytest.mark.parametrize("age_days,refresh", [(2, False), (8, True), (None, True)])
def test_security_update_uses_latest_price_date(monkeypatch, age_days, refresh):
    latest = None if age_days is None else {
        "date": (dt.date.today() - dt.timedelta(days=age_days)).isoformat(),
        "close": 10.0,
    }
    calls = []

    class FakePrices:
        def __init__(self, ticker):
            assert ticker == "AAA"

        def latest_price(self):
            return latest

    class FakeDetails:
        def __init__(self, ticker):
            assert ticker == "AAA"

        def get_details(self):
            return {}

    monkeypatch.setattr("data_access.OHLCVPriceData.OHLCVPriceData", FakePrices)
    monkeypatch.setattr("data_ingestion.DataExtraction.CD", FakeDetails)
    monkeypatch.setattr(
        "Securities_DB.create_database.update_ohlcv_for_ticker",
        lambda ticker: calls.append(("database", ticker)),
    )
    extractor = DataExtraction("AAA")
    monkeypatch.setattr(
        extractor, "price_history_api_call_to_file",
        lambda: calls.append(("download", "AAA")),
    )

    extractor.update_securities_data()
    assert calls == ([('download', 'AAA'), ('database', 'AAA')] if refresh else [])


def test_security_update_compares_quarterly_dates_without_datetime_error(monkeypatch):
    class FakePrices:
        def __init__(self, ticker):
            pass

        def latest_price(self):
            return {"date": dt.date.today().isoformat(), "close": 10.0}

    class FakeDetails:
        def __init__(self, ticker):
            pass

        def get_details(self):
            return {"AssetType": "Common Stock", "FiscalYearEnd": "December"}

        def get_latest_quarterly_fiscal_date(self):
            return (dt.date.today() - dt.timedelta(days=200)).isoformat()

        def get_latest_quarter(self):
            return self.get_latest_quarterly_fiscal_date()

        def get_latest_annual_fiscal_date(self):
            return dt.date.today().isoformat()

    updated = []
    monkeypatch.setattr("data_access.OHLCVPriceData.OHLCVPriceData", FakePrices)
    monkeypatch.setattr("data_ingestion.DataExtraction.CD", FakeDetails)
    monkeypatch.setattr(
        "Securities_DB.create_database.update_market_capitalization_for_ticker",
        updated.append,
    )
    extractor = DataExtraction("AAA")
    monkeypatch.setattr(extractor, "_check_financial_files_recently_modified", lambda **_: True)

    extractor.update_securities_data()
    assert updated == ["AAA"]
