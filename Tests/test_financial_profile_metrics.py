import pandas as pd
import pytest

from analytics.FinancialAssessment import FinancialAssessment


class _StatementAccessor:
    def __init__(self, current, annual):
        self.current = current
        self.annual_data = pd.DataFrame(annual)

    def get_by_date(self, _date, quarterly=False):
        return dict(self.current)

    def annual(self):
        return self.annual_data.copy()


class _PriceAccessor:
    def __init__(self, close):
        self.close = close

    def price_on_date(self, _date):
        return {"date": _date, "close": self.close}


def _build_assessment():
    current_balance_sheet = {
        "fiscalDateEnding": "2024-12-31",
        "totalAssets": 1_000.0,
        "totalLiabilities": 500.0,
        "totalCurrentAssets": 600.0,
        "totalCurrentLiabilities": 400.0,
        "totalShareholderEquity": 500.0,
        "shortLongTermDebtTotal": 200.0,
        "cashAndShortTermInvestments": 100.0,
        "cashAndCashEquivalentsAtCarryingValue": 80.0,
        "commonStockSharesOutstanding": 100.0,
        "propertyPlantEquipment": 300.0,
        "accumulatedDepreciationAmortizationPPE": 50.0,
    }
    prior_balance_sheet = {
        "fiscalDateEnding": "2023-12-31",
        "totalAssets": 900.0,
        "totalLiabilities": 450.0,
        "totalCurrentLiabilities": 350.0,
        "totalShareholderEquity": 450.0,
        "shortLongTermDebtTotal": 180.0,
        "cashAndShortTermInvestments": 90.0,
    }
    current_income = {
        "fiscalDateEnding": "2024-12-31",
        "totalRevenue": 600.0,
        "ebit": 120.0,
        "incomeBeforeTax": 100.0,
        "incomeTaxExpense": 20.0,
    }
    annual_income = [
        {"fiscalDateEnding": f"{year}-12-31"}
        for year in range(2024, 2018, -1)
    ]
    annual_earnings = [
        {"fiscalDateEnding": f"{year}-12-31", "reportedEPS": eps}
        for year, eps in zip(
            range(2024, 2018, -1),
            (4.0, 3.6, 3.2, 2.8, 2.4, 2.0),
        )
    ]

    assessment = FinancialAssessment.__new__(FinancialAssessment)
    assessment._ticker = "TEST"
    assessment._date = "2025-03-31"
    assessment._annual_fin_analysis_date = "2024-12-31"
    assessment._share_price_analysis_date = "2025-03-31"
    assessment._ttm = {"ebitTTM": 120.0}
    assessment._bs = _StatementAccessor(
        current_balance_sheet,
        [current_balance_sheet, prior_balance_sheet],
    )
    assessment._cf = _StatementAccessor(
        {
            "fiscalDateEnding": "2024-12-31",
            "operatingCashflow": 150.0,
            "capitalExpenditures": 30.0,
        },
        [],
    )
    assessment._is = _StatementAccessor(current_income, annual_income)
    assessment._er = _StatementAccessor(
        {"fiscalDateEnding": "2024-12-31", "reportedEPS": 4.0},
        annual_earnings,
    )
    assessment._ohlcv = _PriceAccessor(close=10.0)
    return assessment


def test_seven_frozen_financial_profile_metrics_use_expected_formulas():
    assessment = _build_assessment()

    assert assessment.return_on_invested_capital() == pytest.approx(96 / 570)
    assert assessment.financial_profile_return_on_capital() == pytest.approx(
        120 / 575
    )
    assert assessment.free_cash_flow_margin() == pytest.approx(120 / 600)
    assert assessment.estimated_owner_earnings() == 120.0
    assert assessment.estimated_owner_earnings_yield() == pytest.approx(
        120 / 1_000
    )
    assert assessment.debt_to_assets() == pytest.approx(200 / 1_000)
    assert assessment.net_debt_to_free_cash_flow() == pytest.approx(100 / 120)
    assert assessment.eps_cagr_5yr() == pytest.approx(
        (4 / 2.4) ** (1 / 4) - 1
    )


def test_financial_profile_and_magic_formula_roc_are_distinct_metrics():
    assessment = _build_assessment()

    assert assessment.financial_profile_return_on_capital() == pytest.approx(
        120 / 575
    )
    assert assessment.return_on_capital() == pytest.approx(120 / 470)


def test_negative_free_cash_flow_remains_valid_for_margin_and_eoey():
    assessment = _build_assessment()
    assessment._cf.current["operatingCashflow"] = 10.0

    assert assessment.free_cash_flow() == -20.0
    assert assessment.free_cash_flow_margin() == pytest.approx(-20 / 600)
    assert assessment.estimated_owner_earnings_yield() == pytest.approx(
        -20 / 1_000
    )
    assert assessment.net_debt_to_free_cash_flow() is None


def test_zero_debt_is_valid_and_negative_net_debt_is_preserved():
    assessment = _build_assessment()
    assessment._bs.current["shortLongTermDebtTotal"] = 0.0

    assert assessment.debt_to_assets() == 0.0
    assert assessment.net_debt_to_free_cash_flow() == pytest.approx(-100 / 120)


def test_missing_inputs_are_not_silently_converted_to_zero():
    assessment = _build_assessment()
    del assessment._cf.current["operatingCashflow"]
    del assessment._bs.current["shortLongTermDebtTotal"]

    assert assessment.free_cash_flow() is None
    assert assessment.free_cash_flow_margin() is None
    assert assessment.estimated_owner_earnings_yield() is None
    assert assessment.debt_to_assets() is None
    assert assessment.net_debt_to_free_cash_flow() is None


def test_capital_returns_require_a_prior_annual_balance_sheet():
    assessment = _build_assessment()
    assessment._bs.annual_data = assessment._bs.annual_data.iloc[:1]

    assert assessment.return_on_invested_capital() is None
    assert assessment.financial_profile_return_on_capital() is None


@pytest.mark.parametrize("invalid_eps", [0.0, -1.0, None])
def test_eps_cagr_requires_positive_endpoints(invalid_eps):
    assessment = _build_assessment()
    assessment._er.annual_data.loc[
        assessment._er.annual_data["fiscalDateEnding"] == "2020-12-31",
        "reportedEPS",
    ] = invalid_eps

    assert assessment.eps_cagr_5yr() is None


def test_eps_cagr_requires_five_aligned_annual_periods():
    assessment = _build_assessment()
    assessment._is.annual_data = assessment._is.annual_data[
        assessment._is.annual_data["fiscalDateEnding"] != "2021-12-31"
    ]

    assert assessment.eps_cagr_5yr() is None
