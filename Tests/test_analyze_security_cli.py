from datetime import date
import json

from scripts import analyze_security as cli


CONTRACT_KEYS = {
    "ticker",
    "company_name",
    "analysis_date",
    "price_date",
    "annual_financial_statement_analysis_date",
    "quarter_financial_statement_analysis_date",
    "market_price_for_period",
    "min_200_day_price",
    "max_200_day_price",
    "avg_price_200_day",
    "median_price_200_day",
    "market_cap",
    "market_cap_group",
    "sector",
    "industry",
    "total_sales_services",
    "price_to_earnings",
    "eps",
    "eps_ttm",
    "net_income_ttm",
    "ebit_ttm",
    "period_three_year_average_eps",
    "tangible_book_value_per_share",
    "graham_number",
    "serenity_number",
    "defensive_margin_of_safety",
    "enterprising_margin_of_safety",
    "defensive_revenue_requirement_met",
    "current_assets_200pct_or_greater_current_liabilities_met",
    "current_assets_to_current_liabilities_ratio",
    "current_assets_150pct_or_greater_long_term_debt_met",
    "current_assets_150pct_or_greater_than_long_term_debt_ratio",
    "long_term_debt_less_than_net_current_assets_met",
    "long_term_debt_to_net_current_assets_ratio",
    "utility_debt_to_book_equity_met",
    "long_term_debt_to_book_equity_ratio",
    "long_term_debt_110pct_or_less_to_net_current_assets_met",
    "positive_earnings_for_the_past_10_years_met",
    "eps_3yr_average_33pct_gte_10yr_previous_eps_met",
    "eps_3yr_average_to_10yr_previous_eps_ratio",
    "continuous_dividend_payments_for_past_20yrs_met",
    "average_dividend_payments_for_past_20yrs",
    "price_15x_or_less_eps_3yr_average_met",
    "price_to_eps_3yr_average",
    "price_150pct_or_less_book_value_met",
    "price_to_book_value",
    "no_earnings_deficit_for_5yrs_met",
    "earnings_growth_greater_than_5yrs_previous_met",
    "earnings_to_5yr_earnings_lookback_ratio",
    "price_120pct_or_less_tangible_book_met",
    "price_to_tangible_book_value",
    "debt_to_equity",
    "debt_to_assets",
    "longterm_debt_to_cash",
    "interest_coverage",
    "net_debt_to_free_cash_flow",
    "gross_margin",
    "free_cash_flow",
    "free_cash_flow_margin",
    "estimated_owner_earnings",
    "estimated_owner_earnings_yield",
    "operating_income",
    "inventory_turnover",
    "return_on_assets",
    "return_on_equity",
    "return_on_invested_capital",
    "financial_profile_return_on_capital",
    "eps_cagr_5yr",
    "return_on_capital",
    "earnings_yield",
    "magic_formula_quarter_date",
    "magic_formula_associated_annual_date",
    "magic_formula_financial_statement_availability_date",
    "magic_formula_rank",
    "return_on_capital_rank",
    "earnings_yield_rank",
    "total_roc_ey_score",
    "magic_formula_score",
    "defensive_criteria_met",
    "enterprising_criteria_met",
    "data_complete",
    "missing_fields",
    "calculation_warnings",
    "not_applicable_fields",
    "field_explanations",
}


def _contract_result(ticker="TEST", **overrides):
    result = {
        "ticker": ticker,
        "company_name": f"{ticker} Corp.",
        "analysis_date": date(2024, 12, 31),
        "price_date": "2024-12-30",
        "annual_financial_statement_analysis_date": "2023-12-31",
        "quarter_financial_statement_analysis_date": "2024-09-30",
        "market_price_for_period": 100.0,
        "min_200_day_price": 80.0,
        "max_200_day_price": 120.0,
        "avg_price_200_day": 101.5,
        "median_price_200_day": 100.5,
        "market_cap": 1_000_000.0,
        "market_cap_group": "Large",
        "sector": "Technology",
        "industry": "Software",
        "total_sales_services": 500_000.0,
        "price_to_earnings": 20.0,
        "eps": 5.0,
        "eps_ttm": 5.5,
        "net_income_ttm": 250_000.0,
        "ebit_ttm": 300_000.0,
        "period_three_year_average_eps": 4.8,
        "tangible_book_value_per_share": 20.0,
        "graham_number": 75.0,
        "serenity_number": 70.0,
        "defensive_margin_of_safety": 0.75,
        "enterprising_margin_of_safety": 0.70,
        "defensive_revenue_requirement_met": True,
        "current_assets_200pct_or_greater_current_liabilities_met": True,
        "current_assets_to_current_liabilities_ratio": 2.1,
        "current_assets_150pct_or_greater_long_term_debt_met": True,
        "current_assets_150pct_or_greater_than_long_term_debt_ratio": 1.8,
        "long_term_debt_less_than_net_current_assets_met": True,
        "long_term_debt_to_net_current_assets_ratio": 0.4,
        "utility_debt_to_book_equity_met": None,
        "long_term_debt_to_book_equity_ratio": None,
        "long_term_debt_110pct_or_less_to_net_current_assets_met": True,
        "positive_earnings_for_the_past_10_years_met": True,
        "eps_3yr_average_33pct_gte_10yr_previous_eps_met": True,
        "eps_3yr_average_to_10yr_previous_eps_ratio": 1.5,
        "continuous_dividend_payments_for_past_20yrs_met": None,
        "average_dividend_payments_for_past_20yrs": None,
        "price_15x_or_less_eps_3yr_average_met": False,
        "price_to_eps_3yr_average": 18.0,
        "price_150pct_or_less_book_value_met": False,
        "price_to_book_value": 4.0,
        "no_earnings_deficit_for_5yrs_met": True,
        "earnings_growth_greater_than_5yrs_previous_met": False,
        "earnings_to_5yr_earnings_lookback_ratio": 0.9,
        "price_120pct_or_less_tangible_book_met": False,
        "price_to_tangible_book_value": 5.0,
        "debt_to_equity": 0.2,
        "debt_to_assets": 0.1,
        "longterm_debt_to_cash": 0.3,
        "interest_coverage": 12.0,
        "net_debt_to_free_cash_flow": None,
        "gross_margin": 0.25,
        "free_cash_flow": 120_000.0,
        "free_cash_flow_margin": 0.24,
        "estimated_owner_earnings": 120_000.0,
        "estimated_owner_earnings_yield": 0.12,
        "operating_income": 200_000.0,
        "inventory_turnover": None,
        "return_on_assets": 0.15,
        "return_on_equity": 0.30,
        "return_on_invested_capital": 0.22,
        "financial_profile_return_on_capital": 0.25,
        "eps_cagr_5yr": 0.10,
        "return_on_capital": 0.30,
        "earnings_yield": 0.08,
        "magic_formula_quarter_date": "2024-09-30",
        "magic_formula_associated_annual_date": "2023-12-31",
        "magic_formula_financial_statement_availability_date": "2024-11-01",
        "magic_formula_rank": 12,
        "return_on_capital_rank": 8,
        "earnings_yield_rank": 16,
        "total_roc_ey_score": 24,
        "magic_formula_score": 0.38,
        "defensive_criteria_met": True,
        "enterprising_criteria_met": False,
        "data_complete": False,
        "missing_fields": (),
        "calculation_warnings": ("Synthetic warning",),
        "not_applicable_fields": ("utility_debt_to_book_equity_met",),
        "field_explanations": (
            (
                "utility_debt_to_book_equity_met",
                "The Utility test does not apply to this sector.",
            ),
        ),
    }
    result.update(overrides)
    return result


def test_cli_json_single_ticker_outputs_contract_shaped_result(
    monkeypatch,
    capsys,
):
    calls = []

    def fake_analyze_security(ticker, analysis_date=None):
        calls.append((ticker, analysis_date))
        return _contract_result(ticker)

    monkeypatch.setattr(cli.mvp_service, "analyze_security", fake_analyze_security)

    exit_code = cli.main(["test", "--analysis-date", "2024-12-31"])

    assert exit_code == 0
    assert calls == [("TEST", "2024-12-31")]
    output = json.loads(capsys.readouterr().out)
    assert set(output) == CONTRACT_KEYS
    assert output["ticker"] == "TEST"
    assert output["analysis_date"] == "2024-12-31"
    assert output["price_date"] == "2024-12-30"
    assert output["annual_financial_statement_analysis_date"] == "2023-12-31"
    assert output["quarter_financial_statement_analysis_date"] == "2024-09-30"
    assert output["net_debt_to_free_cash_flow"] is None
    assert output["inventory_turnover"] is None
    assert output["defensive_criteria_met"] is True
    assert output["enterprising_criteria_met"] is False
    assert output["data_complete"] is False
    assert output["missing_fields"] == []
    assert output["calculation_warnings"] == ["Synthetic warning"]
    assert output["not_applicable_fields"] == [
        "utility_debt_to_book_equity_met"
    ]


def test_cli_json_multiple_tickers_outputs_contract_result_list(
    monkeypatch,
    capsys,
):
    calls = []

    def fake_analyze_security(ticker, analysis_date=None):
        calls.append((ticker, analysis_date))
        return _contract_result(ticker, magic_formula_score=None)

    monkeypatch.setattr(cli.mvp_service, "analyze_security", fake_analyze_security)

    exit_code = cli.main(["aaa", "bbb", "--analysis-date", "2024-06-30"])

    assert exit_code == 0
    assert calls == [("AAA", "2024-06-30"), ("BBB", "2024-06-30")]
    output = json.loads(capsys.readouterr().out)
    assert isinstance(output, list)
    assert [row["ticker"] for row in output] == ["AAA", "BBB"]
    assert all(set(row) == CONTRACT_KEYS for row in output)
    assert [row["magic_formula_score"] for row in output] == [None, None]


def test_cli_text_output_prints_contract_summary_and_warnings(monkeypatch, capsys):
    def fake_analyze_security(ticker, analysis_date=None):
        return _contract_result(
            ticker,
            company_name="Text Mode Inc.",
            analysis_date="2024-12-31",
            data_complete=False,
            calculation_warnings=("Missing Defensive Graham history",),
        )

    monkeypatch.setattr(cli.mvp_service, "analyze_security", fake_analyze_security)

    exit_code = cli.main(["txt", "--analysis-date", "2024-12-31", "--format", "text"])

    assert exit_code == 0
    output = capsys.readouterr().out.splitlines()
    assert output == [
        "TXT: Text Mode Inc.",
        "analysis_date: 2024-12-31",
        "data_complete: False",
        "warnings: Missing Defensive Graham history",
    ]


def test_cli_text_output_omits_warning_line_when_no_warnings(monkeypatch, capsys):
    def fake_analyze_security(ticker, analysis_date=None):
        return _contract_result(
            ticker,
            data_complete=True,
            calculation_warnings=(),
        )

    monkeypatch.setattr(cli.mvp_service, "analyze_security", fake_analyze_security)

    exit_code = cli.main(["ok", "--format", "text"])

    assert exit_code == 0
    output = capsys.readouterr().out.splitlines()
    assert output == [
        "OK: OK Corp.",
        "analysis_date: 2024-12-31",
        "data_complete: True",
    ]
