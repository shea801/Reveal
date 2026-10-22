from datetime import date

import pandas as pd
import pytest

from mvp.models import SecurityAnalysisResult
from mvp.service import (
    DESCRIPTIVE_METRIC_FIELDS,
    FINANCIAL_PROFILE_FIELDS,
    financial_profile_distributions,
)


def _result(**overrides) -> SecurityAnalysisResult:
    values = {
        "ticker": "ACME",
        "company_name": "Acme Industries",
        "analysis_date": date(2025, 12, 31),
        "market_cap": 3_000_000_000,
        "market_cap_group": "Mid",
        "sector": "Industrials",
        "industry": "Tools",
    }
    values.update({metric: 0.30 for metric in FINANCIAL_PROFILE_FIELDS})
    values.update(overrides)
    return SecurityAnalysisResult(**values)


def _row(
    ticker: str,
    *,
    industry: str = "TOOLS",
    sector: str = "INDUSTRIALS",
    market_cap: float = 3_000_000_000,
    asset_type: str = "Common Stock",
) -> dict:
    return {
        "Symbol": ticker,
        "Name": f"{ticker} Company",
        "AssetType": asset_type,
        "Exchange": "NYSE",
        "MarketCapitalization": market_cap,
        "Sector": sector,
        "Industry": industry,
    }


def _metric_provider(values: dict[str, float]):
    def provide(ticker: str, _analysis_date: str) -> dict:
        return {
            metric: values[ticker]
            for metric in FINANCIAL_PROFILE_FIELDS
        }

    return provide


def test_distributions_use_narrowest_peer_group_with_five_values():
    universe = pd.DataFrame(
        [_row("ACME"), *[_row(f"P{index}") for index in range(1, 5)]]
    )
    peer_values = {
        "P1": 0.10,
        "P2": 0.20,
        "P3": 0.40,
        "P4": 0.50,
    }

    distributions = financial_profile_distributions(
        _result(),
        universe_provider=lambda: universe,
        metric_provider=_metric_provider(peer_values),
    )

    assert len(distributions) == 7
    distribution = distributions[0]
    assert distribution.comparison_basis == "Industry + market cap"
    assert distribution.comparison_group == "Tools / Mid"
    assert distribution.sample_size == 5
    assert distribution.values == (0.10, 0.20, 0.30, 0.40, 0.50)
    assert distribution.median == pytest.approx(0.30)
    assert distribution.mean == pytest.approx(0.30)
    assert distribution.percentile == pytest.approx(50.0)


def test_distributions_fall_back_to_industry_when_cap_group_is_small():
    universe = pd.DataFrame(
        [
            _row("ACME"),
            _row("P1"),
            _row("P2"),
            _row("P3", market_cap=20_000_000_000),
            _row("P4", market_cap=20_000_000_000),
        ]
    )
    peer_values = {
        "P1": 0.10,
        "P2": 0.20,
        "P3": 0.40,
        "P4": 0.50,
    }

    distributions = financial_profile_distributions(
        _result(),
        universe_provider=lambda: universe,
        metric_provider=_metric_provider(peer_values),
    )

    assert distributions[0].comparison_basis == "Industry"
    assert distributions[0].comparison_group == "Tools"


def test_distributions_ignore_ineligible_and_nonfinite_observations():
    universe = pd.DataFrame(
        [
            _row("ACME"),
            _row("P1"),
            _row("P2"),
            _row("P3"),
            _row("P4"),
            _row("WARRANT", asset_type="Warrant"),
        ]
    )
    peer_values = {
        "P1": 0.10,
        "P2": 0.20,
        "P3": 0.40,
        "P4": float("nan"),
    }

    distributions = financial_profile_distributions(
        _result(),
        universe_provider=lambda: universe,
        metric_provider=_metric_provider(peer_values),
    )

    assert distributions == ()


def test_distributions_preserve_unavailable_selected_value():
    universe = pd.DataFrame(
        [_row("ACME"), *[_row(f"P{index}") for index in range(1, 6)]]
    )
    peer_values = {f"P{index}": index / 10 for index in range(1, 6)}
    result = _result(return_on_invested_capital=None)

    distributions = financial_profile_distributions(
        result,
        universe_provider=lambda: universe,
        metric_provider=_metric_provider(peer_values),
    )

    roic = distributions[0]
    assert roic.metric == "return_on_invested_capital"
    assert roic.selected_value is None
    assert roic.percentile is None
    assert roic.sample_size == 5


def test_requested_overview_metrics_share_peer_cohort_and_preserve_nulls():
    universe = pd.DataFrame(
        [_row("ACME"), *[_row(f"P{index}") for index in range(1, 6)]]
    )
    selected = _result(gross_margin=0.45, free_cash_flow=None)

    def provide(ticker, _analysis_date):
        return {
            **{field: 0.30 for field in FINANCIAL_PROFILE_FIELDS},
            "gross_margin": 0.10 * int(ticker[1:]),
            "free_cash_flow": 1_000_000 * int(ticker[1:]),
        }

    distributions = financial_profile_distributions(
        selected,
        universe_provider=lambda: universe,
        metric_provider=provide,
        metric_fields=DESCRIPTIVE_METRIC_FIELDS,
    )
    by_metric = {item.metric: item for item in distributions}

    assert len(DESCRIPTIVE_METRIC_FIELDS) == 17
    assert by_metric["gross_margin"].sample_size == 6
    assert by_metric["gross_margin"].selected_value == 0.45
    assert by_metric["free_cash_flow"].selected_value is None
    assert by_metric["free_cash_flow"].percentile is None
