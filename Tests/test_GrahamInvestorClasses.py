import numpy as np
import pandas as pd

from analytics.GrahamInvestorClasses import (
    DEFENSIVE_MIN_REVENUE,
    DEFENSIVE_UTILITY_MIN_REVENUE,
    DefensiveInvestor,
    defensive_min_revenue_for_sector,
)


def _sample_defensive_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fiscalDateEnding": pd.date_range(
                "2024-12-31",
                periods=10,
                freq="-1YE",
            ).strftime("%Y-%m-%d"),
            "totalRevenue": [150_000_000] * 10,
            "totalCurrentAssets": [80_000_000] * 10,
            "totalCurrentLiabilities": [20_000_000] * 10,
            "longTermDebt": [10_000_000] * 10,
            "totalAssets": [200_000_000] * 10,
            "totalLiabilities": [80_000_000] * 10,
            "commonStockSharesOutstanding": [10_000_000] * 10,
            "reportedEPS": [4.0, 4.2, 3.8, 3.4, 3.1, 3.0, 2.9, 2.8, 2.7, 2.6],
            "netIncome": [40_000_000] * 10,
            "dividendPayoutCommonStock": [1.25] * 10,
            "commonStockDividendPaid": [True] * 10,
            "closingSharePrice": [40.0] * 10,
        }
    )


def test_graham_number_uses_three_year_average_eps_and_book_value():
    investor = DefensiveInvestor.from_dataframe(_sample_defensive_df())

    result = investor.graham_number

    assert np.isclose(result.iloc[0], np.sqrt(22.5 * 4.0 * 12.0))


def test_positive_earnings_requires_positive_net_income_across_lookback():
    investor = DefensiveInvestor.from_dataframe(_sample_defensive_df())

    result = investor.pos_earnings(period=10)

    assert result.iloc[0]


def test_positive_earnings_fails_when_net_income_is_negative_in_lookback():
    df = _sample_defensive_df()
    df.loc[5, "netIncome"] = -1.0
    investor = DefensiveInvestor.from_dataframe(df)

    result = investor.pos_earnings(period=10)

    assert not result.iloc[0]


def test_defensive_revenue_uses_general_and_utility_thresholds():
    df = _sample_defensive_df()
    df["totalRevenue"] = 300_000_000
    investor = DefensiveInvestor.from_dataframe(df)

    general = investor.total_sales_services(DEFENSIVE_MIN_REVENUE)
    utility = investor.total_sales_services(DEFENSIVE_UTILITY_MIN_REVENUE)

    assert not general.iloc[0]
    assert utility.iloc[0]
    assert defensive_min_revenue_for_sector("Utilities") == 250_000_000
    assert defensive_min_revenue_for_sector("Industrials") == 500_000_000


def test_utility_debt_to_book_equity_uses_two_times_limit():
    investor = DefensiveInvestor.from_dataframe(_sample_defensive_df())

    ratio = investor.values.long_term_debt_to_book_equity()
    criterion = investor.utility_debt_to_book_equity()

    assert np.isclose(ratio.iloc[0], 10_000_000 / 120_000_000)
    assert criterion.iloc[0]
