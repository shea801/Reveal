"""Alpha Vantage request helper used by the ingestion workflows."""

from time import sleep

import requests

from runtime_config import get_alphavantage_api_key


API_URL = "https://www.alphavantage.co/query?"
FUNCTIONS = {
    "earnings": "EARNINGS",
    "balance": "BALANCE_SHEET",
    "cash": "CASH_FLOW",
    "income": "INCOME_STATEMENT",
    "ohlcv": "TIME_SERIES_DAILY_ADJUSTED",
    "company_details": "OVERVIEW",
    "etf": "ETF_PROFILE",
    "symbol_search": "SYMBOL_SEARCH",
}


def make_alphavantage_api_call(ticker: str, key: str):
    if ticker is None or key is None or ticker == "" or key == "":
        return None
    if key not in FUNCTIONS:
        raise ValueError(f"Invalid key: {key}")

    api_key = get_alphavantage_api_key()
    parameter = "keywords" if key == "symbol_search" else "symbol"
    url = f"{API_URL}function={FUNCTIONS[key]}&{parameter}={ticker}"
    if key in ("ohlcv", "etf", "symbol_search"):
        if key == "ohlcv":
            url += "&outputsize=full"
        url += "&datatype=json"
    url += f"&apikey={api_key}"

    sleep(0.9)
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        raise RuntimeError("Alpha Vantage request failed.") from None
    return response.json()
