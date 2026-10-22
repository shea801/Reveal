from datetime import date
import json
import sqlite3

import pandas as pd

from data_access.PipelineETL import _has_annual_statement_history
from data_access.PipelineETL import FinancialData
from data_ingestion.DataExtraction import DataExtraction
import minimum_viable_product as legacy_mvp
from mvp import service as mvp
from scripts import analyze_security as mvp_cli

def test_has_annual_statement_history_accepts_distinct_periods_with_span():
    df = pd.DataFrame(
        {
            "fiscalDateEnding": pd.date_range(
                "2015-12-31",
                periods=10,
                freq="YE",
            )
        }
    )

    assert _has_annual_statement_history(df, years=10)


def test_has_annual_statement_history_rejects_duplicate_dates():
    df = pd.DataFrame({"fiscalDateEnding": ["2024-12-31"] * 10})

    assert not _has_annual_statement_history(df, years=10)


def test_has_annual_statement_history_rejects_short_date_span():
    df = pd.DataFrame(
        {
            "fiscalDateEnding": pd.date_range(
                "2024-01-01",
                periods=10,
                freq="30D",
            )
        }
    )

    assert not _has_annual_statement_history(df, years=10)


def test_has_annual_statement_history_rejects_empty_missing_or_invalid_dates():
    assert not _has_annual_statement_history(pd.DataFrame(), years=10)
    assert not _has_annual_statement_history(
        pd.DataFrame({"not_dates": ["2024-12-31"]}),
        years=10,
    )
    assert not _has_annual_statement_history(
        pd.DataFrame({"fiscalDateEnding": ["not-a-date"]}),
        years=10,
    )


def test_build_security_analysis_result_attaches_warnings_and_marks_incomplete():
    result = mvp.build_security_analysis_result(
        financial_metrics={
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "company_description": "Consumer technology company.",
            "analysis_date": "2024-09-30",
        },
        defensive_values={},
        enterprising_values={},
        calculation_warnings=("Insufficient data for Defensive Graham analysis",),
    )

    assert result.calculation_warnings == (
        "Insufficient data for Defensive Graham analysis",
    )
    assert result.missing_fields == ()
    assert result.company_description == "Consumer technology company."
    assert not result.data_complete


def test_legacy_minimum_viable_product_import_reexports_package_api():
    assert legacy_mvp.SecurityAnalysisResult is mvp.SecurityAnalysisResult
    assert legacy_mvp.analyze_security is mvp.analyze_security
    assert (
        legacy_mvp.build_security_analysis_result
        is mvp.build_security_analysis_result
    )
    assert legacy_mvp.DEFENSIVE_CRITERIA_MAP is mvp.DEFENSIVE_CRITERIA_MAP
    assert legacy_mvp.ENTERPRISING_CRITERIA_MAP is mvp.ENTERPRISING_CRITERIA_MAP


def test_build_security_analysis_result_complete_when_identity_and_no_warnings():
    result = mvp.build_security_analysis_result(
        financial_metrics={
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "analysis_date": "2024-09-30",
        },
        defensive_values={},
        enterprising_values={},
    )

    assert result.analysis_date == date(2024, 9, 30)
    assert result.company_description is None
    assert result.calculation_warnings == ()
    assert result.missing_fields == ()
    assert result.data_complete


def test_build_security_analysis_result_maps_ttm_and_magic_formula_fields():
    result = mvp.build_security_analysis_result(
        financial_metrics={
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "analysis_date": "2024-09-30",
            "eps_ttm": 6.5,
            "net_income_ttm": 100.0,
            "ebit_ttm": 125.0,
            "financial_profile_return_on_capital": 0.18,
            "estimated_owner_earnings": 90.0,
            "estimated_owner_earnings_yield": 0.06,
            "eps_cagr_5yr": 0.09,
            "return_on_capital": 0.25,
            "earnings_yield": 0.08,
            "magic_formula_quarter_date": "2024-09-30",
            "magic_formula_associated_annual_date": "2023-12-31",
            "magic_formula_financial_statement_availability_date": "2024-11-01",
            "magic_formula_rank": 10,
            "return_on_capital_rank": 4,
            "earnings_yield_rank": 12,
            "total_roc_ey_score": 16,
        },
        defensive_values={},
        enterprising_values={},
    )

    assert result.eps_ttm == 6.5
    assert result.net_income_ttm == 100.0
    assert result.ebit_ttm == 125.0
    assert result.financial_profile_return_on_capital == 0.18
    assert result.estimated_owner_earnings == 90.0
    assert result.estimated_owner_earnings_yield == 0.06
    assert result.eps_cagr_5yr == 0.09
    assert result.magic_formula_quarter_date == "2024-09-30"
    assert result.magic_formula_associated_annual_date == "2023-12-31"
    assert result.magic_formula_rank == 10
    assert result.return_on_capital_rank == 4
    assert result.earnings_yield_rank == 12
    assert result.total_roc_ey_score == 16


def test_build_security_analysis_result_separates_graham_values_and_checks():
    result = mvp.build_security_analysis_result(
        financial_metrics={
            "ticker": "TEST",
            "company_name": "Test Co.",
            "analysis_date": "2024-12-31",
            "sector": "Industrials",
        },
        defensive_values={
            "currentAssets200pctCurrentLiabilities": 1.8,
            "averageDividendPayments20yr": float("nan"),
            "price15xEarningsPerShare3yrAverage": 16.0,
        },
        enterprising_values={
            "earningsTo5yrLookbackRatio": 1.2,
        },
        defensive_criteria={
            "currentAssetsGte200pctCurrentLiabilities": False,
            "continuousDividendPayments20yr": pd.NA,
        },
        enterprising_criteria={
            "earningsGreaterThan5yrLookback": True,
        },
    )

    assert result.current_assets_to_current_liabilities_ratio == 1.8
    assert result.current_assets_200pct_or_greater_current_liabilities_met is False
    assert result.average_dividend_payments_for_past_20yrs is None
    assert result.continuous_dividend_payments_for_past_20yrs_met is None
    assert result.earnings_to_5yr_earnings_lookback_ratio == 1.2
    assert result.earnings_growth_greater_than_5yrs_previous_met is True
    assert result.defensive_criteria_met is False
    assert result.enterprising_criteria_met is None


def test_industrial_result_applies_working_capital_not_utility_test():
    result = mvp.build_security_analysis_result(
        financial_metrics={
            "ticker": "TEST",
            "company_name": "Test Co.",
            "analysis_date": "2024-12-31",
            "sector": "Industrials",
        },
        defensive_values={},
        enterprising_values={},
        defensive_criteria={
            "totalSalesServicesGteMinimum": True,
            "currentAssetsGte200pctCurrentLiabilities": False,
            "utilityDebtLte200pctBookEquity": True,
        },
    )

    assert result.defensive_criteria_met is False
    assert "utility_debt_to_book_equity_met" in result.not_applicable_fields
    assert (
        "current_assets_200pct_or_greater_current_liabilities_met"
        not in result.not_applicable_fields
    )


def test_utility_result_applies_utility_test_and_excludes_magic_formula():
    result = mvp.build_security_analysis_result(
        financial_metrics={
            "ticker": "TEST",
            "company_name": "Test Utility",
            "analysis_date": "2024-12-31",
            "sector": "Utilities",
        },
        defensive_values={},
        enterprising_values={},
        defensive_criteria={
            "totalSalesServicesGteMinimum": True,
            "currentAssetsGte200pctCurrentLiabilities": False,
            "utilityDebtLte200pctBookEquity": True,
        },
    )

    assert result.defensive_criteria_met is None
    assert (
        "current_assets_200pct_or_greater_current_liabilities_met"
        in result.not_applicable_fields
    )
    assert "utility_debt_to_book_equity_met" not in result.not_applicable_fields
    assert (
        "long_term_debt_to_net_current_assets_ratio"
        not in result.not_applicable_fields
    )
    assert "magic_formula_rank" in result.not_applicable_fields
    assert "return_on_capital" in result.not_applicable_fields


def test_build_security_analysis_result_incomplete_when_required_identity_missing():
    result = mvp.build_security_analysis_result(
        financial_metrics={
            "ticker": "AAPL",
            "analysis_date": "2024-09-30",
        },
        defensive_values={},
        enterprising_values={},
    )

    assert result.missing_fields == ("company_name",)
    assert not result.data_complete


class _FakeFinancialAssessment:
    def __init__(self, ticker, date=None):
        self.ticker = ticker
        self.date = date

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "company_name": "Test Co.",
            "company_description": "Test company description.",
            "analysis_date": self.date or "2024-12-31",
            "market_cap": 1000.0,
        }


class _FakeDefensiveValues:
    def __init__(self, ticker):
        self.ticker = ticker

    def get_by_date(self, analysis_date):
        return {
            "currentAssets200pctCurrentLiabilities": 2.5,
            "longTermDebtToNetCurrentAssets": 0.5,
            "eps3yrAverageTo10yrPreviousEPSRatio": 1.4,
            "averageDividendPayments20yr": None,
            "price15xEarningsPerShare3yrAverage": 12.0,
            "price150pctBookValue": 1.2,
            "grahamNumber": 50.0,
        }


class _FakeEnterprisingValues:
    def __init__(self, ticker):
        self.ticker = ticker

    def get_by_date(self, analysis_date):
        return {
            "currentAssets150pctLongTermDebt": 1.8,
            "longTermDebt110pctNetCurrentAssets": 0.5,
            "earningsTo5yrLookbackRatio": 1.25,
            "price120pctTangibleBook": 1.1,
            "serenityNumber": 40.0,
        }


class _FakeDefensiveInvestor:
    @classmethod
    def from_values(cls, values):
        return cls()

    def criteria_dataframe(self, minimum_revenue=None):
        return pd.DataFrame({
            "fiscalDateEnding": ["2024-12-31"],
            "totalSalesServicesGteMinimum": [True],
            "currentAssetsGte200pctCurrentLiabilities": [True],
            "longTermDebtLessThanNetCurrentAssets": [True],
            "utilityDebtLte200pctBookEquity": [None],
            "positiveEarnings10yr": [True],
            "eps3yrAverageGte33pct10yrPreviousEPS": [True],
            "continuousDividendPayments20yr": [None],
            "priceLte15xEPS": [True],
            "priceLte150pctBV": [True],
        })


def test_assess_security_eligibility_accepts_supported_common_stock():
    result = mvp.assess_security_eligibility(
        " test ",
        details_provider=lambda ticker: {
            "Name": "Test Co.",
            "AssetType": "Common Stock",
            "Exchange": "NASDAQ",
            "MarketCapitalization": "500000000",
        },
        history_checker=lambda ticker, years: (ticker, years) == ("TEST", 5),
    )

    assert result.ticker == "TEST"
    assert result.eligible
    assert result.reasons == ()


def test_assess_security_eligibility_reports_each_failed_requirement():
    result = mvp.assess_security_eligibility(
        "bad",
        details_provider=lambda ticker: {
            "Name": "Bad Co. Warrant",
            "AssetType": "Warrant",
            "Exchange": "OTC",
            "MarketCapitalization": 100_000_000,
        },
        history_checker=lambda ticker, years: False,
    )

    assert not result.eligible
    assert len(result.reasons) == 4
    assert "not eligible common stock" in result.reasons[0]
    assert "not a supported major U.S. exchange" in result.reasons[1]
    assert "$250 million" in result.reasons[2]
    assert "five years" in result.reasons[3]


class _FakeEnterprisingInvestor:
    @classmethod
    def from_values(cls, values):
        return cls()

    def criteria_dataframe(self):
        return pd.DataFrame({
            "fiscalDateEnding": ["2024-12-31"],
            "currentAssetsGte150pctLongTermDebt": [True],
            "longTermDebtLte110pctNetCurrentAssets": [True],
            "positiveEarnings5yr": [True],
            "earningsGreaterThan5yrLookback": [True],
            "priceLte120pctTangibleAssets": [True],
        })


def _mock_graham_investors(monkeypatch):
    monkeypatch.setattr(mvp, "DefensiveInvestor", _FakeDefensiveInvestor)
    monkeypatch.setattr(mvp, "EnterprisingInvestor", _FakeEnterprisingInvestor)


def test_analyze_security_complete_when_both_graham_sections_available(monkeypatch):
    monkeypatch.setattr(mvp, "FA", _FakeFinancialAssessment)
    monkeypatch.setattr(mvp, "DICV", _FakeDefensiveValues)
    monkeypatch.setattr(mvp, "EICV", _FakeEnterprisingValues)
    _mock_graham_investors(monkeypatch)
    monkeypatch.setattr(mvp, "has_defensive_history", lambda ticker: True)
    monkeypatch.setattr(mvp, "has_enterprising_history", lambda ticker: True)

    result = mvp.analyze_security("TEST", analysis_date="2024-12-31")

    assert result.data_complete
    assert result.company_description == "Test company description."
    assert result.calculation_warnings == ()
    assert result.current_assets_to_current_liabilities_ratio == 2.5
    assert result.current_assets_200pct_or_greater_current_liabilities_met is True
    assert (
        result.current_assets_150pct_or_greater_than_long_term_debt_ratio
        == 1.8
    )
    assert result.current_assets_150pct_or_greater_long_term_debt_met is True
    assert result.continuous_dividend_payments_for_past_20yrs_met is None
    assert result.defensive_criteria_met is None
    assert result.enterprising_criteria_met is True


def test_analyze_security_partial_when_defensive_unavailable(monkeypatch):
    monkeypatch.setattr(mvp, "FA", _FakeFinancialAssessment)
    monkeypatch.setattr(mvp, "DICV", _FakeDefensiveValues)
    monkeypatch.setattr(mvp, "EICV", _FakeEnterprisingValues)
    _mock_graham_investors(monkeypatch)
    monkeypatch.setattr(mvp, "has_defensive_history", lambda ticker: False)
    monkeypatch.setattr(mvp, "has_enterprising_history", lambda ticker: True)

    result = mvp.analyze_security("TEST", analysis_date="2024-12-31")

    assert not result.data_complete
    assert result.calculation_warnings == (
        "Insufficient data for Defensive Graham analysis",
    )
    assert result.company_name == "Test Co."
    assert result.current_assets_to_current_liabilities_ratio is None
    assert result.current_assets_200pct_or_greater_current_liabilities_met is None
    assert (
        result.current_assets_150pct_or_greater_than_long_term_debt_ratio
        == 1.8
    )


def test_analyze_security_partial_when_both_graham_sections_unavailable(monkeypatch):
    monkeypatch.setattr(mvp, "FA", _FakeFinancialAssessment)
    monkeypatch.setattr(mvp, "DICV", _FakeDefensiveValues)
    monkeypatch.setattr(mvp, "EICV", _FakeEnterprisingValues)
    monkeypatch.setattr(mvp, "has_defensive_history", lambda ticker: False)
    monkeypatch.setattr(mvp, "has_enterprising_history", lambda ticker: False)

    result = mvp.analyze_security("TEST", analysis_date="2024-12-31")

    assert not result.data_complete
    assert result.calculation_warnings == (
        "Insufficient data for Defensive Graham analysis",
        "Insufficient data for Enterprising Graham analysis",
    )
    assert result.company_name == "Test Co."
    assert result.market_cap == 1000.0


def test_mvp_cli_outputs_single_security_json(monkeypatch, capsys):
    def fake_analyze_security(ticker, analysis_date=None):
        assert ticker == "TEST"
        assert analysis_date == "2024-12-31"
        return mvp.SecurityAnalysisResult(
            ticker=ticker,
            company_name="Test Co.",
            analysis_date=date(2024, 12, 31),
            market_cap=1000.0,
        )

    monkeypatch.setattr(
        mvp_cli.mvp_service,
        "analyze_security",
        fake_analyze_security,
    )

    exit_code = mvp_cli.main(["test", "--analysis-date", "2024-12-31"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ticker"] == "TEST"
    assert output["company_name"] == "Test Co."
    assert output["analysis_date"] == "2024-12-31"
    assert output["market_cap"] == 1000.0


def test_eligible_common_stock_analysis_single_ticker_returns_contract_dict(monkeypatch):
    def fake_analyze_security(ticker, analysis_date=None):
        assert ticker == "TEST"
        assert analysis_date == "2024-12-31"
        return mvp.SecurityAnalysisResult(
            ticker=ticker,
            company_name="Test Co.",
            analysis_date=date(2024, 12, 31),
            market_cap=1000.0,
            current_assets_to_current_liabilities_ratio=2.2,
            current_assets_150pct_or_greater_than_long_term_debt_ratio=1.7,
            data_complete=False,
            calculation_warnings=("example warning",),
        )

    monkeypatch.setattr(mvp, "analyze_security", fake_analyze_security)
    monkeypatch.setattr(
        mvp,
        "_investment_criteria_met",
        lambda result, investor_type=None: result,
    )

    result = mvp.eligible_common_stock_analysis(
        "test",
        analysis_date="2024-12-31",
    )

    assert result["ticker"] == "TEST"
    assert result["analysis_date"] == "2024-12-31"
    assert result["current_assets_to_current_liabilities_ratio"] == 2.2
    assert (
        result[
            "current_assets_150pct_or_greater_than_long_term_debt_ratio"
        ]
        == 1.7
    )
    assert result["data_complete"] is False
    assert result["calculation_warnings"] == ("example warning",)


def test_eligible_common_stock_analysis_all_tickers_handles_missing_ticker(monkeypatch):
    monkeypatch.setattr(mvp, "eligible_common_stock_tickers", lambda: ["AAA", "BBB"])
    monkeypatch.setattr(
        mvp,
        "analyze_security",
        lambda ticker, analysis_date=None: mvp.SecurityAnalysisResult(
            ticker=ticker,
            company_name=f"{ticker} Co.",
            analysis_date=date(2024, 12, 31),
        ),
    )
    monkeypatch.setattr(
        mvp,
        "_investment_criteria_met",
        lambda result, investor_type=None: result,
    )

    result = mvp.eligible_common_stock_analysis(analysis_date="2024-12-31")

    assert sorted(result) == ["AAA", "BBB"]
    assert result["AAA"]["ticker"] == "AAA"
    assert result["BBB"]["company_name"] == "BBB Co."


def test_eligible_common_stock_analysis_validates_investor_type():
    try:
        mvp.eligible_common_stock_analysis("TEST", investor_type="growth")
    except ValueError as exc:
        assert "investor_type" in str(exc)
    else:
        raise AssertionError("Expected invalid investor_type to raise ValueError")


def test_eligible_common_stock_analysis_defensive_output_excludes_enterprising(monkeypatch):
    monkeypatch.setattr(
        mvp,
        "analyze_security",
        lambda ticker, analysis_date=None: mvp.SecurityAnalysisResult(
            ticker=ticker,
            company_name="Test Co.",
            analysis_date=date(2024, 12, 31),
            current_assets_to_current_liabilities_ratio=2.1,
            current_assets_150pct_or_greater_than_long_term_debt_ratio=1.8,
        ),
    )
    monkeypatch.setattr(
        mvp,
        "_investment_criteria_met",
        lambda result, investor_type=None: result,
    )

    result = mvp.eligible_common_stock_analysis("TEST", investor_type="defensive")

    assert "current_assets_to_current_liabilities_ratio" in result
    assert (
        "current_assets_150pct_or_greater_than_long_term_debt_ratio"
        not in result
    )


def test_investment_criteria_met_adds_compatibility_aliases():
    result = mvp._investment_criteria_met({
        "ticker": "TEST",
        "analysis_date": "2024-12-31",
        "current_assets_200pct_or_greater_current_liabilities_met": True,
        "defensive_criteria_met": True,
        "price_120pct_or_less_tangible_book_met": False,
        "enterprising_criteria_met": False,
    })

    assert result["defensive_criteria_met"] is True
    assert result["enterprising_criteria_met"] is False
    assert result[
        "defensive_criteria_currentAssetsGte200pctCurrentLiabilities"
    ] is True
    assert result[
        "enterprising_criteria_priceLte120pctTangibleAssets"
    ] is False


def test_investment_criteria_met_returns_dict_for_one_strategy():
    result = mvp._investment_criteria_met(
        {
            "ticker": "TEST",
            "analysis_date": "2024-12-31",
            "current_assets_200pct_or_greater_current_liabilities_met": True,
            "defensive_criteria_met": True,
        },
        investor_type="defensive",
    )

    assert isinstance(result, dict)
    assert result["defensive_criteria_met"] is True
    assert "enterprising_criteria_met" not in result


def test_etf_profile_api_call_to_file_uses_etf_path_key(monkeypatch, tmp_path):
    etf_profile_path = tmp_path / "ETF_Securities" / "TEST__ETF" / "TEST_etf_profile.json"

    monkeypatch.setattr(
        "data_ingestion.DataExtraction.make_alphavantage_api_call",
        lambda ticker, key: {"symbol": ticker, "net_assets": "1000"} if key == "etf" else None,
    )
    monkeypatch.setattr(
        "data_ingestion.TickerFileSearch.TickerSearch.ticker_file_pathways",
        lambda self, ticker: {"etf": str(etf_profile_path)},
    )

    DataExtraction("TEST").etf_profile_api_call_to_file()

    assert json.loads(etf_profile_path.read_text()) == {
        "symbol": "TEST",
        "net_assets": "1000",
    }


def test_company_market_info_handles_missing_market_cap(monkeypatch):
    class FakeCompanyDetails:
        def get_details(self, ticker):
            return {
                "Name": None,
                "AssetType": None,
                "FiscalYearEnd": "December",
                "LatestQuarter": "2024-09-30",
                "Sector": "ETF",
                "Industry": "Broad Market",
            }

    class FakeTickerSearch:
        def ticker_search_information(self, ticker):
            return {
                "2. name": "Test ETF",
                "3. type": "ETF",
            }

    import data_access.CompanyDetails as company_details_module
    import data_ingestion.TickerFileSearch as ticker_search_module

    monkeypatch.setattr(company_details_module, "CompanyDetails", FakeCompanyDetails)
    monkeypatch.setattr(ticker_search_module, "TickerSearch", FakeTickerSearch)

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE sec_tickers (ticker TEXT)")
    conn.execute("INSERT INTO sec_tickers VALUES ('TEST')")
    conn.execute(
        """
        CREATE TABLE market_capitalization (
            ticker TEXT,
            marketCapitalization REAL,
            marketCapGroup TEXT
        )
        """
    )

    pipeline = FinancialData.__new__(FinancialData)
    pipeline.conn = conn

    result = pipeline.company_market_fye_quarter_sector_industry_info()

    assert result.loc["TEST", "name"] == "Test ETF"
    assert result.loc["TEST", "asset_type"] == "ETF"
    assert result.loc["TEST", "market_cap"] == 0
    assert pd.isna(result.loc["TEST", "market_cap_group"])
