from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from mvp import HistoricalMetricComparison, HistoricalMetricObservation


def test_historical_metric_comparison_exposes_anchor_aligned_contract_fields():
    selected_observation = HistoricalMetricObservation(
        ticker="PRIMARY",
        anchor_fiscal_year=2026,
        fiscal_year=2026,
        annual_statement_date="2026-06-30",
        statement_availability_date="2026-07-30",
        price_date=None,
        value=0.18,
    )
    peer_observation = HistoricalMetricObservation(
        ticker="PEER",
        anchor_fiscal_year=2026,
        fiscal_year=2025,
        annual_statement_date="2025-12-31",
        statement_availability_date="2026-02-05",
        price_date=None,
        value=0.16,
    )
    comparison = HistoricalMetricComparison(
        metric="return_on_invested_capital",
        analysis_date=date(2026, 10, 2),
        requested_period=5,
        applied_period=1,
        available_periods=(1, "all"),
        selected_ticker="PRIMARY",
        peer_ticker="PEER",
        anchor_fiscal_years=(2026,),
        series=(selected_observation, peer_observation),
        limiting_tickers=("PEER",),
        max_fiscal_period_offset_days=181,
        warning_codes=("limited_history",),
    )

    assert comparison.series == (selected_observation, peer_observation)
    assert comparison.available_periods == (1, "all")
    assert comparison.anchor_fiscal_years == (2026,)
    assert peer_observation.anchor_fiscal_year != peer_observation.fiscal_year

    with pytest.raises(FrozenInstanceError):
        comparison.metric = "free_cash_flow_margin"
