import pandas as pd
import pytest
import sqlite3

from analytics.FinancialAssessment import (
    FinancialAssessment,
    quarter_analysis_date,
    quarter_group_mapper,
)
from data_access.OHLCVPriceData import OHLCVPriceData
from data_access.date_selection import select_statement_date


def test_select_statement_date_annual_uses_latest_prior_fiscal_year():
    dates = ["2022-12-31", "2023-12-31", "2024-12-31"]

    selected = select_statement_date(dates, "2024-02-15")

    assert selected == "2023-12-31"


def test_select_statement_date_annual_falls_back_to_prior_year_when_needed():
    dates = ["2021-12-31", "2022-12-31", "2024-12-31"]

    selected = select_statement_date(dates, "2023-08-15")

    assert selected == "2022-12-31"


def test_select_statement_date_quarterly_uses_latest_prior_quarter():
    dates = ["2024-03-31", "2024-06-30", "2024-09-30"]

    selected = select_statement_date(
        dates,
        "2024-08-15",
        quarterly=True,
    )

    assert selected == "2024-06-30"


def test_ohlcv_get_closest_date_falls_back_to_prior_trading_day():
    ohlcv = OHLCVPriceData.__new__(OHLCVPriceData)
    ohlcv.ticker = "TEST"

    def closing_prices():
        return pd.DataFrame(
            {"close": [10.0, 11.0, 12.0]},
            index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-02-15"]),
        )

    def latest_price():
        return {"date": "2024-02-15", "close": 12.0}

    ohlcv.closing_prices = closing_prices
    ohlcv.latest_price = latest_price

    selected = ohlcv.get_closest_date("2024-01-04")

    assert selected.strftime("%Y-%m-%d") == "2024-01-03"


def test_ohlcv_get_closest_date_does_not_use_future_price():
    ohlcv = OHLCVPriceData.__new__(OHLCVPriceData)
    ohlcv.ticker = "TEST"
    ohlcv.closing_prices = lambda: pd.DataFrame(
        {"close": [10.0]},
        index=pd.to_datetime(["2024-01-02"]),
    )

    with pytest.raises(ValueError, match="on or before"):
        ohlcv.get_closest_date("2024-01-01")


@pytest.mark.parametrize(
    ("date", "expected_quarter"),
    [
        ("2024-03-31", "Q1"),
        ("2024-06-30", "Q2"),
        ("2024-09-30", "Q3"),
        ("2024-12-31", "Q4"),
    ],
)
def test_quarter_group_mapper_includes_quarter_end_dates(date, expected_quarter):
    assert quarter_group_mapper(date) == expected_quarter


@pytest.mark.parametrize(
    ("date", "expected_statement_date"),
    [
        ("2024-03-31", "2023-12-31"),
        ("2024-04-01", "2024-03-31"),
        ("2024-07-01", "2024-06-30"),
        ("2024-10-01", "2024-09-30"),
    ],
)
def test_quarter_analysis_date_selects_prior_completed_quarter(
        date,
        expected_statement_date,
):
    assert quarter_analysis_date("TEST", date) == expected_statement_date


def test_financial_assessment_to_dict_separates_statement_and_price_dates(monkeypatch):
    assessment = FinancialAssessment.__new__(FinancialAssessment)
    assessment._ticker = "TEST"
    assessment._date = "2024-03-31"
    assessment._share_price_analysis_date = "2024-03-28"
    assessment._annual_fin_analysis_date = "2023-12-31"
    assessment._quarter_analysis_date = "2023-12-31"
    assessment._cd = type(
        "CompanyDetails",
        (),
        {"get_details": lambda self: {"Name": "Test Co."}},
    )()

    monkeypatch.setattr(
        FinancialAssessment,
        "_price",
        lambda self: {
            "date": pd.Timestamp("2024-04-05"),
            "close": 10.0,
        },
    )
    monkeypatch.setattr(
        FinancialAssessment,
        "_balance_sheet",
        lambda self: {"commonStockSharesOutstanding": 100},
    )
    monkeypatch.setattr(
        FinancialAssessment,
        "_earnings_report",
        lambda self: {"reportedEPS": 1.0},
    )
    monkeypatch.setattr(
        "analytics.FinancialAssessment.min_max_mean_200_day_price",
        lambda ticker, date: {
            "min": 8.0,
            "max": 12.0,
            "mean": 10.0,
            "median": 10.5,
        },
    )

    metric_methods = (
        "eps_ttm",
        "net_income_ttm",
        "ebit_ttm",
        "gross_margin",
        "free_cash_flow",
        "free_cash_flow_margin",
        "estimated_owner_earnings",
        "estimated_owner_earnings_yield",
        "operating_income",
        "inventory_turnover",
        "financial_profile_return_on_capital",
        "return_on_capital",
        "earnings_yield",
        "magic_formula_score",
        "return_on_assets",
        "return_on_equity",
        "return_on_invested_capital",
        "eps_cagr_5yr",
        "debt_to_assets",
        "debt_to_equity",
        "interest_coverage",
        "net_debt_to_free_cash_flow",
        "longterm_debt_to_cash",
        "total_sales_services",
    )
    for method_name in metric_methods:
        monkeypatch.setattr(
            FinancialAssessment,
            method_name,
            lambda self: 0.0,
        )
    monkeypatch.setattr(
        FinancialAssessment,
        "magic_formula_ranking",
        lambda self: {},
    )

    result = assessment.to_dict()

    assert result["analysis_date"] == "2024-03-31"
    assert result["price_date"] == "2024-04-05"
    assert result["annual_financial_statement_analysis_date"] == "2023-12-31"
    assert result["quarter_financial_statement_analysis_date"] == "2023-12-31"
    assert result["min_200_day_price"] == 8.0
    assert result["max_200_day_price"] == 12.0
    assert result["avg_price_200_day"] == 10.0
    assert result["median_price_200_day"] == 10.5


def test_magic_formula_values_are_the_point_in_time_ranking_inputs(monkeypatch):
    assessment = FinancialAssessment.__new__(FinancialAssessment)
    assessment._ticker = "TEST"
    assessment._date = "2024-09-30"
    assessment._annual_fin_analysis_date = "2023-12-31"
    monkeypatch.setattr(
        FinancialAssessment,
        "return_on_capital",
        lambda self: 0.25,
    )
    monkeypatch.setattr(
        FinancialAssessment,
        "earnings_yield",
        lambda self: 0.08,
    )

    assert assessment.magic_formula_values() == {
        "ticker": "TEST",
        "quarter_date": "2024-09-30",
        "associated_annual_date": "2023-12-31",
        "return_on_capital": 0.25,
        "earnings_yield": 0.08,
    }


def test_magic_formula_ranking_reads_latest_persisted_quarter_on_or_before_date():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE magic_formula_quarterly_results (
            ticker TEXT,
            quarter_date TEXT,
            associated_annual_date TEXT,
            financial_statement_availability_date TEXT,
            magic_formula_rank INTEGER,
            return_on_capital_rank INTEGER,
            earnings_yield_rank INTEGER,
            total_roc_ey_score INTEGER
        )
    """)
    conn.executemany(
        """
        INSERT INTO magic_formula_quarterly_results VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            ("TEST", "2024-03-31", "2023-12-31", "2024-04-26", 4, 2, 8, 10),
            ("TEST", "2024-06-30", "2023-12-31", "2024-07-26", 2, 3, 1, 4),
            ("TEST", "2024-09-30", "2023-12-31", "2024-10-25", 1, 1, 1, 2),
        ],
    )
    assessment = FinancialAssessment.__new__(FinancialAssessment)
    assessment._ticker = "TEST"
    assessment._date = "2024-08-15"

    ranking = assessment.magic_formula_ranking(conn=conn)

    assert ranking == {
        "ticker": "TEST",
        "quarter_date": "2024-06-30",
        "associated_annual_date": "2023-12-31",
        "financial_statement_availability_date": "2024-07-26",
        "magic_formula_rank": 2,
        "return_on_capital_rank": 3,
        "earnings_yield_rank": 1,
        "total_roc_ey_score": 4,
    }


def test_magic_formula_ranking_returns_empty_when_ticker_is_not_ranked():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE magic_formula_quarterly_results (
            ticker TEXT,
            quarter_date TEXT,
            associated_annual_date TEXT,
            financial_statement_availability_date TEXT,
            magic_formula_rank INTEGER,
            return_on_capital_rank INTEGER,
            earnings_yield_rank INTEGER,
            total_roc_ey_score INTEGER
        )
    """)
    assessment = FinancialAssessment.__new__(FinancialAssessment)
    assessment._ticker = "MISSING"
    assessment._date = "2024-12-31"

    assert assessment.magic_formula_ranking(conn=conn) == {}
