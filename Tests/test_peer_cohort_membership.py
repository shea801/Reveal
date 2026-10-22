from datetime import date

import pandas as pd
import pytest

import mvp.service as service
from mvp.models import SecurityAnalysisResult
from mvp.service import (
    FINANCIAL_PROFILE_FIELDS,
    comparable_security_cohort,
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
    name: str | None = None,
    industry: str = "TOOLS",
    sector: str = "INDUSTRIALS",
    market_cap: float = 3_000_000_000,
    asset_type: str = "Common Stock",
    exchange: str = "NYSE",
) -> dict:
    return {
        "Symbol": ticker,
        "Name": name or f"{ticker} Company",
        "AssetType": asset_type,
        "Exchange": exchange,
        "MarketCapitalization": market_cap,
        "Sector": sector,
        "Industry": industry,
    }


def test_comparable_cohort_returns_presentation_ready_metadata_without_analysis(
    monkeypatch,
):
    universe = pd.DataFrame(
        [
            _row("ACME", name="Acme Industries"),
            *[_row(f"P{index}") for index in range(1, 5)],
        ]
    )

    def forbidden_analysis(*_args, **_kwargs):
        pytest.fail("FinancialAssessment must not run for cohort membership")

    monkeypatch.setattr(service, "FA", forbidden_analysis)

    cohort = comparable_security_cohort(
        _result(),
        universe_provider=lambda: universe,
    )

    assert cohort.selected_ticker == "ACME"
    assert cohort.comparison_basis == "Industry + market cap"
    assert cohort.comparison_group == "Tools / Mid"
    assert [member.ticker for member in cohort.members] == [
        "ACME",
        "P1",
        "P2",
        "P3",
        "P4",
    ]
    assert cohort.members[1].company_name == "P1 Company"
    assert cohort.members[1].industry == "Tools"
    assert cohort.members[1].sector == "Industrials"
    assert cohort.members[1].market_cap_group == "Mid"


def test_comparable_cohort_default_falls_back_to_five_member_tier():
    universe = pd.DataFrame(
        [
            _row("ACME"),
            _row("P1"),
            _row("P2"),
            _row("P3", market_cap=20_000_000_000),
            _row("P4", market_cap=20_000_000_000),
        ]
    )

    cohort = comparable_security_cohort(
        _result(),
        universe_provider=lambda: universe,
    )

    assert cohort.comparison_basis == "Industry"
    assert len(cohort.members) == 5


def test_comparable_cohort_returns_requested_broader_membership():
    universe = pd.DataFrame(
        [
            _row("ACME"),
            _row("TOOLS"),
            _row("MACH", industry="MACHINERY", market_cap=20_000_000_000),
            _row("TECH", industry="SOFTWARE", sector="TECHNOLOGY"),
            _row("WARRANT", asset_type="Warrant"),
        ]
    )

    cohort = comparable_security_cohort(
        _result(),
        "sector",
        universe_provider=lambda: universe,
    )

    assert cohort.comparison_basis == "Sector"
    assert cohort.comparison_group == "Industrials"
    assert [member.ticker for member in cohort.members] == [
        "ACME",
        "MACH",
        "TOOLS",
    ]


def test_comparable_cohort_keeps_requested_name_when_membership_is_duplicated():
    universe = pd.DataFrame([_row("ACME"), _row("PEER")])

    cohort = comparable_security_cohort(
        _result(),
        "Industry",
        universe_provider=lambda: universe,
    )

    assert cohort.comparison_basis == "Industry"
    assert cohort.comparison_group == "Tools"
    assert [member.ticker for member in cohort.members] == ["ACME", "PEER"]


def test_comparable_cohort_matches_distribution_candidate_membership():
    universe = pd.DataFrame(
        [
            _row("ACME"),
            _row("P1"),
            _row("P2"),
            _row("P3", market_cap=20_000_000_000),
            _row("P4", market_cap=20_000_000_000),
        ]
    )
    metric_values = {
        "P1": 0.10,
        "P2": 0.20,
        "P3": 0.40,
        "P4": 0.50,
    }

    def metric_provider(ticker, _analysis_date):
        return {
            metric: metric_values[ticker]
            for metric in FINANCIAL_PROFILE_FIELDS
        }

    distribution = financial_profile_distributions(
        _result(),
        universe_provider=lambda: universe,
        metric_provider=metric_provider,
    )[0]
    cohort = comparable_security_cohort(
        _result(),
        distribution.comparison_basis,
        universe_provider=lambda: universe,
    )

    assert distribution.comparison_basis == "Industry"
    assert len(cohort.members) == distribution.candidate_count
    assert [member.ticker for member in cohort.members] == [
        "ACME",
        "P1",
        "P2",
        "P3",
        "P4",
    ]


def test_comparable_cohort_uses_result_metadata_when_selected_row_is_absent():
    universe = pd.DataFrame([_row("PEER")])

    cohort = comparable_security_cohort(
        _result(),
        universe_provider=lambda: universe,
    )

    selected = next(
        member for member in cohort.members if member.ticker == "ACME"
    )
    assert selected.company_name == "Acme Industries"
    assert selected.industry == "Tools"
    assert selected.sector == "Industrials"
    assert selected.market_cap_group == "Mid"


def test_comparable_cohort_rejects_unknown_comparison_basis():
    universe = pd.DataFrame([_row("ACME"), _row("PEER")])

    with pytest.raises(ValueError, match="available cohorts"):
        comparable_security_cohort(
            _result(),
            "Country",
            universe_provider=lambda: universe,
        )


def test_comparable_cohort_default_reads_only_peer_metadata(monkeypatch):
    universe = pd.DataFrame([_row("ACME"), _row("PEER")])
    calls = []

    class MetadataAccess:
        def get_peer_metadata(self):
            calls.append("get_peer_metadata")
            return universe

        def get_all(self):
            pytest.fail("The full company-details table should not be loaded")

    monkeypatch.setattr(service, "CompanyDetails", MetadataAccess)

    cohort = comparable_security_cohort(_result())

    assert calls == ["get_peer_metadata"]
    assert len(cohort.members) == 2
