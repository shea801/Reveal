import json

from data_ingestion.DataExtraction import DataExtraction


def test_search_ticker(monkeypatch):
    def fake_api_call(ticker, key):
        assert ticker == "AAPL"
        assert key == "symbol_search"
        return {
            "bestMatches": [
                {
                    "1. symbol": "AAPL",
                    "2. name": "Apple Inc.",
                    "3. type": "Common Stock",
                    "4. region": "United States",
                    "5. marketOpen": "09:30",
                    "6. marketClose": "16:00",
                    "7. timezone": "UTC-04",
                    "8. currency": "USD",
                    "9. matchScore": "1.0000",
                }
            ]
        }

    monkeypatch.setattr(
        "data_ingestion.DataExtraction.make_alphavantage_api_call",
        fake_api_call,
    )

    ticker = 'AAPL'
    data_extraction = DataExtraction()
    result = data_extraction.search_ticker(ticker)
    assert result == {
        'symbol': 'AAPL',
        'name': 'Apple Inc.',
        'type': 'Common Stock',
        'region': 'United States',
        'marketOpen': '09:30',
        'marketClose': '16:00',
        'timezone': 'UTC-04',
        'currency': 'USD',
        'matchScore': '1.0000',
    }


def test_company_details(monkeypatch):
    def fake_api_call(ticker, key):
        assert ticker == "AAPL"
        assert key == "company_details"
        return {
            "Symbol": "AAPL",
            "Name": "Apple Inc.",
            "Exchange": "NASDAQ",
            "AssetType": "Common Stock",
            "Currency": "USD",
            "Country": "USA",
            "FiscalYearEnd": "September",
            "Sector": "Technology",
        }

    monkeypatch.setattr(
        "data_ingestion.DataExtraction.make_alphavantage_api_call",
        fake_api_call,
    )

    ticker = 'AAPL'
    data_extraction = DataExtraction()
    result = data_extraction.company_details(ticker)
    comp_deets = result.company_details()

    assert comp_deets == {
        'Symbol': 'AAPL',
        'Name': 'Apple Inc.',
        'Exchange': 'NASDAQ',
        'AssetType': 'Common Stock',
        'Currency': 'USD',
        'Country': 'USA',
        'FiscalYearEnd': 'September',
    }


def test_price_history_writes_daily_adjusted_payload(monkeypatch, tmp_path):
    price_path = tmp_path / "AAAohlcv.json"
    meta_path = tmp_path / "AAAmeta.json"
    daily = {
        "2026-09-01": {
            "1. open": "231.0",
            "2. high": "233.09",
            "3. low": "229.9",
            "4. close": "231.4",
            "5. adjusted close": "231.4",
            "6. volume": "3240341",
            "7. dividend amount": "0.0000",
            "8. split coefficient": "1.0",
        }
    }

    def fake_api_call(ticker, key):
        assert (ticker, key) == ("AAA", "ohlcv")
        return {
            "Meta Data": {"2. Symbol": "AAA"},
            "Time Series (Daily)": daily,
        }

    class FakeTickerSearch:
        @staticmethod
        def ticker_file_pathways(ticker):
            assert ticker == "AAA"
            return {
                "ohlcv": {
                    "price_hx": str(price_path),
                    "meta_data": str(meta_path),
                }
            }

    monkeypatch.setattr(
        "data_ingestion.DataExtraction.make_alphavantage_api_call",
        fake_api_call,
    )
    extractor = DataExtraction("AAA")
    object.__setattr__(extractor, "ts", FakeTickerSearch())

    extractor.price_history_api_call_to_file()

    assert json.loads(price_path.read_text()) == daily
    assert json.loads(meta_path.read_text()) == {"2. Symbol": "AAA"}
