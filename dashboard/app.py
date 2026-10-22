"""Single-page Dash application for Reveal security analysis."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
from importlib.metadata import PackageNotFoundError, version
import logging
from typing import Callable

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from mvp import service
from mvp.models import (
    ComparableSecurityCohort,
    FinancialMetricDistribution,
    HistoricalMetricComparison,
    HistoricalMetricObservation,
    MagicFormulaRankedSecurity,
    SecurityAnalysisResult,
    SecurityEligibilityAssessment,
)


LOGGER = logging.getLogger(__name__)


def _application_version() -> str:
    try:
        return version("investment-analysis-platform")
    except PackageNotFoundError:
        return "0.6.3"


@dataclass(frozen=True)
class MetricDefinition:
    field: str
    label: str
    description: str
    calculation: str
    caveat: str
    direction: str
    value_format: str = "percent"


FINANCIAL_PROFILE_METRICS = (
    MetricDefinition(
        "return_on_invested_capital",
        "Return on Invested Capital (ROIC)",
        "Measures how a company uses it's debt (ex: Corporate Bonds sold to get cash) to invest in capital items (i.e. buildings, equipment, etc.) and determines how well it was turned into operating profit.",
        "Annual NOPAT / average invested capital",
        "Capital intensity and acquisition history can make peer context essential.",
        "higher",
    ),
    MetricDefinition(
        "financial_profile_return_on_capital",
        "Financial Profile Return on Capital (ROC)",
        "Operating profit produced by the capital employed in the business before taxes and interest.",
        "Annual EBIT / average capital employed",
        "This annual descriptive measure is not the Magic Formula ROC.",
        "higher",
    ),
    MetricDefinition(
        "free_cash_flow_margin",
        "Free Cash Flow Margin (FCFM)",
        "The ratio of free cash flow (the cash from revenue left over after all expenses are paid) compared to the total revenue a company generated.",
        "Annual free cash flow / annual revenue",
        "Working-capital swings and uneven capital spending can move one year sharply.",
        "higher",
    ),
    MetricDefinition(
        "estimated_owner_earnings_yield",
        "Estimated Owner Earnings Yield (EOEY)",
        "'Owner Earnings' is the amount of cash remaining after all expenses are paid. Owners Earnings Yield is the ratio of owners earnings to the total purchase price of a company.",
        "OCF less capex / point-in-time market capitalization",
        "This is an operating-cash-flow-less-capital-expenditures estimate, not a complete owner-earnings reconstruction.",
        "higher",
    ),
    MetricDefinition(
        "debt_to_assets",
        "Debt to Assets",
        "Debt to Assets measures a companies ability to pay off it's current debt should they come under financial distress.",
        "Annual interest-bearing debt / total assets",
        "Normal leverage differs materially across industries and business models.",
        "lower",
    ),
    MetricDefinition(
        "net_debt_to_free_cash_flow",
        "Net Debt to Free Cash Flow",
        "Short and long term debt, minus the cash and equivalents held by a company, compared to their free cash flow; measures how well a company can repay it's debts.",
        "Net debt / positive annual free cash flow",
        "Unavailable when free cash flow is zero or negative; negative values can indicate net cash.",
        "lower",
        "multiple",
    ),
    MetricDefinition(
        "eps_cagr_5yr",
        "EPS CAGR (4-Year Growth)",
        "Annualized EPS growth over four intervals using five aligned annual observations.",
        "Growth over four annual intervals from five aligned EPS observations",
        "Positive endpoints are required, and one-time earnings can distort the result.",
        "higher",
    ),
)

ADDITIONAL_OVERVIEW_METRICS = (
    MetricDefinition(
        "gross_margin", "Gross Margin", "Revenue remaining after direct costs.",
        "(Annual revenue - annual cost of goods and services sold) / annual revenue",
        "Product mix and accounting classifications affect comparisons.", "higher",
    ),
    MetricDefinition(
        "free_cash_flow", "Free Cash Flow", "Cash flow after capital spending.",
        "Annual operating cash flow - annual capital expenditures",
        "Cash flow and capital spending can vary substantially by year.", "higher", "currency_compact",
    ),
    MetricDefinition(
        "estimated_owner_earnings", "Estimated Owner Earnings",
        "Operating-cash-flow-less-capex owner-earnings proxy.",
        "Annual operating cash flow - annual capital expenditures",
        "This proxy is not a full owner-earnings reconstruction.", "higher", "currency_compact",
    ),
    MetricDefinition(
        "operating_income", "Operating Income",
        "Revenue remaining after direct and operating expenses.",
        "Annual revenue - cost of goods and services sold - operating expenses",
        "Expense classification differs across companies.", "higher", "currency_compact",
    ),
    MetricDefinition(
        "inventory_turnover", "Inventory Turnover",
        "Revenue relative to reported inventory.",
        "Annual revenue / selected annual inventory balance",
        "This implementation uses revenue rather than cost of goods sold.", "higher", "multiple",
    ),
    MetricDefinition(
        "return_on_assets", "Return on Assets", "Net income relative to assets.",
        "Annual net income / annual total assets",
        "Asset intensity varies by industry.", "higher",
    ),
    MetricDefinition(
        "return_on_equity", "Return on Equity", "Net income relative to equity.",
        "Annual net income / annual shareholder equity; assets less liabilities if equity is absent",
        "Leverage can amplify this ratio.", "higher",
    ),
    MetricDefinition(
        "debt_to_equity", "Liabilities to Equity",
        "Total liabilities relative to equity.",
        "Annual total liabilities / (annual total assets - annual total liabilities)",
        "The source field is named debt_to_equity but includes all liabilities.", "lower", "multiple",
    ),
    MetricDefinition(
        "longterm_debt_to_cash", "Long-term Debt / Cash-flow-adjusted Cash",
        "Long-term debt relative to cash plus annual free cash flow.",
        "Annual long-term debt / (cash and equivalents + annual operating cash flow - annual capital expenditures)",
        "The denominator includes cash flow as well as the cash balance.", "lower", "multiple",
    ),
    MetricDefinition(
        "interest_coverage", "Interest Coverage",
        "Operating earnings relative to interest expense.",
        "Annual EBIT / annual interest expense",
        "Unavailable when interest expense is zero or missing.", "higher", "multiple",
    ),
)
DESCRIPTIVE_METRICS = FINANCIAL_PROFILE_METRICS + ADDITIONAL_OVERVIEW_METRICS
METRIC_DEFINITIONS = {metric.field: metric for metric in DESCRIPTIVE_METRICS}


DEFENSIVE_CRITERIA = (
    (
        "defensive_revenue_requirement_met",
        "Annual revenue meets the sector minimum",
        "total_sales_services",
        "currency_compact",
    ),
    (
        "current_assets_200pct_or_greater_current_liabilities_met",
        "Current assets at least 2x current liabilities",
        "current_assets_to_current_liabilities_ratio",
        "multiple",
    ),
    (
        "utility_debt_to_book_equity_met",
        "Utility long-term debt no more than 2x book equity",
        "long_term_debt_to_book_equity_ratio",
        "multiple",
    ),
    (
        "long_term_debt_less_than_net_current_assets_met",
        "Long-term debt below net current assets",
        "long_term_debt_to_net_current_assets_ratio",
        "multiple",
    ),
    (
        "positive_earnings_for_the_past_10_years_met",
        "Positive earnings in each of the past 10 years",
        None,
        "number",
    ),
    (
        "eps_3yr_average_33pct_gte_10yr_previous_eps_met",
        "Three-year average EPS grew at least one-third",
        "eps_3yr_average_to_10yr_previous_eps_ratio",
        "multiple",
    ),
    (
        "continuous_dividend_payments_for_past_20yrs_met",
        "Continuous dividend payments for 20 years",
        "average_dividend_payments_for_past_20yrs",
        "currency",
    ),
    (
        "price_15x_or_less_eps_3yr_average_met",
        "Price no more than 15x three-year average EPS",
        "price_to_eps_3yr_average",
        "multiple",
    ),
    (
        "price_150pct_or_less_book_value_met",
        "Price no more than 1.5x book value",
        "price_to_book_value",
        "multiple",
    ),
)


SECURITY_TYPE_LINKS = {
    "COMMON STOCK": "https://www.investopedia.com/terms/c/commonstock.asp",
    "PREFERRED STOCK": "https://www.investopedia.com/terms/p/preferredstock.asp",
    "WARRANT": "https://www.investopedia.com/terms/w/warrant.asp",
}


ENTERPRISING_CRITERIA = (
    (
        "current_assets_150pct_or_greater_long_term_debt_met",
        "Current assets at least 1.5x long-term debt",
        "current_assets_150pct_or_greater_than_long_term_debt_ratio",
        "multiple",
    ),
    (
        "long_term_debt_110pct_or_less_to_net_current_assets_met",
        "Long-term debt no more than 110% of net current assets",
        "long_term_debt_to_net_current_assets_ratio",
        "multiple",
    ),
    (
        "no_earnings_deficit_for_5yrs_met",
        "No earnings deficit in the past five years",
        None,
        "number",
    ),
    (
        "earnings_growth_greater_than_5yrs_previous_met",
        "Current earnings exceed five-year lookback earnings",
        "earnings_to_5yr_earnings_lookback_ratio",
        "multiple",
    ),
    (
        "price_120pct_or_less_tangible_book_met",
        "Price no more than 1.2x tangible book value",
        "price_to_tangible_book_value",
        "multiple",
    ),
)


def _format_value(value, value_format: str = "number") -> str:
    if value is None:
        return "Unavailable"
    if value_format == "percent":
        return f"{value:.1%}"
    if value_format == "currency":
        return f"${value:,.2f}"
    if value_format == "currency_compact":
        absolute_value = abs(value)
        for threshold, suffix in (
            (1_000_000_000_000, "T"),
            (1_000_000_000, "B"),
            (1_000_000, "M"),
        ):
            if absolute_value >= threshold:
                return f"${value / threshold:,.2f}{suffix}"
        return f"${value:,.0f}"
    if value_format == "multiple":
        return f"{value:,.2f}x"
    if value_format == "integer":
        return f"{int(value):,}"
    if value_format == "date":
        return str(value)
    return f"{value:,.2f}" if isinstance(value, float) else str(value)


def _section_heading(title: str, eyebrow: str) -> html.Div:
    return html.Div(
        [html.P(eyebrow, className="section-eyebrow"), html.H2(title)],
        className="section-heading",
    )


def _field_explanations(result: SecurityAnalysisResult) -> dict[str, str]:
    return dict(result.field_explanations)


def _field_state(result: SecurityAnalysisResult, field: str) -> str:
    if field in result.not_applicable_fields:
        return "not_applicable"
    value = getattr(result, field)
    if value is True:
        return "passed"
    if value is False:
        return "failed"
    return "unavailable"


def _status_badge(state: str) -> dbc.Badge:
    if state == "passed":
        return dbc.Badge("Passed", color="success", className="status-badge")
    if state == "failed":
        return dbc.Badge("Failed", color="danger", className="status-badge")
    if state == "not_applicable":
        return dbc.Badge(
            "Not applicable", color="info", className="status-badge"
        )
    return dbc.Badge(
        "Unavailable", color="secondary", className="status-badge"
    )


def _summary_badge(value: bool | None) -> dbc.Badge:
    if value is True:
        return dbc.Badge("All evaluated criteria passed", color="success")
    if value is False:
        return dbc.Badge("One or more criteria failed", color="danger")
    return dbc.Badge("Assessment incomplete", color="secondary")


def _criterion_context(
    result: SecurityAnalysisResult,
    status_field: str,
    state: str,
) -> str:
    explanation = _field_explanations(result).get(status_field)
    if explanation:
        return explanation
    if status_field == "continuous_dividend_payments_for_past_20yrs_met":
        if state == "passed":
            return (
                "Adjusted market history shows a common-stock dividend in "
                "every covered fiscal year of the 20-year window."
            )
        if state == "failed":
            return (
                "Adjusted market history contains at least one fiscal year "
                "without a common-stock dividend in the 20-year window."
            )
        return (
            "Twenty complete fiscal years of adjusted dividend-event history "
            "are not available."
        )
    if state == "unavailable":
        return (
            "This criterion applies, but the required source data was not "
            "available for the selected period."
        )
    return "Evaluated from the selected period's available source data."


def _cohort_member_list(
    cohort: ComparableSecurityCohort | None,
    error: str | None,
) -> html.Div:
    if cohort is None:
        message = (
            "Cohort membership is unavailable for this analysis."
            if error
            else "No comparison cohort is available."
        )
        return html.Div(message, className="cohort-unavailable")

    members = []
    for member in cohort.members:
        content = [
            html.Strong(member.ticker),
            html.Span(member.company_name or "Company name unavailable"),
        ]
        if member.ticker == cohort.selected_ticker:
            members.append(
                html.Div(
                    [*content, html.Small("Selected security")],
                    className="cohort-member cohort-member-selected",
                )
            )
        else:
            members.append(
                html.A(
                    content,
                    id={
                        "type": "cohort-peer-link",
                        "ticker": member.ticker,
                    },
                    href="#peer-distribution",
                    n_clicks=0,
                    className="cohort-member cohort-member-link",
                )
            )

    return html.Div(
        [
            html.Div(
                [
                    html.Strong(
                        cohort.comparison_basis,
                        title=cohort.comparison_basis,
                    ),
                    html.Span(
                        cohort.comparison_group,
                        title=cohort.comparison_group,
                    ),
                    html.Small(f"{len(cohort.members)} securities"),
                ],
                className="cohort-summary",
            ),
            html.Div(members, className="cohort-list"),
        ]
    )


def _value_lens(result: SecurityAnalysisResult) -> html.Div:
    magic_formula_value = (
        "Not applicable"
        if "magic_formula_rank" in result.not_applicable_fields
        else (
            f"Rank {result.magic_formula_rank:,}"
            if result.magic_formula_rank is not None
            else "Unavailable"
        )
    )
    rows = (
        ("Defensive criteria", _summary_badge(result.defensive_criteria_met)),
        (
            "Enterprising criteria",
            _summary_badge(result.enterprising_criteria_met),
        ),
        ("Magic Formula", html.Strong(magic_formula_value)),
        (
            "Graham Number",
            html.Strong(_format_value(result.graham_number, "currency")),
        ),
        (
            "Defensive margin of safety",
            html.Strong(
                _format_value(result.defensive_margin_of_safety, "multiple")
            ),
        ),
        (
            "Serenity Number",
            html.Strong(_format_value(result.serenity_number, "currency")),
        ),
        (
            "Enterprising margin of safety",
            html.Strong(
                _format_value(
                    result.enterprising_margin_of_safety,
                    "multiple",
                )
            ),
        ),
    )
    return html.Div(
        [
            html.Div([html.Span(label), value], className="value-lens-row")
            for label, value in rows
        ],
        className="value-lens-list",
    )


def _overview_section(
    result: SecurityAnalysisResult,
    cohort: ComparableSecurityCohort | None = None,
    cohort_error: str | None = None,
) -> html.Section:
    market_items = (
        ("Analysis date", result.analysis_date, "date"),
        ("Price date", result.price_date, "date"),
        (
            "Annual statement",
            result.annual_financial_statement_analysis_date,
            "date",
        ),
        (
            "Quarterly statement",
            result.quarter_financial_statement_analysis_date,
            "date",
        ),
        ("Current price", result.market_price_for_period, "currency"),
        ("Market capitalization", result.market_cap, "currency_compact"),
        ("Market-cap group", result.market_cap_group, "number"),
        ("Price / earnings", result.price_to_earnings, "multiple"),
        ("Annual revenue", result.total_sales_services, "currency_compact"),
        ("200-day low", result.min_200_day_price, "currency"),
        ("200-day high", result.max_200_day_price, "currency"),
        ("200-day average", result.avg_price_200_day, "currency"),
        ("200-day median", result.median_price_200_day, "currency"),
    )
    return html.Section(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.P(
                                "Security analysis",
                                className="section-eyebrow",
                            ),
                            html.H1(result.ticker or "Unavailable"),
                            html.P(
                                result.company_name
                                or "Company name unavailable",
                                className="company-name",
                            ),
                            html.Div(
                                [
                                    dbc.Badge(
                                        result.sector or "Sector unavailable",
                                        color="light",
                                        text_color="dark",
                                    ),
                                    dbc.Badge(
                                        result.industry or "Industry unavailable",
                                        color="light",
                                        text_color="dark",
                                    ),
                                    dbc.Badge(
                                        result.market_cap_group
                                        or "Market-cap group unavailable",
                                        color="light",
                                        text_color="dark",
                                    ),
                                ],
                                className="identity-tags",
                                id="security-classification",
                            ),
                        ],
                        className="identity-company",
                    ),
                    html.P(
                        result.company_description or "Company description unavailable",
                        className="identity-description",
                        id="security-description",
                        title=result.company_description or "Company description unavailable",
                    ),
                ],
                className="identity-row",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Company and market context"),
                            html.Dl(
                                [
                                    html.Div(
                                        [
                                            html.Dt(label),
                                            html.Dd(
                                                _format_value(
                                                    value,
                                                    value_format,
                                                )
                                            ),
                                        ],
                                        className="company-fact",
                                    )
                                    for label, value, value_format in market_items
                                ],
                                className="company-facts",
                            ),
                        ],
                        className="analysis-region company-region",
                        id="company-market-context",
                    ),
                    html.Div(
                        [
                            html.H2("Comparison cohort"),
                            _cohort_member_list(cohort, cohort_error),
                        ],
                        className="analysis-region cohort-region",
                    ),
                    html.Div(
                        [html.H2("Value lens"), _value_lens(result)],
                        className="analysis-region value-region",
                    ),
                ],
                className="security-analysis-grid",
            ),
        ],
        className="analysis-section overview-section",
        id="security-overview",
    )


def _metric_distribution_spread(
    ticker: str,
    metric: MetricDefinition,
    distribution: FinancialMetricDistribution | None,
) -> html.Div:
    """Render compact percentile context without recalculating statistics."""
    if distribution is None or not distribution.values:
        return html.Div(
            "Distribution unavailable",
            className="metric-spread metric-spread-unavailable",
            role="img",
            **{
                "aria-label": (
                    f"{metric.label} peer distribution is unavailable."
                )
            },
        )

    tick_values = (
        (0, "0", distribution.values[0]),
        (10, "10", distribution.p10),
        (25, "25", distribution.p25),
        (50, "Median", distribution.median),
        (75, "75", distribution.p75),
        (90, "90", distribution.p90),
        (100, "100", distribution.values[-1]),
    )
    ticks = [
        html.Span(
            [
                html.Span(className="metric-spread-tick-mark"),
                html.Span(label, className="metric-spread-tick-label"),
            ],
            id=f"spread-tick-{metric.field}-{position}",
            className=(f"metric-spread-tick metric-spread-tick-{position}"),
            style={"left": f"{position}%"},
            title=(
                f"{label}th percentile: "
                f"{_format_value(value, metric.value_format)}"
                if label != "Median"
                else (f"Median: {_format_value(value, metric.value_format)}")
            ),
            **{
                "aria-label": (
                    f"{label} percentile value "
                    f"{_format_value(value, metric.value_format)}"
                )
            },
        )
        for position, label, value in tick_values
    ]

    marker = None
    if (
        distribution.selected_value is not None
        and distribution.percentile is not None
    ):
        percentile = max(0.0, min(100.0, distribution.percentile))
        alignment = (
            " metric-spread-marker-start"
            if percentile < 12
            else " metric-spread-marker-end"
            if percentile > 88
            else ""
        )
        marker = html.Span(
            [
                html.Span(
                    (
                        f"{ticker} "
                        f"{_format_value(distribution.selected_value, metric.value_format)}"
                    ),
                    className="metric-spread-marker-label",
                ),
                html.Span(className="metric-spread-marker-line"),
                html.Span(className="metric-spread-marker-dot"),
            ],
            id=f"spread-marker-{metric.field}",
            className=f"metric-spread-marker{alignment}",
            style={"left": f"{percentile:g}%"},
            title=(
                f"{ticker}: "
                f"{_format_value(distribution.selected_value, metric.value_format)}, "
                f"{_ordinal_percentile(percentile)}"
            ),
        )

    distribution_label = "; ".join(
        (f"{label} percentile {_format_value(value, metric.value_format)}")
        for _, label, value in tick_values
    )
    selected_label = (
        f"{ticker} is at {_ordinal_percentile(distribution.percentile)}."
        if distribution.percentile is not None
        else f"{ticker}'s value is unavailable."
    )
    return html.Div(
        html.Div(
            [
                html.Span(className="metric-spread-axis"),
                *ticks,
                marker,
            ],
            className="metric-spread-track",
        ),
        className="metric-spread",
        role="img",
        title=f"{distribution.comparison_group} peer distribution",
        **{
            "aria-label": (
                f"{metric.label} peer distribution. {distribution_label}. "
                f"{selected_label}"
            )
        },
    )


def _financial_profile_section(
    result: SecurityAnalysisResult,
    distributions: tuple[FinancialMetricDistribution, ...] = (),
    distribution_error: str | None = None,
) -> html.Section:
    annual_period = _format_value(
        result.annual_financial_statement_analysis_date, "date"
    )
    distributions_by_metric = {
        distribution.metric: distribution for distribution in distributions
    }
    return html.Section(
        [
            _section_heading("Descriptive annual metrics", "Financial Profile"),
            html.Div(
                [
                    html.Span("Annual period", className="context-label"),
                    html.Strong(annual_period),
                    html.Span(
                        "Absolute values remain distinct from peer position.",
                        className="context-note",
                    ),
                ],
                className="profile-context-strip",
            ),
            html.Div(
                [
                    html.Div(
                        dbc.Table(
                    [
                        html.Thead(
                            html.Tr(
                                [
                                    html.Th("Metric"),
                                    html.Th("Current value"),
                                    html.Th(
                                        "Financial Metric Distribution Spread"
                                    ),
                                ]
                            )
                        ),
                        html.Tbody(
                            [
                                html.Tr(
                                    [
                                        html.Th(
                                            [
                                                html.Span(
                                                    metric.label,
                                                    id=f"metric-label-{metric.field}",
                                                    className="metric-label",
                                                    tabIndex=0,
                                                ),
                                                dbc.Tooltip(
                                                    metric.calculation,
                                                    target=f"metric-label-{metric.field}",
                                                    placement="right",
                                                ),
                                            ],
                                            scope="row",
                                        ),
                                        html.Td(
                                            _format_value(
                                                getattr(result, metric.field),
                                                metric.value_format,
                                            ),
                                            className="metric-value",
                                        ),
                                        html.Td(
                                            _metric_distribution_spread(
                                                result.ticker,
                                                metric,
                                                distributions_by_metric.get(
                                                    metric.field
                                                ),
                                            ),
                                            className="metric-spread-cell",
                                        ),
                                    ],
                                    id=f"metric-{metric.field}",
                                )
                                for metric in DESCRIPTIVE_METRICS
                            ]
                        ),
                    ],
                    bordered=False,
                    hover=True,
                    responsive=True,
                    className="reveal-table financial-profile-table",
                        ),
                        className="table-frame metric-table-scroll",
                    ),
                    _distribution_section(
                        result, distributions, distribution_error
                    ),
                ],
                className="descriptive-layout",
            ),
        ],
        className="analysis-section",
        id="financial-profile",
    )


def _ordinal_percentile(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    rounded = int(round(value))
    if 10 <= rounded % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(rounded % 10, "th")
    return f"{rounded}{suffix} percentile"


def _distribution_interpretation(
    ticker: str,
    distribution: FinancialMetricDistribution,
    metric: MetricDefinition,
) -> str:
    if distribution.selected_value is None:
        return (
            f"{ticker}'s current value is unavailable. The peer spread is "
            "shown for context, but no percentile can be assigned."
        )

    percentile = distribution.percentile
    if percentile is None:
        band = "at an unavailable position"
    elif percentile >= 90:
        band = "in the top 10% of observed values"
    elif percentile >= 75:
        band = "above the middle 50% of observed values"
    elif percentile > 25:
        band = "within the middle 50% of observed values"
    elif percentile > 10:
        band = "below the middle 50% of observed values"
    else:
        band = "in the bottom 10% of observed values"

    median_position = (
        "above"
        if distribution.selected_value > distribution.median
        else "below"
        if distribution.selected_value < distribution.median
        else "at"
    )
    direction_note = (
        "Higher values are generally more favorable for this metric."
        if metric.direction == "higher"
        else "Lower values are generally more favorable for this metric."
    )
    return (
        f"{ticker} is {band} and {median_position} the peer median. "
        f"{direction_note} Relative position is context, not an investment "
        "verdict."
    )


def _distribution_summary(
    ticker: str,
    distribution: FinancialMetricDistribution,
    peer_result: SecurityAnalysisResult | None = None,
    limiting_tickers: tuple[str, ...] = (),
) -> html.Div:
    metric = METRIC_DEFINITIONS[distribution.metric]
    value_format = metric.value_format
    statistics = (
        ("90th percentile", distribution.p90),
        ("75th percentile", distribution.p75),
        ("Median", distribution.median),
        ("Mean", distribution.mean),
        ("25th percentile", distribution.p25),
        ("10th percentile", distribution.p10),
    )
    peer_value = (
        getattr(peer_result, distribution.metric)
        if peer_result is not None
        else None
    )
    limiting = set(limiting_tickers)
    selected_label = f"{ticker}*" if ticker in limiting else ticker
    comparison_rows = [
        html.Tr(
            [
                html.Th(selected_label, scope="row"),
                html.Td(
                    _format_value(distribution.selected_value, value_format),
                    className="metric-value",
                ),
                html.Td(_ordinal_percentile(distribution.percentile)),
            ]
        )
    ]
    if peer_result is not None:
        peer_label = (
            f"{peer_result.ticker}*"
            if peer_result.ticker in limiting
            else peer_result.ticker
        )
        comparison_rows.append(
            html.Tr(
                [
                    html.Th(peer_label, scope="row"),
                    html.Td(
                        _format_value(peer_value, value_format),
                        className="metric-value peer-metric-value",
                    ),
                    html.Td(
                        "Marked on chart"
                        if peer_value is not None
                        else "Unavailable"
                    ),
                ]
            )
        )
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.P(
                                "Selected metric", className="section-eyebrow"
                            ),
                            html.H3(metric.label),
                        ]
                    ),
                    html.Div(
                        [
                            html.Strong(
                                _format_value(
                                    distribution.selected_value,
                                    value_format,
                                )
                            ),
                            html.Span(
                                _ordinal_percentile(distribution.percentile)
                            ),
                        ],
                        className="distribution-current",
                    ),
                ],
                className="distribution-summary-header",
            ),
            html.P(metric.description, className="distribution-description"),
            dbc.Table(
                [
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Security"),
                                html.Th("Value"),
                                html.Th("Cohort position"),
                            ]
                        )
                    ),
                    html.Tbody(comparison_rows),
                ],
                bordered=False,
                className="comparison-table",
            ),
            html.Dl(
                [
                    html.Div(
                        [
                            html.Dt("Comparison group"),
                            html.Dd(distribution.comparison_group),
                        ]
                    ),
                    html.Div(
                        [
                            html.Dt("Selection basis"),
                            html.Dd(distribution.comparison_basis),
                        ]
                    ),
                    html.Div(
                        [
                            html.Dt("Usable observations"),
                            html.Dd(
                                f"{distribution.sample_size} of "
                                f"{distribution.candidate_count} candidates"
                            ),
                        ]
                    ),
                ],
                className="distribution-meta",
            ),
            dbc.Table(
                html.Tbody(
                    [
                        html.Tr(
                            [
                                html.Th(label, scope="row"),
                                html.Td(
                                    _format_value(value, value_format),
                                    className="metric-value",
                                ),
                            ]
                        )
                        for label, value in statistics
                    ]
                ),
                bordered=False,
                className="distribution-statistics",
            ),
            html.P(
                _distribution_interpretation(ticker, distribution, metric),
                className="distribution-interpretation",
            ),
            html.P(
                [html.Strong("Important context: "), metric.caveat],
                className="distribution-caveat",
            ),
        ],
        className="distribution-summary",
    )


def _distribution_figure(
    ticker: str,
    distribution: FinancialMetricDistribution,
    chart_type: str,
    peer_result: SecurityAnalysisResult | None = None,
    limiting_tickers: tuple[str, ...] = (),
) -> go.Figure:
    metric = METRIC_DEFINITIONS[distribution.metric]
    values = list(distribution.values)
    selected = distribution.selected_value
    figure = go.Figure()

    if chart_type == "box":
        figure.add_trace(
            go.Box(
                x=values,
                name=distribution.comparison_group,
                orientation="h",
                boxpoints="outliers",
                marker_color="#2b6f77",
                line_color="#234f55",
                fillcolor="rgba(43, 111, 119, 0.22)",
                hovertemplate="%{x}<extra>Peer observation</extra>",
            )
        )
    elif chart_type == "scatter":
        ranks = [
            100 * (index + 0.5) / len(values) for index in range(len(values))
        ]
        figure.add_trace(
            go.Scatter(
                x=values,
                y=ranks,
                mode="markers",
                name="Peer observations",
                marker={"color": "#2b6f77", "size": 8, "opacity": 0.74},
                hovertemplate="Value %{x}<br>Position %{y:.0f}%<extra></extra>",
            )
        )
        figure.update_yaxes(title="Percentile position", range=[0, 100])
    else:
        figure.add_trace(
            go.Histogram(
                x=values,
                name="Peer observations",
                marker_color="#2b6f77",
                opacity=0.84,
                hovertemplate="Value %{x}<br>Count %{y}<extra></extra>",
            )
        )
        figure.update_yaxes(title="Observations")

    if selected is not None:
        selected_label = f"{ticker}*" if ticker in limiting_tickers else ticker
        figure.add_vline(
            x=selected,
            line_width=3,
            line_color="#c45b3c",
            annotation_text=selected_label,
            annotation_position="top",
        )

    peer_value = (
        getattr(peer_result, distribution.metric)
        if peer_result is not None
        else None
    )
    if peer_value is not None:
        peer_label = (
            f"{peer_result.ticker}*"
            if peer_result.ticker in limiting_tickers
            else peer_result.ticker
        )
        figure.add_vline(
            x=peer_value,
            line_width=3,
            line_dash="dot",
            line_color="#b37a22",
            annotation_text=peer_label,
            annotation_position="top left",
        )

    tickformat = ".1%" if metric.value_format == "percent" else ".2f"
    figure.update_xaxes(title=metric.label, tickformat=tickformat)
    figure.update_layout(
        template="plotly_white",
        height=285,
        margin={"l": 48, "r": 18, "t": 25, "b": 52},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"family": "Inter, system-ui, sans-serif", "color": "#1e2b28"},
        showlegend=False,
        hoverlabel={"bgcolor": "#ffffff", "font_color": "#18231f"},
    )
    return figure


def _result_from_data(data: dict | None) -> SecurityAnalysisResult | None:
    if not data:
        return None
    return SecurityAnalysisResult(**dict(data))


def _empty_metric_history_figure(
    metric_field: str,
    message: str = "Historical observations are loading",
) -> go.Figure:
    metric = METRIC_DEFINITIONS[metric_field]
    figure = go.Figure()
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": "#60706a"},
    )

    tickformat = ".1%" if metric.value_format == "percent" else ".2f"
    figure.update_yaxes(title=metric.label, tickformat=tickformat)
    figure.update_xaxes(title="Selected-security fiscal year")
    figure.update_layout(
        template="plotly_white",
        barmode="group",
        height=330,
        margin={"l": 64, "r": 24, "t": 34, "b": 66},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"family": "Inter, system-ui, sans-serif", "color": "#1e2b28"},
        legend={"orientation": "h", "y": 1.08, "x": 0},
        hoverlabel={"bgcolor": "#ffffff", "font_color": "#18231f"},
    )
    return figure


def _metric_history_figure(
    comparison: HistoricalMetricComparison,
) -> go.Figure:
    metric = METRIC_DEFINITIONS[comparison.metric]
    figure = go.Figure()
    limiting = set(comparison.limiting_tickers)
    colors = {
        comparison.selected_ticker: "#c45b3c",
        comparison.peer_ticker: "#b37a22",
    }
    tickers = [comparison.selected_ticker]
    if comparison.peer_ticker is not None:
        tickers.append(comparison.peer_ticker)

    for ticker in tickers:
        observations = [
            item for item in comparison.series if item.ticker == ticker
        ]
        if not observations:
            continue
        customdata = [
            [
                item.annual_statement_date,
                item.statement_availability_date,
                item.price_date or "Not applicable",
            ]
            for item in observations
        ]
        price_line = (
            "<br>Price date %{customdata[2]}"
            if comparison.metric == "estimated_owner_earnings_yield"
            else ""
        )
        value_template = (
            "%{y:.1%}"
            if metric.value_format == "percent"
            else "%{y:.2f}"
        )
        label = f"{ticker}*" if ticker in limiting else ticker
        figure.add_trace(go.Bar(
            x=[str(item.anchor_fiscal_year) for item in observations],
            y=[item.value for item in observations],
            customdata=customdata,
            name=label,
            marker_color=colors[ticker],
            hovertemplate=(
                f"{label}<br>Anchor fiscal year %{{x}}"
                "<br>Statement date %{customdata[0]}"
                "<br>Available %{customdata[1]}"
                f"{price_line}<br>Value {value_template}<extra></extra>"
            ),
        ))
    if not figure.data:
        return _empty_metric_history_figure(
            comparison.metric,
            "No availability-aware annual observations",
        )

    tickformat = ".1%" if metric.value_format == "percent" else ".2f"
    figure.update_yaxes(title=metric.label, tickformat=tickformat)
    figure.update_xaxes(title=f"{comparison.selected_ticker} fiscal year")
    figure.update_layout(
        template="plotly_white",
        barmode="group",
        height=330,
        margin={"l": 64, "r": 24, "t": 34, "b": 66},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"family": "Inter, system-ui, sans-serif", "color": "#1e2b28"},
        legend={"orientation": "h", "y": 1.08, "x": 0},
        hoverlabel={"bgcolor": "#ffffff", "font_color": "#18231f"},
    )
    return figure


def _historical_comparison_from_data(
    data: dict | None,
) -> HistoricalMetricComparison | None:
    if not data:
        return None
    payload = dict(data)
    payload["analysis_date"] = date.fromisoformat(str(payload["analysis_date"]))
    payload["available_periods"] = tuple(payload.get("available_periods") or ())
    payload["anchor_fiscal_years"] = tuple(
        payload.get("anchor_fiscal_years") or ()
    )
    payload["series"] = tuple(
        HistoricalMetricObservation(**item)
        for item in payload.get("series") or ()
    )
    payload["limiting_tickers"] = tuple(payload.get("limiting_tickers") or ())
    payload["warning_codes"] = tuple(payload.get("warning_codes") or ())
    return HistoricalMetricComparison(**payload)


def _history_period_options(
    available_periods: tuple[int | str, ...],
) -> list[dict]:
    available = {str(period) for period in available_periods}
    return [
        {
            "label": label,
            "value": value,
            "disabled": value not in available,
        }
        for label, value in (
            ("1Y", "1"),
            ("3Y", "3"),
            ("5Y", "5"),
            ("7Y", "7"),
            ("10Y", "10"),
            ("All", "all"),
        )
    ]


def _history_warning(comparison: HistoricalMetricComparison):
    messages = []
    if "limited_history" in comparison.warning_codes:
        tickers = ", ".join(comparison.limiting_tickers)
        messages.append(
            f"{tickers} limits this comparison to "
            f"{comparison.applied_period} annual observation(s)."
        )
    if "no_comparable_history" in comparison.warning_codes:
        messages.append(
            f"{comparison.peer_ticker} has no valid annual history for this "
            "metric by the analysis cutoff; only the selected security is shown."
        )
    if "fiscal_period_offset" in comparison.warning_codes:
        messages.append(
            "Paired annual statement dates differ by as much as "
            f"{comparison.max_fiscal_period_offset_days} days."
        )
    if not messages:
        return None
    return dbc.Alert(
        html.Ul([html.Li(message) for message in messages]),
        color="warning",
        className="history-warning",
    )


def _distribution_from_data(
    data: list[dict] | None,
    metric_field: str | None,
) -> FinancialMetricDistribution | None:
    for item in data or []:
        if item.get("metric") == metric_field:
            payload = dict(item)
            payload["values"] = tuple(payload.get("values") or ())
            return FinancialMetricDistribution(**payload)
    return None


def _peer_metric_table(
    selected: SecurityAnalysisResult | None,
    peer: SecurityAnalysisResult | None,
):
    if selected is None or peer is None:
        return None
    return html.Div(
        [
            html.H3("Selected security and peer", className="peer-metrics-title"),
            html.Div(
                dbc.Table(
                    [
                        html.Thead(
                            html.Tr(
                                [
                                    html.Th("Metric"),
                                    html.Th(selected.ticker),
                                    html.Th(peer.ticker),
                                ]
                            )
                        ),
                        html.Tbody(
                            [
                                html.Tr(
                                    [
                                        html.Th(metric.label, scope="row"),
                                        html.Td(
                                            _format_value(
                                                getattr(selected, metric.field),
                                                metric.value_format,
                                            )
                                        ),
                                        html.Td(
                                            _format_value(
                                                getattr(peer, metric.field),
                                                metric.value_format,
                                            )
                                        ),
                                    ],
                                    id=f"peer-metric-{metric.field}",
                                )
                                for metric in DESCRIPTIVE_METRICS
                            ]
                        ),
                    ],
                    bordered=False,
                    className="reveal-table peer-metrics-table",
                ),
                className="peer-metrics-scroll",
            ),
        ],
        className="peer-metrics-panel",
    )


def _distribution_section(
    result: SecurityAnalysisResult,
    distributions: tuple[FinancialMetricDistribution, ...],
    error: str | None = None,
) -> html.Section:
    if not distributions:
        message = (
            "Peer context could not be calculated for this request. Current "
            "metric values remain available in the descriptive table."
            if error
            else "No peer cohort has five usable observations for the selected period."
        )
        return html.Section(
            [
                _section_heading(
                    "Peer Distribution", "Current cross-sectional context"
                ),
                dbc.Alert(
                    message, color="warning", className="distribution-alert"
                ),
                html.Div(
                    "Comparison: no peer selected",
                    id="comparison-request-status",
                    className="comparison-status",
                    **{"aria-live": "polite"},
                ),
                html.Div(id="peer-metric-table"),
            ],
            className="distribution-panel",
            id="peer-distribution",
        )

    available = {item.metric: item for item in distributions}
    default_metric = next(
        metric.field
        for metric in DESCRIPTIVE_METRICS
        if metric.field in available
    )
    default_distribution = available[default_metric]
    serialized = [asdict(item) for item in distributions]
    return html.Section(
        [
            _section_heading(
                "Peer Distribution", "Current cross-sectional context"
            ),
            html.P(
                "Metric values use the selected analysis cutoff. Cohort "
                "membership uses the latest locally stored company "
                "classification and is not a strict historical universe.",
                className="distribution-method-note",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label(
                                "Metric", htmlFor="distribution-metric-select"
                            ),
                            dcc.Dropdown(
                                id="distribution-metric-select",
                                options=[
                                    {
                                        "label": METRIC_DEFINITIONS[
                                            item.metric
                                        ].label,
                                        "value": item.metric,
                                    }
                                    for item in distributions
                                ],
                                value=default_metric,
                                clearable=False,
                                searchable=False,
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Chart",
                                htmlFor="distribution-chart-select",
                            ),
                            dcc.Dropdown(
                                id="distribution-chart-select",
                                options=[
                                    {
                                        "label": "Scatter plot",
                                        "value": "scatter",
                                    },
                                    {
                                        "label": "Histogram",
                                        "value": "histogram",
                                    },
                                    {"label": "Box plot", "value": "box"},
                                ],
                                value="scatter",
                                clearable=False,
                                searchable=False,
                            ),
                        ]
                    ),
                ],
                className="distribution-controls",
            ),
            html.Div(
                "Comparison: no peer selected",
                id="comparison-request-status",
                className="comparison-status",
                **{"aria-live": "polite"},
            ),
            html.Div(id="peer-metric-table"),
            html.Div(
                _distribution_summary(result.ticker, default_distribution),
                id="distribution-summary",
                className="distribution-summary",
            ),
            dcc.Store(id="distribution-data", data=serialized),
            dcc.Store(id="distribution-ticker", data=result.ticker),
            dcc.Store(id="history-comparison-data"),
        ],
        className="distribution-panel",
        id="peer-distribution",
    )


def _history_section(
    result: SecurityAnalysisResult,
    distributions: tuple[FinancialMetricDistribution, ...],
) -> html.Section | None:
    if not distributions:
        return None
    available = {item.metric: item for item in distributions}
    default_metric = next(
        metric.field for metric in DESCRIPTIVE_METRICS
        if metric.field in available
    )
    return html.Section(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.P("Metric history", className="section-eyebrow"),
                            html.H3("Annual metric comparison"),
                        ]
                    ),
                    dcc.RadioItems(
                        id="history-period-select",
                        options=_history_period_options((1, 3, 5, 7, 10, "all")),
                        value="5",
                        inline=True,
                        className="history-period-control",
                    ),
                ],
                className="history-header",
            ),
            html.P(
                "Annual values use statements with verified filing "
                "availability by the analysis cutoff.",
                className="history-contract-note",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H4("Current peer distribution"),
                            dcc.Graph(
                                id="distribution-graph",
                                figure=_distribution_figure(
                                    result.ticker,
                                    available[default_metric],
                                    "scatter",
                                ),
                                config={
                                    "displayModeBar": False,
                                    "responsive": True,
                                },
                            ),
                        ],
                        className="comparison-chart-pane distribution-chart",
                        id="current-distribution-chart",
                    ),
                    html.Div(
                        [
                            html.H4("Annual metric history"),
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="metric-history-graph",
                                        figure=_empty_metric_history_figure(
                                            default_metric
                                        ),
                                        config={
                                            "displayModeBar": False,
                                            "responsive": True,
                                        },
                                    ),
                                    html.Div(
                                        id="history-warning",
                                        **{"aria-live": "polite"},
                                    ),
                                ],
                                id="history-chart-container",
                                className="history-chart-container",
                            ),
                        ],
                        className="comparison-chart-pane",
                    ),
                ],
                className="comparison-charts-grid",
            ),
        ],
        className="analysis-section history-panel",
        id="metric-history",
    )


def _criteria_table(
    result: SecurityAnalysisResult,
    criteria: tuple[tuple[str, str, str | None, str], ...],
) -> dbc.Table:
    return dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Criterion"),
                        html.Th("Result"),
                        html.Th("Observed value"),
                    ]
                )
            ),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Th(label, scope="row"),
                            html.Td(
                                [
                                    html.Span(
                                        _status_badge(
                                            _field_state(result, status_field)
                                        ),
                                        id=f"criterion-result-{status_field}",
                                        className="criterion-result",
                                        tabIndex=0,
                                    ),
                                    dbc.Tooltip(
                                        _criterion_context(
                                            result,
                                            status_field,
                                            _field_state(result, status_field),
                                        ),
                                        target=f"criterion-result-{status_field}",
                                        placement="right",
                                    ),
                                ]
                            ),
                            html.Td(
                                "Not applicable"
                                if status_field in result.not_applicable_fields
                                else (
                                    _format_value(
                                        getattr(result, value_field),
                                        value_format,
                                    )
                                    if value_field
                                    else "Not separately reported"
                                ),
                                className="metric-value",
                            ),
                        ]
                    )
                    for status_field, label, value_field, value_format in criteria
                ]
            ),
        ],
        bordered=False,
        hover=True,
        responsive=True,
        className="reveal-table criteria-table",
    )


def _graham_section(result: SecurityAnalysisResult) -> html.Section:
    return html.Section(
        [
            _section_heading("Criteria-based analysis", "Graham and Magic Formula"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H3("Defensive"),
                                    _summary_badge(
                                        result.defensive_criteria_met
                                    ),
                                ],
                                className="subsection-title",
                            ),
                            _criteria_table(result, DEFENSIVE_CRITERIA),
                            html.Dl(
                                [
                                    html.Div(
                                        [
                                            html.Dt("Graham Number"),
                                            html.Dd(
                                                _format_value(
                                                    result.graham_number,
                                                    "currency",
                                                )
                                            ),
                                        ]
                                    ),
                                    html.Div(
                                        [
                                            html.Dt("Margin of safety"),
                                            html.Dd(
                                                _format_value(
                                                    result.defensive_margin_of_safety,
                                                    "multiple",
                                                )
                                            ),
                                        ]
                                    ),
                                ],
                                className="valuation-strip",
                            ),
                        ],
                        className="graham-column",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H3("Enterprising"),
                                    _summary_badge(
                                        result.enterprising_criteria_met
                                    ),
                                ],
                                className="subsection-title",
                            ),
                            _criteria_table(result, ENTERPRISING_CRITERIA),
                            html.Dl(
                                [
                                    html.Div(
                                        [
                                            html.Dt("Serenity Number"),
                                            html.Dd(
                                                _format_value(
                                                    result.serenity_number,
                                                    "currency",
                                                )
                                            ),
                                        ]
                                    ),
                                    html.Div(
                                        [
                                            html.Dt("Margin of safety"),
                                            html.Dd(
                                                _format_value(
                                                    result.enterprising_margin_of_safety,
                                                    "multiple",
                                                )
                                            ),
                                        ]
                                    ),
                                ],
                                className="valuation-strip",
                            ),
                        ],
                        className="graham-column",
                    ),
                    _magic_formula_section(result),
                ],
                className="graham-grid",
            ),
            html.P(
                [
                    html.Strong("Two ROC views: "),
                    "Financial Profile ROC uses annual EBIT and average capital "
                    "employed. Magic Formula ROC uses TTM EBIT and a "
                    "quarter-aware capital base for ordinal ranking.",
                ],
                className="method-note",
            ),
        ],
        className="analysis-section",
        id="graham-analysis",
    )


def _magic_formula_section(result: SecurityAnalysisResult) -> html.Div:
    values = (
        (
            "magic_formula_rank",
            "Magic Formula rank",
            result.magic_formula_rank,
            "integer",
        ),
        (
            "return_on_capital_rank",
            "Return on Capital rank",
            result.return_on_capital_rank,
            "integer",
        ),
        (
            "earnings_yield_rank",
            "Earnings Yield rank",
            result.earnings_yield_rank,
            "integer",
        ),
        (
            "total_roc_ey_score",
            "Combined rank score",
            result.total_roc_ey_score,
            "integer",
        ),
        (
            "return_on_capital",
            "Return on Capital (TTM)",
            result.return_on_capital,
            "percent",
        ),
        (
            "earnings_yield",
            "Earnings Yield (TTM)",
            result.earnings_yield,
            "percent",
        ),
        (
            "magic_formula_quarter_date",
            "Ranking quarter",
            result.magic_formula_quarter_date,
            "date",
        ),
        (
            "magic_formula_associated_annual_date",
            "Associated annual period",
            result.magic_formula_associated_annual_date,
            "date",
        ),
        (
            "magic_formula_financial_statement_availability_date",
            "Statement availability",
            result.magic_formula_financial_statement_availability_date,
            "date",
        ),
    )
    explanations = _field_explanations(result)
    magic_formula_explanation = explanations.get("magic_formula_rank")
    return html.Div(
        [
            html.Div(
                html.H3("Magic Formula"),
                className="subsection-title",
            ),
            dbc.Alert(
                [
                    html.Strong("Not applicable. "),
                    html.Span(magic_formula_explanation),
                ],
                color="info",
                className="applicability-alert",
            )
            if magic_formula_explanation
            else None,
            html.Div(
                dbc.Table(
                    html.Tbody(
                        [
                            html.Tr(
                                [
                                    html.Th(label, scope="row"),
                                    html.Td(
                                        "Not applicable"
                                        if field
                                        in result.not_applicable_fields
                                        else _format_value(
                                            value, value_format
                                        ),
                                        className="metric-value",
                                    ),
                                ]
                            )
                            for field, label, value, value_format in values
                        ]
                    ),
                    bordered=False,
                    responsive=True,
                    className="reveal-table key-value-table",
                ),
                className="table-frame compact-table",
            ),
        ],
        className="graham-column magic-formula-column",
        id="magic-formula",
    )


def _data_quality_section(result: SecurityAnalysisResult) -> html.Section:
    warnings = list(result.calculation_warnings)
    missing_fields = list(result.missing_fields)
    applicability_notes = list(
        dict.fromkeys(_field_explanations(result).values())
    )
    quality_message = (
        "Required identity fields are present and no calculation warnings "
        "were reported."
        if result.data_complete
        else "Review unavailable fields and warnings before comparing this result."
    )
    return html.Section(
        [
            _section_heading(
                "Data Quality", "Completeness and calculation context"
            ),
            dbc.Alert(
                [
                    html.Strong(
                        "Complete"
                        if result.data_complete
                        else "Partial result"
                    ),
                    html.Span(quality_message),
                ],
                color="success" if result.data_complete else "warning",
                className="quality-alert",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Missing required fields"),
                            html.Ul(
                                [html.Li(field) for field in missing_fields]
                                or [html.Li("None")]
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.H3("Calculation warnings"),
                            html.Ul(
                                [html.Li(warning) for warning in warnings]
                                or [html.Li("None")]
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.H3("Method applicability"),
                            html.Ul(
                                [html.Li(note) for note in applicability_notes]
                                or [html.Li("No method exclusions")]
                            ),
                        ]
                    ),
                ],
                className="quality-grid",
            ),
        ],
        className="analysis-section",
        id="data-quality",
    )


def build_analysis_view(
    result: SecurityAnalysisResult,
    distributions: tuple[FinancialMetricDistribution, ...] = (),
    distribution_error: str | None = None,
    cohort: ComparableSecurityCohort | None = None,
    cohort_error: str | None = None,
) -> html.Div:
    """Build dashboard components from the frozen application result model."""
    return html.Div(
        [
            dcc.Store(id="primary-analysis-data", data=asdict(result)),
            dcc.Store(id="peer-analysis-data"),
            _overview_section(result, cohort, cohort_error),
            _financial_profile_section(
                result, distributions, distribution_error
            ),
            _history_section(result, distributions),
            _graham_section(result),
            _data_quality_section(result),
        ],
        className="analysis-view",
    )


def _security_type_link(asset_type: str | None, company_name: str) -> str:
    normalized = str(asset_type or "").strip().upper()
    normalized_name = company_name.upper()
    if "WARRANT" in normalized or "WARRANT" in normalized_name:
        return SECURITY_TYPE_LINKS["WARRANT"]
    if "PREFERRED" in normalized or "PREFERRED" in normalized_name:
        return SECURITY_TYPE_LINKS["PREFERRED STOCK"]
    return SECURITY_TYPE_LINKS["COMMON STOCK"]


def _ineligible_view(
    assessment: SecurityEligibilityAssessment,
) -> html.Section:
    return html.Section(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.P(
                                "Security eligibility",
                                className="section-eyebrow",
                            ),
                            html.H1(assessment.ticker),
                            html.P(
                                assessment.company_name
                                or "Company name unavailable",
                                className="company-name",
                            ),
                        ]
                    ),
                    dbc.Badge(
                        "Ineligible",
                        color="danger",
                        className="eligibility-badge",
                    ),
                ],
                className="identity-row",
            ),
            html.H2("This security is outside Reveal's analysis universe."),
            html.Ul(
                [html.Li(reason) for reason in assessment.reasons],
                className="eligibility-reasons",
            ),
            html.P(
                "Reveal v1 analyzes U.S.-listed common stocks with at least "
                "$250 million in market capitalization and five years of "
                "financial and market-price history."
            ),
            html.A(
                "Learn about this security type on Investopedia",
                href=_security_type_link(
                    assessment.asset_type, assessment.company_name
                ),
                target="_blank",
                rel="noopener noreferrer",
                className="education-link",
            ),
        ],
        className="analysis-section ineligible-section",
    )


def analyze_ticker(
    ticker: str | None,
    analysis_date: str | None,
    analyzer: Callable[[str, str | None], SecurityAnalysisResult],
    eligibility_checker: Callable[[str], SecurityEligibilityAssessment]
    | None = None,
    distribution_provider: Callable[
        [SecurityAnalysisResult], tuple[FinancialMetricDistribution, ...]
    ]
    | None = None,
    cohort_provider: Callable[
        [SecurityAnalysisResult, str | None], ComparableSecurityCohort
    ]
    | None = None,
    identifier_resolver: Callable[[str], str] | None = None,
):
    """Validate dashboard input and render one contract-shaped result."""
    identifier = (ticker or "").strip()
    if not identifier:
        return dbc.Alert(
            "Enter a ticker, company name, or SEC CIK to run an analysis.",
            color="warning",
            className="request-alert",
        )

    try:
        normalized_ticker = (
            identifier_resolver(identifier)
            if identifier_resolver is not None
            else identifier.upper()
        )
    except (TypeError, ValueError) as exc:
        return dbc.Alert(
            str(exc),
            color="warning",
            className="request-alert",
        )
    except Exception:
        LOGGER.exception("Reveal identifier search failed for %s", identifier)
        return dbc.Alert(
            "Security search is temporarily unavailable.",
            color="danger",
            className="request-alert",
        )

    try:
        if eligibility_checker is not None:
            eligibility = eligibility_checker(normalized_ticker)
            if not eligibility.eligible:
                return _ineligible_view(eligibility)
        result = analyzer(normalized_ticker, analysis_date or None)
    except Exception as exc:  # The UI boundary must keep the page usable.
        LOGGER.exception("Reveal analysis failed for %s", normalized_ticker)
        return dbc.Alert(
            [
                html.Strong("Analysis unavailable. "),
                html.Span(str(exc) or "The security could not be analyzed."),
            ],
            color="danger",
            className="request-alert",
        )

    distributions = ()
    distribution_error = None
    if distribution_provider is not None:
        try:
            distributions = tuple(distribution_provider(result))
        except Exception:
            LOGGER.exception(
                "Reveal peer distribution failed for %s",
                normalized_ticker,
            )
            distribution_error = "Peer distribution unavailable"

    cohort = None
    cohort_error = None
    if cohort_provider is not None:
        try:
            comparison_basis = (
                distributions[0].comparison_basis if distributions else None
            )
            cohort = cohort_provider(result, comparison_basis)
        except Exception:
            LOGGER.exception(
                "Reveal cohort membership failed for %s",
                normalized_ticker,
            )
            cohort_error = "Cohort membership unavailable"

    return build_analysis_view(
        result,
        distributions,
        distribution_error,
        cohort,
        cohort_error,
    )


def _security_suggestion_options(
    query: str | None,
    search_provider,
) -> list:
    """Build native input suggestions from inexpensive SEC metadata."""
    normalized_query = (query or "").strip()
    if not normalized_query:
        return []
    try:
        matches = search_provider(normalized_query, limit=8)
    except Exception:
        LOGGER.exception(
            "Reveal identifier suggestions failed for %s",
            normalized_query,
        )
        return []

    return [
        html.Option(
            value=match["ticker"],
            label=(
                f'{match["company_name"] or "Company name unavailable"} | '
                f'CIK {match["cik"] or "unavailable"}'
            ),
        )
        for match in matches
    ]


def _magic_formula_dropdown_options(
    rankings: tuple[MagicFormulaRankedSecurity, ...],
) -> list[dict[str, str]]:
    return [
        {
            "label": f"{item.rank}. {item.ticker} | {item.company_name}",
            "value": item.ticker,
        }
        for item in rankings
    ]


def _initial_layout(
    magic_formula_rankings: tuple[MagicFormulaRankedSecurity, ...] = (),
) -> html.Div:
    ranking_options = _magic_formula_dropdown_options(magic_formula_rankings)
    ranking_date = (
        magic_formula_rankings[0].quarter_date
        if magic_formula_rankings
        else None
    )
    return html.Div(
        [
            html.Header(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span("R", className="brand-mark"),
                                html.Div(
                                    [
                                        html.P(
                                            "Investment analysis",
                                            className="brand-kicker",
                                        ),
                                        html.H1("Reveal"),
                                    ]
                                ),
                            ],
                            className="brand-lockup",
                        ),
                        dbc.Badge(
                            f"v{_application_version()}",
                            color="light",
                            text_color="dark",
                            className="version-badge",
                        ),
                    ],
                    className="header-inner",
                ),
                className="app-header",
            ),
            html.P(
                "An investment application of practical counsel",
                className="app-subtitle",
            ),
            html.Main(
                [
                    html.Section(
                        [
                            html.Div(
                                [
                                    html.Label(
                                        "Security", htmlFor="ticker-input"
                                    ),
                                    dbc.Input(
                                        id="ticker-input",
                                        type="text",
                                        placeholder=(
                                            "Ticker, company name, or 10-digit "
                                            "SEC CIK"
                                        ),
                                        maxLength=160,
                                        autoComplete="off",
                                        list="security-suggestions",
                                    ),
                                    html.Datalist(id="security-suggestions"),
                                ],
                                className="ticker-control",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "Analysis date",
                                        htmlFor="analysis-date-input",
                                    ),
                                    dbc.Input(
                                        id="analysis-date-input",
                                        type="date",
                                    ),
                                ],
                                className="date-control",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "Magic Formula ranking",
                                        htmlFor="magic-formula-security-select",
                                    ),
                                    dcc.Dropdown(
                                        id="magic-formula-security-select",
                                        options=ranking_options,
                                        placeholder=(
                                            f"Select from {ranking_date} rankings"
                                            if ranking_date
                                            else "Rankings unavailable"
                                        ),
                                        clearable=True,
                                        searchable=True,
                                        disabled=not ranking_options,
                                    ),
                                ],
                                className="magic-formula-control",
                            ),
                            dbc.Button(
                                "Analyze",
                                id="analyze-button",
                                color="primary",
                                n_clicks=0,
                            ),
                        ],
                        className="analysis-controls",
                        **{"aria-label": "Security analysis controls"},
                    ),
                    html.Div(
                        id="analysis-status", className="visually-hidden"
                    ),
                    dcc.Loading(
                        html.Div(
                            html.Div(
                                [
                                    html.P(
                                        "Ready for analysis",
                                        className="section-eyebrow",
                                    ),
                                    html.H2("No security selected"),
                                ],
                                className="empty-state",
                            ),
                            id="analysis-results",
                            **{"aria-live": "polite"},
                        ),
                        type="circle",
                        color="#0b6b57",
                    ),
                ],
                className="app-main",
            ),
            html.Footer(
                "Reveal is educational and research-oriented, not financial advice.",
                className="app-footer",
            ),
        ],
        className="app-shell",
    )


def create_app(
    analyzer: Callable[[str, str | None], SecurityAnalysisResult]
    | None = None,
    eligibility_checker: Callable[[str], SecurityEligibilityAssessment]
    | None = None,
    distribution_provider: Callable[
        [SecurityAnalysisResult], tuple[FinancialMetricDistribution, ...]
    ]
    | None = None,
    cohort_provider: Callable[
        [SecurityAnalysisResult, str | None], ComparableSecurityCohort
    ]
    | None = None,
    history_provider: Callable[
        [SecurityAnalysisResult, str, int | str, str | None],
        HistoricalMetricComparison,
    ]
    | None = None,
    identifier_search_provider=None,
    identifier_resolver: Callable[[str], str] | None = None,
    magic_formula_rankings_provider: Callable[
        [], tuple[MagicFormulaRankedSecurity, ...]
    ]
    | None = None,
) -> Dash:
    """Create the Reveal Dash application with an injectable service boundary."""
    analyze = analyzer or service.analyze_security
    assess_eligibility = (
        eligibility_checker or service.assess_security_eligibility
    )
    provide_distributions = distribution_provider
    if provide_distributions is None and analyzer is None:
        def provide_distributions(result):
            return service.financial_profile_distributions(
                result, metric_fields=service.DESCRIPTIVE_METRIC_FIELDS
            )
    provide_cohort = cohort_provider
    if provide_cohort is None and analyzer is None:
        provide_cohort = service.comparable_security_cohort
    provide_history = history_provider
    if provide_history is None and analyzer is None:
        provide_history = service.historical_financial_profile_comparison
    search_identifiers = (
        identifier_search_provider or service.search_security_identifiers
    )
    resolve_identifier = (
        identifier_resolver or service.resolve_security_identifier
    )
    provide_magic_formula_rankings = magic_formula_rankings_provider
    if provide_magic_formula_rankings is None and analyzer is None:
        provide_magic_formula_rankings = (
            service.current_magic_formula_ranked_securities
        )
    magic_formula_rankings = ()
    if provide_magic_formula_rankings is not None:
        try:
            magic_formula_rankings = tuple(provide_magic_formula_rankings())
        except Exception:
            LOGGER.exception("Reveal Magic Formula ranking list failed")
    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="Reveal",
        update_title="Analyzing...",
        suppress_callback_exceptions=True,
    )
    app.layout = _initial_layout(magic_formula_rankings)

    @app.callback(
        Output("ticker-input", "value"),
        Input("magic-formula-security-select", "value"),
        prevent_initial_call=True,
    )
    def select_magic_formula_security(ticker):
        normalized_ticker = (ticker or "").strip().upper()
        if not normalized_ticker:
            raise PreventUpdate
        return normalized_ticker

    @app.callback(
        Output("security-suggestions", "children"),
        Input("ticker-input", "value"),
    )
    def update_security_suggestions(identifier):
        return _security_suggestion_options(identifier, search_identifiers)

    @app.callback(
        Output("analysis-results", "children"),
        Output("analysis-status", "children"),
        Input("analyze-button", "n_clicks"),
        Input("ticker-input", "n_submit"),
        State("ticker-input", "value"),
        State("analysis-date-input", "value"),
        prevent_initial_call=True,
    )
    def update_analysis(_clicks, _submits, ticker, analysis_date):
        normalized_ticker = (ticker or "").strip().upper()
        return (
            analyze_ticker(
                ticker,
                analysis_date,
                analyze,
                assess_eligibility,
                provide_distributions,
                provide_cohort,
                resolve_identifier,
            ),
            f"Analysis request completed for {normalized_ticker}"
            if normalized_ticker
            else "Security identifier required",
        )

    @app.callback(
        Output("distribution-summary", "children"),
        Output("distribution-graph", "figure"),
        Input("distribution-metric-select", "value"),
        Input("distribution-chart-select", "value"),
        Input("peer-analysis-data", "data"),
        Input("history-comparison-data", "data"),
        State("distribution-data", "data"),
        State("distribution-ticker", "data"),
    )
    def update_distribution(
        metric_field,
        chart_type,
        peer_data,
        history_data,
        data,
        ticker,
    ):
        distribution = _distribution_from_data(data, metric_field)
        if distribution is None:
            raise PreventUpdate
        peer_result = _result_from_data(peer_data)
        history = _historical_comparison_from_data(history_data)
        limiting_tickers = (
            history.limiting_tickers
            if history is not None and history.metric == metric_field
            else ()
        )
        return (
            _distribution_summary(
                ticker,
                distribution,
                peer_result,
                limiting_tickers,
            ),
            _distribution_figure(
                ticker,
                distribution,
                chart_type,
                peer_result,
                limiting_tickers,
            ),
        )

    @app.callback(
        Output("peer-metric-table", "children"),
        Input("peer-analysis-data", "data"),
        State("primary-analysis-data", "data"),
    )
    def update_peer_metric_table(peer_data, primary_data):
        return _peer_metric_table(
            _result_from_data(primary_data),
            _result_from_data(peer_data),
        )

    @app.callback(
        Output("metric-history-graph", "figure"),
        Output("history-period-select", "options"),
        Output("history-comparison-data", "data"),
        Output("history-warning", "children"),
        Output("history-chart-container", "className"),
        Input("distribution-metric-select", "value"),
        Input("history-period-select", "value"),
        Input("peer-analysis-data", "data"),
        State("primary-analysis-data", "data"),
    )
    def update_history(metric_field, requested_period, peer_data, primary_data):
        primary_result = _result_from_data(primary_data)
        if primary_result is None or metric_field not in METRIC_DEFINITIONS:
            raise PreventUpdate
        if metric_field not in service.FINANCIAL_PROFILE_FIELDS:
            return (
                _empty_metric_history_figure(
                    metric_field,
                    "Annual history is available for the seven core metrics",
                ),
                _history_period_options(()),
                None,
                dbc.Alert(
                    "Annual history is available for the seven core metrics.",
                    color="secondary",
                    className="history-warning",
                ),
                "history-chart-container",
            )
        if provide_history is None:
            return (
                _empty_metric_history_figure(
                    metric_field,
                    "Historical service unavailable",
                ),
                _history_period_options(()),
                None,
                dbc.Alert(
                    "Historical comparison unavailable.",
                    color="warning",
                    className="history-warning",
                ),
                "history-chart-container history-chart-warning",
            )
        period = (
            "all" if requested_period == "all" else int(requested_period)
        )
        peer_result = _result_from_data(peer_data)
        peer_ticker = peer_result.ticker if peer_result is not None else None
        try:
            comparison = provide_history(
                primary_result,
                metric_field,
                period,
                peer_ticker,
            )
        except Exception as exc:
            LOGGER.exception(
                "Reveal historical comparison failed for %s",
                primary_result.ticker,
            )
            return (
                _empty_metric_history_figure(
                    metric_field,
                    "Historical comparison unavailable",
                ),
                _history_period_options(()),
                None,
                dbc.Alert(
                    f"Historical comparison unavailable: {exc}",
                    color="warning",
                    className="history-warning",
                ),
                "history-chart-container history-chart-warning",
            )

        class_name = "history-chart-container"
        if comparison.warning_codes:
            class_name += " history-chart-warning"
        return (
            _metric_history_figure(comparison),
            _history_period_options(comparison.available_periods),
            asdict(comparison),
            _history_warning(comparison),
            class_name,
        )

    @app.callback(
        Output("peer-analysis-data", "data"),
        Output("comparison-request-status", "children"),
        Input({"type": "cohort-peer-link", "ticker": ALL}, "n_clicks"),
        State("primary-analysis-data", "data"),
        prevent_initial_call=True,
    )
    def load_peer_comparison(_clicks, primary_data):
        triggered_id = ctx.triggered_id
        if not isinstance(triggered_id, dict):
            raise PreventUpdate
        peer_ticker = triggered_id.get("ticker")
        primary_result = _result_from_data(primary_data)
        if not peer_ticker or primary_result is None:
            raise PreventUpdate
        try:
            peer_result = analyze(
                peer_ticker,
                str(primary_result.analysis_date),
            )
        except Exception as exc:
            LOGGER.exception(
                "Reveal peer analysis failed for %s",
                peer_ticker,
            )
            return (
                no_update,
                f"Comparison unavailable for {peer_ticker}: {exc}",
            )
        return (
            asdict(peer_result),
            f"Comparing {primary_result.ticker} with {peer_result.ticker}",
        )

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Reveal dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    create_app().run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
