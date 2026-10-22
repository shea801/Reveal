from datetime import date

from mvp.models import SecurityAnalysisResult
from mvp.service import historical_financial_profile_comparison


def _result(ticker="PRIMARY"):
    return SecurityAnalysisResult(
        ticker=ticker,
        company_name=f"{ticker} Company",
        analysis_date=date(2026, 10, 2),
    )


def _availability_provider(records):
    def provide(ticker, _analysis_date):
        return records.get(ticker, ())

    return provide


def _metric_provider(values, metric):
    def provide(ticker, annual_statement_date, _availability_date):
        value = values[(ticker, annual_statement_date)]
        if isinstance(value, dict):
            return value
        return {
            "annual_financial_statement_analysis_date": annual_statement_date,
            "price_date": annual_statement_date,
            metric: value,
        }

    return provide


def _annual_records(ticker, dates):
    return [{
        "ticker": ticker,
        "annual_statement_date": fiscal_date,
        "statement_availability_date": availability_date,
    } for fiscal_date, availability_date in dates]


def test_selected_history_uses_contiguous_exact_annual_metrics():
    metric = "return_on_invested_capital"
    dates = [
        ("2025-06-30", "2025-07-30"),
        ("2024-06-30", "2024-07-30"),
        ("2023-06-30", "2023-07-30"),
        ("2022-06-30", "2022-07-30"),
        ("2021-06-30", "2021-07-30"),
    ]
    values = {
        ("PRIMARY", fiscal_date): index / 10
        for index, (fiscal_date, _) in enumerate(reversed(dates), start=1)
    }

    comparison = historical_financial_profile_comparison(
        _result(),
        metric,
        availability_provider=_availability_provider({
            "PRIMARY": _annual_records("PRIMARY", dates),
        }),
        metric_provider=_metric_provider(values, metric),
    )

    assert comparison.applied_period == 5
    assert comparison.available_periods == (1, 3, 5, "all")
    assert comparison.anchor_fiscal_years == (2021, 2022, 2023, 2024, 2025)
    assert [item.value for item in comparison.series] == [0.1, 0.2, 0.3, 0.4, 0.5]
    assert all(item.price_date is None for item in comparison.series)
    assert comparison.warning_codes == ()


def test_peer_history_aligns_by_recency_and_discloses_large_fiscal_offset():
    metric = "free_cash_flow_margin"
    selected_dates = [
        ("2025-06-30", "2025-07-30"),
        ("2024-06-30", "2024-07-30"),
        ("2023-06-30", "2023-07-30"),
    ]
    peer_dates = [
        ("2025-12-31", "2026-02-05"),
        ("2024-12-31", "2025-02-05"),
        ("2023-12-31", "2024-02-05"),
    ]
    values = {
        **{("PRIMARY", fiscal_date): 0.2 for fiscal_date, _ in selected_dates},
        **{("PEER", fiscal_date): 0.1 for fiscal_date, _ in peer_dates},
    }

    comparison = historical_financial_profile_comparison(
        _result(),
        metric,
        requested_period=3,
        peer_ticker="peer",
        availability_provider=_availability_provider({
            "PRIMARY": _annual_records("PRIMARY", selected_dates),
            "PEER": _annual_records("PEER", peer_dates),
        }),
        metric_provider=_metric_provider(values, metric),
    )

    assert comparison.anchor_fiscal_years == (2023, 2024, 2025)
    assert [item.ticker for item in comparison.series] == [
        "PRIMARY", "PEER", "PRIMARY", "PEER", "PRIMARY", "PEER",
    ]
    assert comparison.max_fiscal_period_offset_days == 184
    assert comparison.warning_codes == ("fiscal_period_offset",)
    assert comparison.limiting_tickers == ()


def test_shorter_peer_limits_requested_period_and_marks_only_peer():
    metric = "debt_to_assets"
    selected_dates = [
        (f"{year}-06-30", f"{year}-07-30")
        for year in range(2025, 2020, -1)
    ]
    peer_dates = [
        (f"{year}-06-30", f"{year}-07-30")
        for year in range(2025, 2022, -1)
    ]
    values = {
        **{("PRIMARY", fiscal_date): 0.2 for fiscal_date, _ in selected_dates},
        **{("PEER", fiscal_date): 0.3 for fiscal_date, _ in peer_dates},
    }

    comparison = historical_financial_profile_comparison(
        _result(),
        metric,
        peer_ticker="PEER",
        availability_provider=_availability_provider({
            "PRIMARY": _annual_records("PRIMARY", selected_dates),
            "PEER": _annual_records("PEER", peer_dates),
        }),
        metric_provider=_metric_provider(values, metric),
    )

    assert comparison.applied_period == 3
    assert comparison.available_periods == (1, 3, "all")
    assert comparison.limiting_tickers == ("PEER",)
    assert comparison.warning_codes == ("limited_history",)


def test_missing_peer_history_keeps_selected_series_and_combines_warnings():
    metric = "financial_profile_return_on_capital"
    dates = [
        (f"{year}-06-30", f"{year}-07-30")
        for year in range(2025, 2020, -1)
    ]
    values = {("PRIMARY", fiscal_date): 0.2 for fiscal_date, _ in dates}

    comparison = historical_financial_profile_comparison(
        _result(),
        metric,
        peer_ticker="PEER",
        availability_provider=_availability_provider({
            "PRIMARY": _annual_records("PRIMARY", dates),
            "PEER": (),
        }),
        metric_provider=_metric_provider(values, metric),
    )

    assert comparison.applied_period == 5
    assert {item.ticker for item in comparison.series} == {"PRIMARY"}
    assert comparison.limiting_tickers == ("PEER",)
    assert comparison.warning_codes == (
        "limited_history",
        "no_comparable_history",
    )


def test_metric_gap_stops_history_without_substituting_another_statement():
    metric = "eps_cagr_5yr"
    dates = [
        ("2025-06-30", "2025-07-30"),
        ("2024-06-30", "2024-07-30"),
        ("2023-06-30", "2023-07-30"),
    ]
    values = {
        ("PRIMARY", "2025-06-30"): 0.12,
        ("PRIMARY", "2024-06-30"): {
            "annual_financial_statement_analysis_date": "2023-06-30",
            metric: 0.10,
        },
        ("PRIMARY", "2023-06-30"): 0.08,
    }

    comparison = historical_financial_profile_comparison(
        _result(),
        metric,
        availability_provider=_availability_provider({
            "PRIMARY": _annual_records("PRIMARY", dates),
        }),
        metric_provider=_metric_provider(values, metric),
    )

    assert comparison.applied_period == 1
    assert [item.annual_statement_date for item in comparison.series] == [
        "2025-06-30"
    ]
    assert comparison.warning_codes == ("limited_history",)


def test_historical_eoey_preserves_price_date_and_rejects_future_price():
    metric = "estimated_owner_earnings_yield"
    records = _annual_records("PRIMARY", [
        ("2025-06-30", "2025-07-30"),
        ("2024-06-30", "2024-07-30"),
    ])
    values = {
        ("PRIMARY", "2025-06-30"): {
            "annual_financial_statement_analysis_date": "2025-06-30",
            "price_date": "2025-07-29",
            metric: 0.08,
        },
        ("PRIMARY", "2024-06-30"): {
            "annual_financial_statement_analysis_date": "2024-06-30",
            "price_date": "2024-08-01",
            metric: 0.07,
        },
    }

    comparison = historical_financial_profile_comparison(
        _result(),
        metric,
        requested_period="all",
        availability_provider=_availability_provider({"PRIMARY": records}),
        metric_provider=_metric_provider(values, metric),
    )

    assert comparison.applied_period == 1
    assert comparison.series[0].price_date == "2025-07-29"
    assert comparison.series[0].price_date <= (
        comparison.series[0].statement_availability_date
    )

