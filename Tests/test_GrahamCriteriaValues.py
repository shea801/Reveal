import numpy as np
import pandas as pd

from analytics.GrahamInvestorClasses import (
    DEFENSIVE_EPS_GROWTH_MIN,
    DefensiveInvestor,
    DefensiveInvestorCriteriaValues,
    EnterprisingInvestor,
    EnterprisingInvestorCriteriaValues,
)


def _annual_df(years: int = 10) -> pd.DataFrame:
    fiscal_dates = pd.date_range("2024-12-31", periods=years, freq="-1YE")
    reported_eps = [4.0, 4.2, 3.8, 3.4, 3.1, 3.0, 2.9, 2.8, 2.7, 2.6]
    if years > len(reported_eps):
        reported_eps.extend([2.5] * (years - len(reported_eps)))

    return pd.DataFrame(
        {
            "fiscalDateEnding": fiscal_dates.strftime("%Y-%m-%d"),
            "totalRevenue": [150_000_000] * years,
            "totalCurrentAssets": [80_000_000] * years,
            "totalCurrentLiabilities": [20_000_000] * years,
            "longTermDebt": [10_000_000] * years,
            "totalLiabilities": [80_000_000] * years,
            "reportedEPS": reported_eps[:years],
            "netIncome": [eps * 10_000_000 for eps in reported_eps[:years]],
            "dividendPayoutCommonStock": [1.25] * years,
            "commonStockDividendPaid": [True] * years,
            "closingSharePrice": [40.0] * years,
            "totalAssets": [200_000_000] * years,
            "intangibleAssets": [10_000_000] * years,
            "goodwill": [5_000_000] * years,
            "preferredStock": [0] * years,
            "commonStockSharesOutstanding": [10_000_000] * years,
        }
    )


def test_defensive_criteria_values_return_calculated_series():
    values = DefensiveInvestorCriteriaValues.from_dataframe(_annual_df())

    assert values.total_sales_services().iloc[0] == 150_000_000
    assert values.curr_assets_2x_curr_liab().iloc[0] == 4.0
    assert np.isclose(values.long_debt_to_curr_assets().iloc[0], 1 / 6)
    assert np.isclose(
        values.price_15x_EPS().iloc[0],
        40.0 / np.mean([4.0, 4.2, 3.8]),
    )
    assert np.isclose(values.price_150pct_BV().iloc[0], 40.0 / 12.0)


def test_defensive_eps_growth_uses_three_year_average_eps_not_book_value():
    values = DefensiveInvestorCriteriaValues.from_dataframe(_annual_df())

    growth = values.eps_growth_10yr().iloc[0]

    current_avg = np.mean([4.0, 4.2, 3.8])
    beginning_avg = np.mean([2.8, 2.7, 2.6])
    assert np.isclose(growth, (current_avg / beginning_avg) - 1)
    assert growth >= DEFENSIVE_EPS_GROWTH_MIN
    assert np.isclose(
        values.eps_3yr_average_to_10yr_previous_eps_ratio().iloc[0],
        current_avg / beginning_avg,
    )


def test_defensive_twenty_year_dividend_fields_require_full_history():
    ten_year_values = DefensiveInvestorCriteriaValues.from_dataframe(_annual_df())
    twenty_year_values = DefensiveInvestorCriteriaValues.from_dataframe(
        _annual_df(years=20)
    )

    assert np.isnan(ten_year_values.average_dividend_payments().iloc[0])
    assert pd.isna(
        DefensiveInvestor.from_dataframe(_annual_df()).divpayments().iloc[0]
    )
    assert twenty_year_values.average_dividend_payments().iloc[0] == 1.25
    assert DefensiveInvestor.from_dataframe(_annual_df(years=20)).divpayments().iloc[0]


def test_defensive_dividend_record_fails_for_a_covered_no_payment_year():
    df = _annual_df(years=20)
    df.loc[8, "commonStockDividendPaid"] = False

    result = DefensiveInvestor.from_dataframe(df).divpayments()

    assert not bool(result.iloc[0])


def test_defensive_dividend_record_is_unavailable_for_incomplete_coverage():
    df = _annual_df(years=20)
    df["commonStockDividendPaid"] = df["commonStockDividendPaid"].astype(
        "boolean"
    )
    df.loc[8, "commonStockDividendPaid"] = pd.NA

    result = DefensiveInvestor.from_dataframe(df).divpayments()

    assert pd.isna(result.iloc[0])


def test_defensive_criteria_values_return_latest_annual_dict():
    values = DefensiveInvestorCriteriaValues.from_dataframe(_annual_df())

    latest = values.latest_annual()

    assert latest["ticker"] == "TEST"
    assert latest["fiscalDateEnding"] == "2024-12-31"
    assert latest["totalSalesServices"] == 150_000_000
    assert np.isclose(latest["price15xEarningsPerShare3yrAverage"], 10.0)
    assert np.isclose(latest["grahamNumber"], np.sqrt(22.5 * 4.0 * 12.0))


def test_enterprising_criteria_values_return_calculated_series_and_dict():
    values = EnterprisingInvestorCriteriaValues.from_dataframe(_annual_df(), min_years=5)

    assert values.current_assets_150pct_long_term_debt().iloc[0] == 6.0
    assert np.isclose(
        values.long_term_debt_110pct_net_current_assets().iloc[0],
        10_000_000 / 60_000_000,
    )
    assert np.isclose(
        values.price_120pct_tangible_assets().iloc[0],
        40.0 / 10.5,
    )

    latest = values.latest_annual()

    assert latest["ticker"] == "TEST"
    assert latest["fiscalDateEnding"] == "2024-12-31"
    assert latest["dividendPayout"] == 1.25
    assert latest["positiveEarnings5yr"] == 40_000_000
    assert np.isclose(latest["earningsTo5yrLookbackRatio"], 4.0 / 3.0)
    assert np.isclose(
        latest["earningsGrowth5yr"],
        ((4.0 / 3.0) ** (1 / 5)) - 1,
    )


def test_boolean_investor_classes_are_derived_from_value_classes():
    df = _annual_df()

    defensive = DefensiveInvestor.from_dataframe(df)
    enterprising = EnterprisingInvestor.from_dataframe(df)

    assert defensive.curr_assets_2x_curr_liab().iloc[0]
    assert defensive.eps_3yr_average_gte_33pct_10yr_previous().iloc[0]
    assert enterprising.current_assets_gte_150pct_long_term_debt.iloc[0]
    assert enterprising.some_current_dividend().iloc[0]
    assert enterprising.earnings_greater_than_5yr_lookback().iloc[0]
