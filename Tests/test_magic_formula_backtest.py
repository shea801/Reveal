import sqlite3

import pandas as pd
import pytest

from analytics import MagicFormulaBacktest as backtest
from Securities_DB import magic_formula_database as mf_db
from Securities_DB import ohlcv_database as ohlcv_db
from Securities_DB import sec_metadata_database as sec_db


FISCAL_DATES = [
    ("annual", "2023-12-31"),
    ("quarterly", "2023-06-30"),
    ("quarterly", "2023-09-30"),
    ("quarterly", "2023-12-31"),
    ("quarterly", "2024-03-31"),
]


def _connections(include_adjusted_prices=True):
    investment = sqlite3.connect(":memory:")
    investment.row_factory = sqlite3.Row
    investment.execute(
        "CREATE TABLE sec_tickers (ticker TEXT PRIMARY KEY)"
    )
    investment.executemany(
        "INSERT INTO sec_tickers VALUES (?)",
        [("AAA",), ("BBB",)],
    )
    ohlcv_db.ensure_ohlcv_schema(investment)
    sec_db.create_sec_metadata_schema(investment)

    results = sqlite3.connect(":memory:")
    results.row_factory = sqlite3.Row
    mf_db.create_magic_formula_schema(results)

    for ticker, rank in (("AAA", 1), ("BBB", 2)):
        mf_db.upsert_magic_formula_records(results, [{
            "ticker": ticker,
            "quarter_date": "2024-03-31",
            "associated_annual_date": "2023-12-31",
            "financial_statement_availability_date": "2024-05-02",
            "magic_formula_rank": rank,
            "return_on_capital_rank": rank,
            "earnings_yield_rank": rank,
            "total_roc_ey_score": rank * 2,
        }])
        acceptance = (
            "2024-05-02T18:00:00Z" if ticker == "BBB"
            else "2024-05-01T18:00:00Z"
        )
        for index, (scope, fiscal_date) in enumerate(FISCAL_DATES):
            accession = f"{ticker}-{index}"
            form = "10-K" if scope == "annual" else "10-Q"
            investment.execute(f"""
                INSERT INTO {sec_db.SEC_FILING_TABLE} (
                    cik, accession_number, form, report_date, filing_date,
                    acceptance_datetime_utc, source_member, is_amendment,
                    imported_at_utc
                ) VALUES (?, ?, ?, ?, '2024-05-01', ?, 'test.json', 0, 'now')
            """, (f"CIK-{ticker}", accession, form, fiscal_date, acceptance))
            investment.execute(f"""
                INSERT INTO {sec_db.SEC_MATCH_TABLE} (
                    ticker, statement_scope, fiscal_date, cik,
                    accession_number, form, acceptance_datetime_utc,
                    match_method, confidence, identity_status,
                    matched_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'report_date_exact', 'high',
                          'confirmed_current_cik', 'now')
            """, (
                ticker,
                scope,
                fiscal_date,
                f"CIK-{ticker}",
                accession,
                form,
                acceptance,
            ))
        purchase = {
            "1. open": "10.0",
            "2. high": "11.0",
            "3. low": "9.0",
            "4. close": "10.0",
            "5. volume": "1000",
        }
        if include_adjusted_prices:
            purchase.update({
                "5. adjusted close": (
                    "10.0" if ticker == "AAA" else "20.0"
                ),
                "6. volume": "1000",
                "7. dividend amount": "0.0",
                "8. split coefficient": "1.0",
            })
        payload = {"2024-05-03": purchase}
        if include_adjusted_prices:
            payload["2025-05-05"] = {
                "1. open": "10.0",
                "2. high": "11.0",
                "3. low": "9.0",
                "4. close": "10.0",
                "5. adjusted close": (
                    "12.0" if ticker == "AAA" else "18.0"
                ),
                "6. volume": "1000",
                "7. dividend amount": "0.0",
                "8. split coefficient": "1.0",
            }
        ohlcv_db.upsert_ohlcv_payload(investment, ticker, payload)
    investment.commit()
    return investment, results


def _fake_ranking(tickers_list, date, market_price_date):
    assert tickers_list == ["AAA", "BBB"]
    assert date == "2024-03-31"
    assert market_price_date == "2024-05-03"
    return pd.DataFrame([
        {
            "ticker": "BBB",
            "quarter_date": date,
            "associated_annual_date": "2023-12-31",
            "magic_formula_rank": 1,
            "return_on_capital_rank": 2,
            "earnings_yield_rank": 1,
            "total_roc_ey_score": 3,
        },
        {
            "ticker": "AAA",
            "quarter_date": date,
            "associated_annual_date": "2023-12-31",
            "magic_formula_rank": 2,
            "return_on_capital_rank": 1,
            "earnings_yield_rank": 2,
            "total_roc_ey_score": 3,
        },
    ])


def test_cohort_uses_latest_acceptance_and_next_common_trading_date():
    investment, results = _connections()

    cohort = backtest.build_availability_aware_cohort(
        investment,
        results,
        quarter_date="2024-03-31",
        ranking_fn=_fake_ranking,
    )

    assert cohort["information_cutoff_utc"] == "2024-05-02T18:00:00Z"
    assert cohort["purchase_date"] == "2024-05-03"
    assert cohort["source_ticker_count"] == 2
    assert cohort["eligible_ticker_count"] == 2
    assert cohort["excluded"] == []
    assert cohort["ranking"]["ticker"].tolist() == ["BBB", "AAA"]


def test_one_year_returns_use_adjusted_closes_and_actual_exit_session():
    investment, results = _connections()
    cohort = backtest.build_availability_aware_cohort(
        investment,
        results,
        quarter_date="2024-03-31",
        ranking_fn=_fake_ranking,
    )

    positions = backtest.calculate_one_year_returns(
        investment,
        cohort["ranking"],
        top_n=2,
    )

    assert positions["exit_date"].tolist() == ["2025-05-05", "2025-05-05"]
    assert positions["one_year_total_return"].tolist() == pytest.approx([-0.1, 0.2])
    assert positions["adjusted_price_source"].tolist() == [
        ohlcv_db.ALPHA_VANTAGE_ADJUSTED_SOURCE,
        ohlcv_db.ALPHA_VANTAGE_ADJUSTED_SOURCE,
    ]


def test_full_backtest_reports_equal_weighted_period_return():
    investment, results = _connections()

    result = backtest.run_magic_formula_backtest(
        investment,
        results,
        quarter_dates=["2024-03-31"],
        top_n=2,
        ranking_fn=_fake_ranking,
    )

    period = result["period_returns"].iloc[0]
    assert period["position_count"] == 2
    assert period["equal_weighted_total_return"] == pytest.approx(0.05)


def test_cohort_refuses_raw_prices_when_all_adjusted_prices_are_missing():
    investment, results = _connections(include_adjusted_prices=False)

    with pytest.raises(
        backtest.AdjustedPriceDataUnavailableError,
        match="No 2024-03-31 securities have an adjusted purchase price",
    ):
        backtest.build_availability_aware_cohort(
            investment,
            results,
            quarter_date="2024-03-31",
            ranking_fn=_fake_ranking,
        )


def test_cohort_excludes_ticker_without_adjusted_purchase_price():
    investment, results = _connections()
    investment.execute("""
        UPDATE ohlcv_daily
        SET adjusted_close = NULL, price_source = NULL
        WHERE ticker = 'BBB'
    """)
    investment.commit()

    def single_ticker_ranking(tickers_list, date, market_price_date):
        assert tickers_list == ["AAA"]
        return pd.DataFrame([{
            "ticker": "AAA",
            "quarter_date": date,
            "associated_annual_date": "2023-12-31",
            "magic_formula_rank": 1,
            "return_on_capital_rank": 1,
            "earnings_yield_rank": 1,
            "total_roc_ey_score": 2,
        }])

    cohort = backtest.build_availability_aware_cohort(
        investment,
        results,
        quarter_date="2024-03-31",
        ranking_fn=single_ticker_ranking,
    )

    assert cohort["eligible_ticker_count"] == 1
    assert cohort["excluded"] == [{
        "ticker": "BBB",
        "reason": "missing_adjusted_purchase_price",
    }]
