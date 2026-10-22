import importlib
import sqlite3

import pytest

from data_access.CompanyDetails import CompanyDetails
from mvp.service import (
    resolve_security_identifier,
    search_security_identifiers,
)


def _identifier_connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE sec_tickers (
            ticker TEXT PRIMARY KEY,
            cik TEXT NOT NULL,
            title TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO sec_tickers (ticker, cik, title) VALUES (?, ?, ?)",
        (
            ("MSFT", "0000789019", "MICROSOFT CORP"),
            ("GOOG", "0001652044", "ALPHABET INC."),
            ("GOOGL", "0001652044", "ALPHABET INC."),
            ("META", "0001326801", "META PLATFORMS, INC."),
        ),
    )
    return conn


def test_sec_ticker_search_supports_ticker_company_name_and_cik(monkeypatch):
    company_details_module = importlib.import_module(
        "data_access.CompanyDetails"
    )
    monkeypatch.setattr(
        company_details_module,
        "get_connection",
        lambda readonly=True: _identifier_connection(),
    )
    access = CompanyDetails()

    assert access.search_sec_tickers("msft")[0]["ticker"] == "MSFT"
    assert access.search_sec_tickers("microsoft")[0]["ticker"] == "MSFT"
    assert access.search_sec_tickers("CIK 0000789019")[0]["ticker"] == "MSFT"
    assert access.search_sec_tickers("789019")[0]["ticker"] == "MSFT"


def test_sec_ticker_search_escapes_sql_wildcards(monkeypatch):
    company_details_module = importlib.import_module(
        "data_access.CompanyDetails"
    )
    monkeypatch.setattr(
        company_details_module,
        "get_connection",
        lambda readonly=True: _identifier_connection(),
    )

    assert CompanyDetails().search_sec_tickers("%") == []


def test_service_normalizes_identifier_matches_and_resolves_exact_values():
    rows = (
        {
            "ticker": "msft",
            "cik": "789019",
            "title": "MICROSOFT CORP",
        },
    )

    def provider(_query, limit):
        assert limit in (8, 25)
        return rows

    matches = search_security_identifiers("micro", search_provider=provider)

    assert matches == (
        {
            "ticker": "MSFT",
            "cik": "0000789019",
            "company_name": "MICROSOFT CORP",
        },
    )
    assert resolve_security_identifier(
        "MSFT", search_provider=provider
    ) == "MSFT"
    assert resolve_security_identifier(
        "Microsoft Corp", search_provider=provider
    ) == "MSFT"
    assert resolve_security_identifier(
        "0000789019", search_provider=provider
    ) == "MSFT"


def test_service_rejects_ambiguous_cik_and_company_searches():
    rows = (
        {
            "ticker": "GOOG",
            "cik": "0001652044",
            "title": "ALPHABET INC.",
        },
        {
            "ticker": "GOOGL",
            "cik": "0001652044",
            "title": "ALPHABET INC.",
        },
    )

    def provider(_query, limit):
        return rows[:limit]

    with pytest.raises(ValueError, match="CIK maps to multiple"):
        resolve_security_identifier(
            "0001652044",
            search_provider=provider,
        )
    with pytest.raises(ValueError, match="company name maps to multiple"):
        resolve_security_identifier(
            "Alphabet Inc.",
            search_provider=provider,
        )


def test_service_reports_no_identifier_match():
    with pytest.raises(ValueError, match="No security matched"):
        resolve_security_identifier(
            "Missing Company",
            search_provider=lambda _query, limit: (),
        )
