import numpy as np
import pandas as pd
import pytest

from data_access.PipelineETL import FinancialData, FinancialData_by_date


class _AnnualStatement:
    def __init__(self, rows):
        self.rows = pd.DataFrame(rows)

    def annual(self):
        return self.rows.copy()


def test_concat_dataframes_joins_annual_statements_by_fiscal_date():
    pipeline = FinancialData.__new__(FinancialData)
    pipeline.needed_columns = (
        "fiscalDateEnding",
        "totalAssets",
        "dividendPayoutCommonStock",
        "totalRevenue",
        "netIncome",
        "reportedEPS",
    )
    pipeline.balance = _AnnualStatement(
        [
            {"fiscalDateEnding": "2023-12-31", "totalAssets": 900},
            {"fiscalDateEnding": "2024-12-31", "totalAssets": 1_000},
        ]
    )
    pipeline.cash = _AnnualStatement(
        [
            {
                "fiscalDateEnding": "2024-12-31",
                "dividendPayoutCommonStock": 40,
            },
            {
                "fiscalDateEnding": "2023-12-31",
                "dividendPayoutCommonStock": 30,
            },
        ]
    )
    pipeline.income = _AnnualStatement(
        [
            {
                "fiscalDateEnding": "2024-12-31",
                "totalRevenue": 600,
                "netIncome": 100,
            },
            {
                "fiscalDateEnding": "2023-12-31",
                "totalRevenue": 500,
                "netIncome": 80,
            },
        ]
    )
    pipeline.earnings = _AnnualStatement(
        [
            {"fiscalDateEnding": "2025-06-30", "reportedEPS": 9.9},
            {"fiscalDateEnding": "2023-12-31", "reportedEPS": 3.0},
            {"fiscalDateEnding": "2024-12-31", "reportedEPS": 4.0},
        ]
    )

    result = pipeline.concat_dataframes().set_index("fiscalDateEnding")

    assert list(result.index) == [
        pd.Timestamp("2023-12-31"),
        pd.Timestamp("2024-12-31"),
    ]
    assert result.loc["2024-12-31", "totalAssets"] == 1_000
    assert result.loc["2024-12-31", "dividendPayoutCommonStock"] == 40
    assert result.loc["2024-12-31", "netIncome"] == 100
    assert result.loc["2024-12-31", "reportedEPS"] == 4.0


def _twenty_year_dividend_history():
    dates = pd.date_range("2004-12-31", "2024-12-31", freq="B")
    history = pd.DataFrame(
        {
            "date": dates,
            "dividend_amount": 0.0,
        }
    )
    for year in range(2005, 2025):
        annual_dates = history[history["date"].dt.year == year].index
        history.loc[annual_dates[0], "dividend_amount"] = 0.25
    return history


def test_annual_common_dividend_status_distinguishes_all_three_states():
    fiscal_dates = pd.Series(
        pd.date_range("2005-12-31", "2024-12-31", freq="YE")
    )
    complete = _twenty_year_dividend_history()

    passed = FinancialData._annual_common_dividend_status(
        fiscal_dates,
        complete,
    )

    missed_year = complete.copy()
    missed_year.loc[
        missed_year["date"].dt.year == 2014,
        "dividend_amount",
    ] = 0.0
    failed = FinancialData._annual_common_dividend_status(
        fiscal_dates,
        missed_year,
    )

    incomplete = complete.copy()
    incomplete.loc[
        incomplete["date"].eq(pd.Timestamp("2014-06-02")),
        "dividend_amount",
    ] = pd.NA
    unavailable = FinancialData._annual_common_dividend_status(
        fiscal_dates,
        incomplete,
    )

    assert passed.all()
    assert not bool(failed.loc[fiscal_dates.dt.year.eq(2014)].iloc[0])
    assert pd.isna(
        unavailable.loc[fiscal_dates.dt.year.eq(2014)].iloc[0]
    )


def test_trailing_twelve_months_uses_latest_four_quarters_on_or_before_date():
    dates = pd.to_datetime([
        "2025-03-31",
        "2024-12-31",
        "2024-09-30",
        "2024-06-30",
        "2024-03-31",
    ])
    income = pd.DataFrame({
        "fiscalDateEnding": dates,
        "ebit": [50, 40, 30, 20, 10],
        "netIncome": [5, 4, 3, 2, 1],
    })
    earnings = pd.DataFrame({
        "fiscalDateEnding": dates,
        "reportedEPS": [0.5, 0.4, 0.3, 0.2, 0.1],
    })

    result = FinancialData_by_date._trailing_twelve_months(
        income,
        earnings,
        "2024-12-31",
    )

    assert result["ebitTTM"] == 100
    assert result["earningsTTM"] == 10
    assert result["epsTTM"] == pytest.approx(1.0)


def test_financial_data_by_date_to_dict_is_safe_for_missing_statements():
    snapshot = FinancialData_by_date.__new__(FinancialData_by_date)
    snapshot.ticker = "TEST"
    snapshot.analysis_date = "2024-12-31"
    snapshot.balance = None
    snapshot.cash = {"operatingCashflow": 10}
    snapshot.income = {}
    snapshot.earnings = {"reportedEPS": 1.0}
    snapshot.price = np.nan
    snapshot.ttm = {
        "epsTTM": 4.0,
        "earningsTTM": 40.0,
        "ebitTTM": 50.0,
    }

    result = snapshot.to_dict()

    assert isinstance(result, dict)
    assert result["ticker"] == "TEST"
    assert result["epsTTM"] == 4.0
    assert np.isnan(result["price"])


def test_financial_data_by_date_safe_lookups_handle_missing_records():
    class MissingStatement:
        @staticmethod
        def get_by_date(analysis_date):
            raise ValueError("no dates")

    class MissingPrice:
        @staticmethod
        def price_on_date(analysis_date):
            return None

    assert FinancialData_by_date._safe_date_lookup(
        MissingStatement(),
        "2024-12-31",
    ) == {}
    assert FinancialData_by_date._safe_price_lookup(
        MissingPrice(),
        "2024-12-31",
    ) == {}


def test_quarterly_data_preserves_eps_ttm_and_uses_complete_four_quarter_windows():
    dates = pd.date_range("2020-03-31", periods=20, freq="QE")[::-1]
    income = pd.DataFrame({
        "fiscalDateEnding": dates,
        "ebit": range(20, 0, -1),
        "netIncome": range(20, 0, -1),
    })
    earnings = pd.DataFrame({
        "fiscalDateEnding": dates,
        "reportedEPS": [1.0] * 20,
        "epsTTM": [4.0] * 17 + [np.nan] * 3,
    })

    class Statement:
        def __init__(self, frame):
            self.frame = frame

        def quarterly(self):
            return self.frame.copy()

    class PriceHistory:
        @staticmethod
        def price_range(start_date, end_date):
            return pd.DataFrame({"close": [10.0]})

    class CompanyDetails:
        @staticmethod
        def get_details():
            return {"FiscalYearEnd": "December"}

    pipeline = FinancialData.__new__(FinancialData)
    pipeline.ticker = "TEST"
    pipeline.income = Statement(income)
    pipeline.earnings = Statement(earnings)
    pipeline.ohlcv = PriceHistory()
    pipeline.company_details = CompanyDetails()

    result = pipeline.quarterly_data()

    assert result.loc[0, "epsTTM"] == 4.0
    assert result.loc[0, "ebitTTM"] == 74
    assert result.loc[0, "earningsTTM"] == 74
    assert result["ebitTTM"].tail(3).isna().all()
    assert result["earningsTTM"].tail(3).isna().all()
