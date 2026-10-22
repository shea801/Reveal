# Stable application result model for Reveal security analysis.
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional


@dataclass(frozen=True)
class SecurityEligibilityAssessment:
    """Pre-analysis eligibility result used by interactive entry points."""

    ticker: str
    eligible: bool
    company_name: str = ""
    asset_type: Optional[str] = None
    exchange: Optional[str] = None
    market_cap: Optional[float] = None
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MagicFormulaRankedSecurity:
    """Presentation-ready member of the latest Magic Formula ranking."""

    rank: int
    ticker: str
    company_name: str
    quarter_date: str


@dataclass(frozen=True)
class ComparableSecurity:
    """Persisted identity and classification for one comparison member."""

    ticker: str
    company_name: str
    industry: Optional[str] = None
    sector: Optional[str] = None
    market_cap_group: Optional[str] = None


@dataclass(frozen=True)
class ComparableSecurityCohort:
    """Presentation-ready membership for one current comparison cohort."""

    selected_ticker: str
    comparison_basis: str
    comparison_group: str
    members: tuple[ComparableSecurity, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FinancialMetricDistribution:
    """Presentation-ready cross-sectional context for one profile metric."""

    metric: str
    comparison_basis: str
    comparison_group: str
    sample_size: int
    candidate_count: int
    values: tuple[float, ...] = field(default_factory=tuple)
    selected_value: Optional[float] = None
    percentile: Optional[float] = None
    p10: Optional[float] = None
    p25: Optional[float] = None
    median: Optional[float] = None
    mean: Optional[float] = None
    p75: Optional[float] = None
    p90: Optional[float] = None


HistoricalComparisonPeriod = int | Literal["all"]
HistoricalComparisonWarning = Literal[
    "limited_history",
    "no_comparable_history",
    "fiscal_period_offset",
]


@dataclass(frozen=True)
class HistoricalMetricObservation:
    """One availability-aware annual metric observation."""

    ticker: str
    anchor_fiscal_year: int
    fiscal_year: int
    annual_statement_date: str
    statement_availability_date: str
    price_date: Optional[str]
    value: float


@dataclass(frozen=True)
class HistoricalMetricComparison:
    """Presentation-ready aligned annual history for one profile metric."""

    metric: str
    analysis_date: date
    requested_period: HistoricalComparisonPeriod
    applied_period: int
    available_periods: tuple[HistoricalComparisonPeriod, ...]
    selected_ticker: str
    peer_ticker: Optional[str]
    anchor_fiscal_years: tuple[int, ...]
    series: tuple[HistoricalMetricObservation, ...]
    limiting_tickers: tuple[str, ...]
    max_fiscal_period_offset_days: int
    warning_codes: tuple[HistoricalComparisonWarning, ...]


@dataclass(frozen=True)
class SecurityAnalysisResult:

    """
    Mapping component to pair financial metrics to their calculated values.
    """
    # basic security information to begin analysis
    ticker: str # trading symbol
    company_name: str # company name
    analysis_date: date # date the analysis is using as a starting point (most recent by default)
    company_description: Optional[str] = None # company description if available
    price_date: Optional[str] = None
    annual_financial_statement_analysis_date: Optional[str] = None
    quarter_financial_statement_analysis_date: Optional[str] = None
    market_price_for_period: Optional[float] = None
    min_200_day_price: Optional[float] = None
    max_200_day_price: Optional[float] = None
    avg_price_200_day: Optional[float] = None
    median_price_200_day: Optional[float] = None
    market_cap: Optional[float] = None
    market_cap_group: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    total_sales_services: Optional[float] = None
    price_to_earnings: Optional[float] = None

    # Graham principal metrics
    eps: Optional[float] = None
    period_three_year_average_eps: Optional[float] = None

    # Graham Defensive metrics
    defensive_revenue_requirement_met: Optional[bool] = None
    current_assets_200pct_or_greater_current_liabilities_met: Optional[bool] = None
    current_assets_to_current_liabilities_ratio: Optional[float] = None
    long_term_debt_less_than_net_current_assets_met: Optional[bool] = None
    long_term_debt_to_net_current_assets_ratio: Optional[float] = None
    utility_debt_to_book_equity_met: Optional[bool] = None
    long_term_debt_to_book_equity_ratio: Optional[float] = None
    positive_earnings_for_the_past_10_years_met: Optional[bool] = None
    eps_3yr_average_33pct_gte_10yr_previous_eps_met: Optional[bool] = None
    eps_3yr_average_to_10yr_previous_eps_ratio: Optional[float] = None
    continuous_dividend_payments_for_past_20yrs_met: Optional[bool] = None
    average_dividend_payments_for_past_20yrs: Optional[float] = None
    price_15x_or_less_eps_3yr_average_met: Optional[bool] = None
    price_to_eps_3yr_average: Optional[float] = None
    price_150pct_or_less_book_value_met: Optional[bool] = None
    price_to_book_value: Optional[float] = None
    graham_number: Optional[float] = None
    defensive_margin_of_safety: Optional[float] = None

    # Graham Enterprising metrics
    current_assets_150pct_or_greater_long_term_debt_met: Optional[bool] = None
    current_assets_150pct_or_greater_than_long_term_debt_ratio: Optional[float] = None
    long_term_debt_110pct_or_less_to_net_current_assets_met: Optional[bool] = None
    no_earnings_deficit_for_5yrs_met: Optional[bool] = None
    earnings_growth_greater_than_5yrs_previous_met: Optional[bool] = None
    earnings_to_5yr_earnings_lookback_ratio: Optional[float] = None
    price_120pct_or_less_tangible_book_met: Optional[bool] = None
    price_to_tangible_book_value: Optional[float] = None
    tangible_book_value_per_share: Optional[float] = None
    serenity_number: Optional[float] = None
    enterprising_margin_of_safety: Optional[float] = None

    # Magic Formula metrics
    eps_ttm: Optional[float] = None
    net_income_ttm: Optional[float] = None
    ebit_ttm: Optional[float] = None
    return_on_capital: Optional[float] = None # ebit / total capital
    earnings_yield: Optional[float] = None # ebit / (market cap + short & long term debt)
    magic_formula_quarter_date: Optional[str] = None
    magic_formula_associated_annual_date: Optional[str] = None
    magic_formula_financial_statement_availability_date: Optional[str] = None
    magic_formula_rank: Optional[int] = None # overall rank of summed ordinal ranks
    return_on_capital_rank: Optional[int] = None
    earnings_yield_rank: Optional[int] = None
    total_roc_ey_score: Optional[int] = None

    # Graham strategy summaries
    defensive_criteria_met: Optional[bool] = None
    enterprising_criteria_met: Optional[bool] = None

    # financial metrics for general company overview
    gross_margin: Optional[float] = None
    free_cash_flow: Optional[float] = None
    free_cash_flow_margin: Optional[float] = None
    estimated_owner_earnings: Optional[float] = None
    estimated_owner_earnings_yield: Optional[float] = None
    operating_income: Optional[float] = None
    inventory_turnover: Optional[float] = None
    return_on_assets: Optional[float] = None
    return_on_equity: Optional[float] = None
    return_on_invested_capital: Optional[float] = None
    financial_profile_return_on_capital: Optional[float] = None
    eps_cagr_5yr: Optional[float] = None
    debt_to_equity: Optional[float] = None
    debt_to_assets: Optional[float] = None
    longterm_debt_to_cash: Optional[float] = None
    interest_coverage: Optional[float] = None
    net_debt_to_free_cash_flow: Optional[float] = None

    # completed analysis
    data_complete: bool = True
    # Reserved for future required-field completeness rules.
    # data_complete = len(missing_fields) == 0
    missing_fields: tuple[str, ...] = field(default_factory=tuple)
    calculation_warnings: tuple[str, ...] = field(default_factory=tuple)
    not_applicable_fields: tuple[str, ...] = field(default_factory=tuple)
    field_explanations: tuple[tuple[str, str], ...] = field(
        default_factory=tuple
    )
