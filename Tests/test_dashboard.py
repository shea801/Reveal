from datetime import date

from dashboard.app import (
    DESCRIPTIVE_METRICS,
    FINANCIAL_PROFILE_METRICS,
    _criterion_context,
    _distribution_figure,
    _format_value,
    _history_period_options,
    _history_warning,
    _metric_history_figure,
    _metric_distribution_spread,
    _peer_metric_table,
    _security_suggestion_options,
    analyze_ticker,
    build_analysis_view,
    create_app,
)
from mvp.models import (
    ComparableSecurity,
    ComparableSecurityCohort,
    FinancialMetricDistribution,
    HistoricalMetricComparison,
    HistoricalMetricObservation,
    SecurityAnalysisResult,
    SecurityEligibilityAssessment,
)


def _text_content(component) -> str:
    if component is None:
        return ""
    if isinstance(component, (str, int, float)):
        return str(component)
    if isinstance(component, (list, tuple)):
        return " ".join(_text_content(item) for item in component)
    return _text_content(getattr(component, "children", None))


def _find_component(component, component_id):
    if getattr(component, "id", None) == component_id:
        return component
    children = getattr(component, "children", None)
    if not isinstance(children, (list, tuple)):
        children = [children] if children is not None else []
    for child in children:
        found = _find_component(child, component_id)
        if found is not None:
            return found
    return None


def _find_components_by_type(component, component_type):
    matches = []
    component_id = getattr(component, "id", None)
    if (
        isinstance(component_id, dict)
        and component_id.get("type") == component_type
    ):
        matches.append(component)
    children = getattr(component, "children", None)
    if not isinstance(children, (list, tuple)):
        children = [children] if children is not None else []
    for child in children:
        matches.extend(_find_components_by_type(child, component_type))
    return matches


def _result(**overrides) -> SecurityAnalysisResult:
    values = {
        "ticker": "ACME",
        "company_name": "Acme Industries",
        "company_description": "Acme makes precision industrial tools.",
        "analysis_date": date(2025, 12, 31),
        "price_date": "2025-12-31",
        "annual_financial_statement_analysis_date": "2025-09-30",
        "quarter_financial_statement_analysis_date": "2025-09-30",
        "market_price_for_period": 42.5,
        "market_cap": 2_500_000_000,
        "market_cap_group": "Mid Cap",
        "sector": "Industrials",
        "industry": "Tools",
        "return_on_invested_capital": 0.148,
        "financial_profile_return_on_capital": 0.163,
        "free_cash_flow_margin": 0.091,
        "estimated_owner_earnings_yield": 0.072,
        "debt_to_assets": 0.224,
        "net_debt_to_free_cash_flow": 2.4,
        "eps_cagr_5yr": 0.082,
        "return_on_capital": 0.211,
        "earnings_yield": 0.097,
        "magic_formula_rank": 14,
        "return_on_capital_rank": 18,
        "earnings_yield_rank": 10,
        "total_roc_ey_score": 28,
        "defensive_revenue_requirement_met": True,
        "total_sales_services": 800_000_000,
        "data_complete": True,
    }
    values.update(overrides)
    return SecurityAnalysisResult(**values)


def _distribution(metric: str) -> FinancialMetricDistribution:
    return FinancialMetricDistribution(
        metric=metric,
        comparison_basis="Industry",
        comparison_group="Tools",
        sample_size=7,
        candidate_count=8,
        values=(0.04, 0.07, 0.09, 0.12, 0.15, 0.18, 0.22),
        selected_value=0.148,
        percentile=64.3,
        p10=0.058,
        p25=0.08,
        median=0.12,
        mean=0.124,
        p75=0.165,
        p90=0.196,
    )


def _cohort() -> ComparableSecurityCohort:
    return ComparableSecurityCohort(
        selected_ticker="ACME",
        comparison_basis="Industry",
        comparison_group="Tools",
        members=(
            ComparableSecurity(
                ticker="ACME",
                company_name="Acme Industries",
                industry="Tools",
                sector="Industrials",
                market_cap_group="Mid Cap",
            ),
            ComparableSecurity(
                ticker="BETA",
                company_name="Beta Manufacturing",
                industry="Tools",
                sector="Industrials",
                market_cap_group="Mid Cap",
            ),
        ),
    )


def _history(**overrides) -> HistoricalMetricComparison:
    values = {
        "metric": "return_on_invested_capital",
        "analysis_date": date(2025, 12, 31),
        "requested_period": 1,
        "applied_period": 1,
        "available_periods": (1, "all"),
        "selected_ticker": "ACME",
        "peer_ticker": "BETA",
        "anchor_fiscal_years": (2025,),
        "series": (
            HistoricalMetricObservation(
                ticker="ACME",
                anchor_fiscal_year=2025,
                fiscal_year=2025,
                annual_statement_date="2025-06-30",
                statement_availability_date="2025-07-30",
                price_date=None,
                value=0.148,
            ),
            HistoricalMetricObservation(
                ticker="BETA",
                anchor_fiscal_year=2025,
                fiscal_year=2024,
                annual_statement_date="2024-12-31",
                statement_availability_date="2025-02-05",
                price_date=None,
                value=0.092,
            ),
        ),
        "limiting_tickers": (),
        "max_fiscal_period_offset_days": 181,
        "warning_codes": (),
    }
    values.update(overrides)
    return HistoricalMetricComparison(**values)


def test_dashboard_layout_has_reveal_header_controls_and_result_target():
    app = create_app(analyzer=lambda _ticker, _date: _result())
    text = _text_content(app.layout)

    assert "Reveal" in text
    assert "An investment application of practical counsel" in text
    assert "Security" in text
    assert "Analysis date" in text
    assert "Analyze" in text
    assert "No security selected" in text
    security_input = _find_component(app.layout, "ticker-input")
    assert security_input.list == "security-suggestions"
    assert "company name" in security_input.placeholder
    assert _find_component(app.layout, "security-suggestions") is not None
    assert any(
        "analysis-results.children" in output for output in app.callback_map
    )
    assert any(
        "security-suggestions.children" in output
        for output in app.callback_map
    )


def test_financial_profile_renders_exactly_seven_frozen_metrics():
    assert [metric.field for metric in FINANCIAL_PROFILE_METRICS] == [
        "return_on_invested_capital",
        "financial_profile_return_on_capital",
        "free_cash_flow_margin",
        "estimated_owner_earnings_yield",
        "debt_to_assets",
        "net_debt_to_free_cash_flow",
        "eps_cagr_5yr",
    ]

    text = _text_content(build_analysis_view(_result()))
    assert "Return on Invested Capital (ROIC)" in text
    assert "Financial Profile Return on Capital (ROC)" in text
    assert "14.8%" in text
    assert "2.40x" in text
    assert "Acme makes precision industrial tools." in text
    assert "Magic Formula rank 14" in " ".join(text.split())


def test_eps_cagr_display_label_spans_four_growth_intervals():
    label = "EPS CAGR (4-Year Growth)"
    metric = FINANCIAL_PROFILE_METRICS[-1]

    assert metric.field == "eps_cagr_5yr"
    assert metric.label == label
    assert "five aligned EPS observations" in metric.calculation
    assert label in _text_content(build_analysis_view(_result()))
    assert (
        _distribution_figure("ACME", _distribution(metric.field), "scatter")
        .layout.xaxis.title.text == label
    )
    assert (
        _metric_history_figure(_history(metric=metric.field))
        .layout.yaxis.title.text == label
    )


def test_peer_comparison_target_remains_when_distribution_is_unavailable():
    view = build_analysis_view(_result())

    assert _find_component(view, "peer-distribution") is not None
    assert _find_component(view, "peer-metric-table") is not None


def test_descriptive_layout_adds_overview_metrics_and_keeps_history_next():
    view = build_analysis_view(
        _result(gross_margin=0.42, free_cash_flow=12_000_000),
        (_distribution("return_on_invested_capital"),),
    )
    profile = _find_component(view, "financial-profile")
    rows = [
        _find_component(profile, f"metric-{metric.field}")
        for metric in DESCRIPTIVE_METRICS
    ]

    assert len(DESCRIPTIVE_METRICS) == 17
    assert all(row is not None for row in rows)
    assert "Descriptive annual metrics" in _text_content(profile)
    assert "Calculation" not in _text_content(profile)
    assert _find_component(profile, "peer-distribution") is not None
    assert [getattr(child, "id", None) for child in view.children][-5:] == [
        "security-overview",
        "financial-profile",
        "metric-history",
        "graham-analysis",
        "data-quality",
    ]
    label, tooltip = rows[0].children[0].children
    assert tooltip.target == label.id
    assert tooltip.children == FINANCIAL_PROFILE_METRICS[0].calculation

    charts = _find_component(view, "metric-history").children[-1]
    assert charts.className == "comparison-charts-grid"
    assert _find_component(charts.children[0], "distribution-graph") is not None
    assert _find_component(charts.children[1], "metric-history-graph") is not None
    assert _find_component(profile, "distribution-graph") is None


def test_peer_comparison_includes_all_descriptive_metrics_and_nulls():
    selected = _result(gross_margin=0.42, free_cash_flow=12_000_000)
    peer = _result(
        ticker="BETA", gross_margin=0.35, free_cash_flow=None,
    )
    table = _peer_metric_table(selected, peer)

    assert all(
        _find_component(table, f"peer-metric-{metric.field}") is not None
        for metric in DESCRIPTIVE_METRICS
    )
    assert "42.0%" in _text_content(
        _find_component(table, "peer-metric-gross_margin")
    )
    assert "Unavailable" in _text_content(
        _find_component(table, "peer-metric-free_cash_flow")
    )


def test_dashboard_renders_distribution_table_controls_and_context():
    distributions = tuple(
        _distribution(metric.field) for metric in FINANCIAL_PROFILE_METRICS
    )

    view = build_analysis_view(_result(), distributions)
    text = _text_content(view)

    assert "Peer Distribution" in text
    assert "Current cross-sectional context" in text
    assert "Industry" in text
    assert "7 of 8 candidates" in text
    assert "90th percentile" in text
    assert "Relative position is context" in text
    chart_select = _find_component(view, "distribution-chart-select")
    assert [option["value"] for option in chart_select.options] == [
        "scatter",
        "histogram",
        "box",
    ]


def test_financial_profile_uses_distribution_spread_with_fixed_ticks():
    distribution = _distribution("return_on_invested_capital")
    metric = FINANCIAL_PROFILE_METRICS[0]

    spread = _metric_distribution_spread("ACME", metric, distribution)
    text = _text_content(spread)

    assert "0 10 25 Median 75 90 100" in " ".join(text.split())
    assert "ACME 14.8%" in text
    assert "64th percentile" in getattr(spread, "aria-label")
    marker = _find_component(
        spread, "spread-marker-return_on_invested_capital"
    )
    assert marker.style == {"left": "64.3%"}
    assert (
        _find_component(
            spread, "spread-tick-return_on_invested_capital-0"
        ).title
        == "0th percentile: 4.0%"
    )
    assert (
        _find_component(
            spread, "spread-tick-return_on_invested_capital-100"
        ).title
        == "100th percentile: 22.0%"
    )


def test_financial_profile_replaces_description_with_distribution_spread():
    view = build_analysis_view(
        _result(),
        (_distribution("return_on_invested_capital"),),
    )
    text = _text_content(view)
    row = _find_component(view, "metric-return_on_invested_capital")

    assert "Financial Metric Distribution Spread" in text
    assert "ACME 14.8%" in _text_content(row)
    assert FINANCIAL_PROFILE_METRICS[0].description not in _text_content(row)
    unavailable_row = _find_component(view, "metric-debt_to_assets")
    assert "Distribution unavailable" in _text_content(unavailable_row)


def test_distribution_supports_each_documented_chart_type():
    distribution = _distribution("return_on_invested_capital")

    for chart_type in ("scatter", "histogram", "box"):
        figure = _distribution_figure("ACME", distribution, chart_type)

        assert figure.data
        assert figure.layout.height == 285
        assert figure.layout.shapes


def test_security_analysis_renders_three_regions_and_clickable_cohort():
    view = build_analysis_view(
        _result(),
        (_distribution("return_on_invested_capital"),),
        cohort=_cohort(),
    )
    text = _text_content(view)
    peer_links = _find_components_by_type(view, "cohort-peer-link")

    assert "Security analysis" in text
    assert "Company and market context" in text
    assert "Comparison cohort" in text
    assert "Value lens" in text
    assert "Beta Manufacturing" in text
    assert "Industry" in text
    assert len(peer_links) == 1
    assert peer_links[0].id["ticker"] == "BETA"
    assert peer_links[0].href == "#peer-distribution"
    company_context = _find_component(view, "company-market-context")
    assert "Sector" not in _text_content(company_context)
    assert "Industry" not in _text_content(company_context)
    assert "Acme makes precision industrial tools." not in _text_content(
        company_context
    )
    assert _find_component(view, "security-description").children == (
        "Acme makes precision industrial tools."
    )
    tags = _find_component(view, "security-classification")
    assert len(tags.children) == 3
    identity = _find_component(view, "security-overview").children[0]
    assert tags in identity.children[0].children
    assert identity.children[1].id == "security-description"


def test_criteria_result_hover_and_magic_formula_share_one_section():
    view = build_analysis_view(_result())
    criteria = _find_component(view, "graham-analysis")
    grid = criteria.children[1]
    result_target = _find_component(
        criteria,
        "criterion-result-continuous_dividend_payments_for_past_20yrs_met",
    )

    assert len(grid.children) == 3
    assert grid.children[2].id == "magic-formula"
    assert "Two ROC views" in _text_content(criteria.children[-1])
    assert result_target is not None
    table = grid.children[0].children[1]
    assert len(table.children[0].children.children) == 3


def test_selected_peer_is_added_to_distribution_and_contract_history_figures():
    distribution = _distribution("return_on_invested_capital")
    peer = _result(
        ticker="BETA",
        company_name="Beta Manufacturing",
        return_on_invested_capital=0.092,
    )

    distribution_figure = _distribution_figure(
        "ACME",
        distribution,
        "scatter",
        peer,
    )
    history_figure = _metric_history_figure(_history())

    assert len(distribution_figure.layout.shapes) == 2
    assert [trace.name for trace in history_figure.data] == ["ACME", "BETA"]
    assert history_figure.layout.barmode == "group"
    assert history_figure.data[0].x == ("2025",)
    assert history_figure.data[1].customdata[0][:2] == [
        "2024-12-31",
        "2025-02-05",
    ]


def test_historical_eoey_discloses_frozen_price_date_in_hover_data():
    observations = tuple(
        HistoricalMetricObservation(
            ticker=item.ticker,
            anchor_fiscal_year=item.anchor_fiscal_year,
            fiscal_year=item.fiscal_year,
            annual_statement_date=item.annual_statement_date,
            statement_availability_date=item.statement_availability_date,
            price_date="2025-07-29" if item.ticker == "ACME" else "2025-02-04",
            value=item.value,
        )
        for item in _history().series
    )
    comparison = _history(
        metric="estimated_owner_earnings_yield",
        series=observations,
    )

    figure = _metric_history_figure(comparison)

    assert figure.data[0].customdata[0][2] == "2025-07-29"
    assert "Price date %{customdata[2]}" in figure.data[0].hovertemplate


def test_history_periods_warnings_and_asterisks_follow_contract():
    comparison = _history(
        requested_period=5,
        applied_period=1,
        limiting_tickers=("BETA",),
        max_fiscal_period_offset_days=184,
        warning_codes=("limited_history", "fiscal_period_offset"),
    )

    options = _history_period_options(comparison.available_periods)
    figure = _metric_history_figure(comparison)
    warning = _history_warning(comparison)

    enabled = [option["value"] for option in options if not option["disabled"]]
    assert enabled == ["1", "all"]
    assert [trace.name for trace in figure.data] == ["ACME", "BETA*"]
    assert "BETA limits this comparison" in _text_content(warning)
    assert "184 days" in _text_content(warning)


def test_dashboard_preserves_unavailable_and_failed_as_distinct_states():
    text = _text_content(
        build_analysis_view(
            _result(
                debt_to_assets=None,
                defensive_criteria_met=False,
                current_assets_200pct_or_greater_current_liabilities_met=False,
                no_earnings_deficit_for_5yrs_met=None,
                data_complete=False,
                calculation_warnings=("Insufficient history",),
            )
        )
    )

    assert "Unavailable" in text
    assert "Failed" in text
    assert "Partial result" in text
    assert "Insufficient history" in text


def test_dashboard_explains_dividend_failure_and_unavailable_history():
    result = _result()

    failed = _criterion_context(
        result,
        "continuous_dividend_payments_for_past_20yrs_met",
        "failed",
    )
    unavailable = _criterion_context(
        result,
        "continuous_dividend_payments_for_past_20yrs_met",
        "unavailable",
    )

    assert "without a common-stock dividend" in failed
    assert "not available" in unavailable


def test_dashboard_distinguishes_not_applicable_from_unavailable():
    reason = (
        "Utilities use the debt-to-book-equity test instead of the "
        "Industrial/Financial working-capital tests."
    )
    text = _text_content(
        build_analysis_view(
            _result(
                sector="Utilities",
                current_assets_200pct_or_greater_current_liabilities_met=None,
                not_applicable_fields=(
                    "current_assets_200pct_or_greater_current_liabilities_met",
                    "current_assets_to_current_liabilities_ratio",
                    "magic_formula_rank",
                ),
                field_explanations=(
                    (
                        "current_assets_200pct_or_greater_current_liabilities_met",
                        reason,
                    ),
                    (
                        "current_assets_to_current_liabilities_ratio",
                        reason,
                    ),
                    (
                        "magic_formula_rank",
                        "Magic Formula ranking excludes Utilities.",
                    ),
                ),
            )
        )
    )

    assert "Not applicable" in text
    assert reason in text
    assert "Magic Formula ranking excludes Utilities." in text


def test_analyze_ticker_normalizes_input_and_uses_injected_service():
    calls = []

    def analyzer(ticker, analysis_date):
        calls.append((ticker, analysis_date))
        return _result(ticker=ticker)

    rendered = analyze_ticker(" acme ", "2025-12-31", analyzer)

    assert calls == [("ACME", "2025-12-31")]
    assert "Acme Industries" in _text_content(rendered)


def test_analyze_ticker_resolves_company_name_before_analysis():
    calls = []

    def analyzer(ticker, analysis_date):
        calls.append((ticker, analysis_date))
        return _result(ticker=ticker, company_name="Microsoft Corp")

    rendered = analyze_ticker(
        "Microsoft Corp",
        "2025-12-31",
        analyzer,
        identifier_resolver=lambda identifier: (
            "MSFT" if identifier == "Microsoft Corp" else ""
        ),
    )

    assert calls == [("MSFT", "2025-12-31")]
    assert "Microsoft Corp" in _text_content(rendered)


def test_analyze_ticker_does_not_guess_an_ambiguous_identifier():
    analysis_calls = []

    def resolver(_identifier):
        raise ValueError(
            "That SEC CIK maps to multiple securities. Choose a ticker."
        )

    rendered = analyze_ticker(
        "0001067983",
        None,
        lambda *_args: analysis_calls.append("called"),
        identifier_resolver=resolver,
    )

    assert analysis_calls == []
    assert "maps to multiple securities" in _text_content(rendered)


def test_security_suggestions_include_ticker_company_and_cik():
    calls = []

    def search_provider(query, limit):
        calls.append((query, limit))
        return (
            {
                "ticker": "MSFT",
                "company_name": "MICROSOFT CORP",
                "cik": "0000789019",
            },
        )

    options = _security_suggestion_options("micro", search_provider)

    assert calls == [("micro", 8)]
    assert options[0].value == "MSFT"
    assert options[0].label == "MICROSOFT CORP | CIK 0000789019"


def test_analyze_ticker_uses_injected_distribution_service():
    calls = []

    def distribution_provider(result):
        calls.append(result.ticker)
        return (_distribution("return_on_invested_capital"),)

    rendered = analyze_ticker(
        "acme",
        None,
        lambda ticker, _date: _result(ticker=ticker),
        distribution_provider=distribution_provider,
    )

    assert calls == ["ACME"]
    assert "Peer Distribution" in _text_content(rendered)
    assert "7 of 8 candidates" in _text_content(rendered)


def test_analyze_ticker_uses_metadata_cohort_for_distribution_basis():
    calls = []

    def cohort_provider(result, comparison_basis):
        calls.append((result.ticker, comparison_basis))
        return _cohort()

    rendered = analyze_ticker(
        "acme",
        None,
        lambda ticker, _date: _result(ticker=ticker),
        distribution_provider=lambda _result: (
            _distribution("return_on_invested_capital"),
        ),
        cohort_provider=cohort_provider,
    )

    assert calls == [("ACME", "Industry")]
    assert "Beta Manufacturing" in _text_content(rendered)


def test_analyze_ticker_stops_before_analysis_when_security_is_ineligible():
    analysis_calls = []

    def analyzer(ticker, analysis_date):
        analysis_calls.append((ticker, analysis_date))
        return _result(ticker=ticker)

    def eligibility_checker(ticker):
        return SecurityEligibilityAssessment(
            ticker=ticker,
            eligible=False,
            company_name="Acme Warrants",
            asset_type="Warrant",
            exchange="NASDAQ",
            market_cap=500_000_000,
            reasons=(
                "ACME is classified as Warrant, not eligible common stock.",
            ),
        )

    rendered = analyze_ticker(
        "acme",
        None,
        analyzer,
        eligibility_checker,
    )
    text = _text_content(rendered)

    assert analysis_calls == []
    assert "Ineligible" in text
    assert "Acme Warrants" in text
    assert "not eligible common stock" in text
    assert "Learn about this security type" in text


def test_analyze_ticker_renders_input_and_service_errors_without_live_data():
    blank = analyze_ticker("", None, lambda _ticker, _date: _result())

    def unavailable(_ticker, _date):
        raise ValueError("Ticker is not eligible")

    failed = analyze_ticker("ETF", None, unavailable)

    assert "Enter a ticker, company name, or SEC CIK" in _text_content(blank)
    assert "Analysis unavailable" in _text_content(failed)
    assert "Ticker is not eligible" in _text_content(failed)


def test_value_formatting_keeps_none_explicit():
    assert _format_value(None, "percent") == "Unavailable"
    assert _format_value(0.125, "percent") == "12.5%"
    assert _format_value(1.75, "multiple") == "1.75x"
