# Reveal application service and analytics-to-contract mapping.

from dataclasses import asdict, fields
import datetime as dt
import math

import pandas as pd

from mvp.models import (
    ComparableSecurity,
    ComparableSecurityCohort,
    FinancialMetricDistribution,
    HistoricalComparisonPeriod,
    HistoricalMetricComparison,
    HistoricalMetricObservation,
    MagicFormulaRankedSecurity,
    SecurityAnalysisResult,
    SecurityEligibilityAssessment,
)

from Securities_DB.db_connection import get_connection
from analytics.GrahamInvestorClasses import (
    DefensiveInvestorCriteriaValues as DICV,
    EnterprisingInvestorCriteriaValues as EICV,
    DefensiveInvestor,
    EnterprisingInvestor,
    defensive_min_revenue_for_sector,
)
from analytics.FinancialAssessment import FinancialAssessment as FA
from data_access.CompanyDetails import CompanyDetails
from data_access.SECFilingMetadata import annual_statement_availability_history
from data_access.PipelineETL import (
    has_defensive_history,
    has_enterprising_history,
    has_minimum_annual_history,
)


MINIMUM_ANALYSIS_MARKET_CAP = 250_000_000
SUPPORTED_US_EXCHANGES = {
    "AMEX",
    "BATS",
    "CBOE",
    "NASDAQ",
    "NYSE",
    "NYSE AMERICAN",
    "NYSE ARCA",
}
FINANCIAL_OR_INDUSTRIAL_SECTORS = {
    "FINANCE",
    "FINANCIAL SERVICES",
    "FINANCIALS",
    "INDUSTRIAL",
    "INDUSTRIALS",
}
UTILITY_SECTORS = {"UTILITY", "UTILITIES"}


def _normalize_cik_identifier(identifier: str) -> str:
    value = identifier.strip()
    if value.upper().startswith("CIK"):
        value = value[3:].lstrip(" #:.-")
    if not value.isdigit() or len(value) > 10:
        return ""
    return value.zfill(10)


def search_security_identifiers(
    query: str,
    limit: int = 8,
    *,
    search_provider=None,
) -> tuple[dict[str, str], ...]:
    """Return normalized SEC identifier matches for dashboard suggestions."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    normalized_query = " ".join(query.strip().split())
    if not normalized_query:
        return ()

    provider = search_provider or CompanyDetails().search_sec_tickers
    rows = provider(normalized_query, limit=limit)
    matches = []
    seen_tickers = set()
    for row in rows:
        record = dict(row)
        ticker = str(record.get("ticker") or "").strip().upper()
        if not ticker or ticker in seen_tickers:
            continue
        seen_tickers.add(ticker)
        cik = str(record.get("cik") or "").strip()
        if cik.isdigit() and len(cik) <= 10:
            cik = cik.zfill(10)
        matches.append(
            {
                "ticker": ticker,
                "cik": cik,
                "company_name": str(record.get("title") or "").strip(),
            }
        )
    return tuple(matches)


def resolve_security_identifier(
    identifier: str,
    *,
    search_provider=None,
) -> str:
    """Resolve a ticker, SEC company title, or CIK to one ticker symbol."""
    if not isinstance(identifier, str):
        raise TypeError("security identifier must be a string")
    normalized_identifier = " ".join(identifier.strip().split())
    if not normalized_identifier:
        raise ValueError("Enter a ticker, company name, or SEC CIK.")

    matches = search_security_identifiers(
        normalized_identifier,
        limit=25,
        search_provider=search_provider,
    )
    query_upper = normalized_identifier.upper()
    exact_ticker = [
        match for match in matches if match["ticker"] == query_upper
    ]
    if exact_ticker:
        return exact_ticker[0]["ticker"]

    exact_cik_value = _normalize_cik_identifier(normalized_identifier)
    exact_cik = [
        match
        for match in matches
        if exact_cik_value and match["cik"] == exact_cik_value
    ]
    if len(exact_cik) == 1:
        return exact_cik[0]["ticker"]
    if len(exact_cik) > 1:
        raise ValueError(
            "That SEC CIK maps to multiple securities. Choose a ticker from "
            "the suggestions."
        )

    exact_title = [
        match
        for match in matches
        if match["company_name"].upper() == query_upper
    ]
    if len(exact_title) == 1:
        return exact_title[0]["ticker"]
    if len(exact_title) > 1:
        raise ValueError(
            "That company name maps to multiple securities. Choose a ticker "
            "from the suggestions."
        )

    if len(matches) == 1:
        return matches[0]["ticker"]
    if not matches:
        raise ValueError(f'No security matched "{normalized_identifier}".')
    raise ValueError(
        f'"{normalized_identifier}" matched multiple securities. Choose a '
        "ticker from the suggestions."
    )


def _latest_magic_formula_rank_rows() -> tuple[dict, ...]:
    conn = get_connection(analysis="magic_formula", readonly=True)
    try:
        rows = conn.execute(
            """
            SELECT ticker, quarter_date, magic_formula_rank
            FROM magic_formula_quarterly_results
            WHERE quarter_date = (
                SELECT MAX(quarter_date)
                FROM magic_formula_quarterly_results
            )
            ORDER BY magic_formula_rank, ticker
            """
        ).fetchall()
        return tuple(dict(row) for row in rows)
    finally:
        conn.close()


def current_magic_formula_ranked_securities(
    *,
    rankings_provider=None,
    company_name_provider=None,
) -> tuple[MagicFormulaRankedSecurity, ...]:
    """Return the latest persisted Magic Formula ranking with company names."""
    provide_rankings = rankings_provider or _latest_magic_formula_rank_rows
    rows = tuple(provide_rankings())
    tickers = {
        str(row.get("ticker") or "").strip().upper()
        for row in rows
        if str(row.get("ticker") or "").strip()
    }
    provide_names = (
        company_name_provider or CompanyDetails().company_names_for_tickers
    )
    names = {
        str(ticker).strip().upper(): str(name).strip()
        for ticker, name in provide_names(tickers).items()
        if str(ticker).strip() and str(name).strip()
    }

    ranked_securities = []
    seen_tickers = set()
    for row in rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        quarter_date = str(row.get("quarter_date") or "").strip()
        rank = row.get("magic_formula_rank")
        if (
            not ticker
            or ticker in seen_tickers
            or not quarter_date
            or isinstance(rank, bool)
        ):
            continue
        try:
            normalized_rank = int(rank)
        except (TypeError, ValueError):
            continue
        if normalized_rank < 1:
            continue
        seen_tickers.add(ticker)
        ranked_securities.append(
            MagicFormulaRankedSecurity(
                rank=normalized_rank,
                ticker=ticker,
                company_name=names.get(ticker, "Company name unavailable"),
                quarter_date=quarter_date,
            )
        )
    return tuple(
        sorted(ranked_securities, key=lambda item: (item.rank, item.ticker))
    )


FINANCIAL_ASSESSMENT_MAP = {
    "ticker": "ticker",
    "company_name": "company_name",
    "company_description": "company_description",
    "analysis_date": "analysis_date",
    "price_date": "price_date",
    "annual_financial_statement_analysis_date": "annual_financial_statement_analysis_date",
    "quarter_financial_statement_analysis_date": "quarter_financial_statement_analysis_date",
    "market_price_for_period": "market_price_for_period",
    "min_200_day_price": "min_200_day_price",
    "max_200_day_price": "max_200_day_price",
    "avg_price_200_day": "avg_price_200_day",
    "median_price_200_day": "median_price_200_day",
    "market_cap": "market_cap",
    "market_cap_group": "market_cap_group",
    "sector": "sector",
    "industry": "industry",
    "eps": "eps",
    "eps_ttm": "eps_ttm",
    "net_income_ttm": "net_income_ttm",
    "ebit_ttm": "ebit_ttm",
    "total_sales_services": "total_sales_services",
    "price_to_earnings": "price_to_earnings",
    "gross_margin": "gross_margin",
    "free_cash_flow": "free_cash_flow",
    "free_cash_flow_margin": "free_cash_flow_margin",
    "estimated_owner_earnings": "estimated_owner_earnings",
    "estimated_owner_earnings_yield": "estimated_owner_earnings_yield",
    "operating_income": "operating_income",
    "inventory_turnover": "inventory_turnover",
    "financial_profile_return_on_capital": "financial_profile_return_on_capital",
    "return_on_capital": "return_on_capital",
    "earnings_yield": "earnings_yield",
    "magic_formula_quarter_date": "magic_formula_quarter_date",
    "magic_formula_associated_annual_date": "magic_formula_associated_annual_date",
    "magic_formula_financial_statement_availability_date": (
        "magic_formula_financial_statement_availability_date"
    ),
    "magic_formula_rank": "magic_formula_rank",
    "return_on_capital_rank": "return_on_capital_rank",
    "earnings_yield_rank": "earnings_yield_rank",
    "total_roc_ey_score": "total_roc_ey_score",
    "return_on_assets": "return_on_assets",
    "return_on_equity": "return_on_equity",
    "return_on_invested_capital": "return_on_invested_capital",
    "eps_cagr_5yr": "eps_cagr_5yr",
    "debt_to_assets": "debt_to_assets",
    "debt_to_equity": "debt_to_equity",
    "longterm_debt_to_cash": "longterm_debt_to_cash",
    "interest_coverage": "interest_coverage",
    "net_debt_to_free_cash_flow": "net_debt_to_free_cash_flow",
}

DEFENSIVE_GRAHAM_MAP = {
    "period_three_year_average_eps": "currentThreeYearAverageEPS",
    "current_assets_to_current_liabilities_ratio": "currentAssets200pctCurrentLiabilities",
    "long_term_debt_to_net_current_assets_ratio": "longTermDebtToNetCurrentAssets",
    "long_term_debt_to_book_equity_ratio": "longTermDebtToBookEquity",
    "eps_3yr_average_to_10yr_previous_eps_ratio": "eps3yrAverageTo10yrPreviousEPSRatio",
    "average_dividend_payments_for_past_20yrs": "averageDividendPayments20yr",
    "price_to_eps_3yr_average": "price15xEarningsPerShare3yrAverage",
    "price_to_book_value": "price150pctBookValue",
    "graham_number": "grahamNumber",
    "defensive_margin_of_safety": "defensiveMarginOfSafety",
}

ENTERPRISING_GRAHAM_MAP = {
    "period_three_year_average_eps": "currentThreeYearAverageEPS",
    "current_assets_150pct_or_greater_than_long_term_debt_ratio": "currentAssets150pctLongTermDebt",
    "long_term_debt_to_net_current_assets_ratio": "longTermDebtToNetCurrentAssets",
    "earnings_to_5yr_earnings_lookback_ratio": "earningsTo5yrLookbackRatio",
    "price_to_tangible_book_value": "price120pctTangibleBook",
    "tangible_book_value_per_share": "tangibleBookValuePerShare",
    "serenity_number": "serenityNumber",
    "enterprising_margin_of_safety": "enterprisingMarginOfSafety",
}

DEFENSIVE_CRITERIA_MAP = {
    "defensive_revenue_requirement_met": "totalSalesServicesGteMinimum",
    "current_assets_200pct_or_greater_current_liabilities_met": (
        "currentAssetsGte200pctCurrentLiabilities"
    ),
    "long_term_debt_less_than_net_current_assets_met": (
        "longTermDebtLessThanNetCurrentAssets"
    ),
    "utility_debt_to_book_equity_met": (
        "utilityDebtLte200pctBookEquity"
    ),
    "positive_earnings_for_the_past_10_years_met": "positiveEarnings10yr",
    "eps_3yr_average_33pct_gte_10yr_previous_eps_met": (
        "eps3yrAverageGte33pct10yrPreviousEPS"
    ),
    "continuous_dividend_payments_for_past_20yrs_met": (
        "continuousDividendPayments20yr"
    ),
    "price_15x_or_less_eps_3yr_average_met": "priceLte15xEPS",
    "price_150pct_or_less_book_value_met": "priceLte150pctBV",
}

ENTERPRISING_CRITERIA_MAP = {
    "current_assets_150pct_or_greater_long_term_debt_met": (
        "currentAssetsGte150pctLongTermDebt"
    ),
    "long_term_debt_110pct_or_less_to_net_current_assets_met": (
        "longTermDebtLte110pctNetCurrentAssets"
    ),
    "no_earnings_deficit_for_5yrs_met": "positiveEarnings5yr",
    "earnings_growth_greater_than_5yrs_previous_met": (
        "earningsGreaterThan5yrLookback"
    ),
    "price_120pct_or_less_tangible_book_met": "priceLte120pctTangibleAssets",
}

DEFENSIVE_WORKING_CAPITAL_FIELDS = {
    "current_assets_200pct_or_greater_current_liabilities_met",
    "current_assets_to_current_liabilities_ratio",
    "long_term_debt_less_than_net_current_assets_met",
}
DEFENSIVE_UTILITY_FIELDS = {
    "utility_debt_to_book_equity_met",
    "long_term_debt_to_book_equity_ratio",
}
MAGIC_FORMULA_FIELDS = {
    "return_on_capital",
    "earnings_yield",
    "magic_formula_quarter_date",
    "magic_formula_associated_annual_date",
    "magic_formula_financial_statement_availability_date",
    "magic_formula_rank",
    "return_on_capital_rank",
    "earnings_yield_rank",
    "total_roc_ey_score",
}

FINANCIAL_PROFILE_FIELDS = (
    "return_on_invested_capital",
    "financial_profile_return_on_capital",
    "free_cash_flow_margin",
    "estimated_owner_earnings_yield",
    "debt_to_assets",
    "net_debt_to_free_cash_flow",
    "eps_cagr_5yr",
)
ADDITIONAL_OVERVIEW_FIELDS = (
    "gross_margin",
    "free_cash_flow",
    "estimated_owner_earnings",
    "operating_income",
    "inventory_turnover",
    "return_on_assets",
    "return_on_equity",
    "debt_to_equity",
    "longterm_debt_to_cash",
    "interest_coverage",
)
DESCRIPTIVE_METRIC_FIELDS = FINANCIAL_PROFILE_FIELDS + ADDITIONAL_OVERVIEW_FIELDS
MINIMUM_DISTRIBUTION_SAMPLE = 5
HISTORICAL_COMPARISON_PERIODS = (1, 3, 5, 7, 10)
HISTORICAL_EOEY_FIELD = "estimated_owner_earnings_yield"


def _company_details(ticker: str) -> dict:
    return CompanyDetails(ticker).get_details()


def _market_cap_group(market_cap: float | None) -> str | None:
    """Return the market-cap grouping used by FinancialAssessment."""
    if market_cap is None or not math.isfinite(market_cap):
        return None
    if market_cap >= 2e11:
        return "Mega"
    if market_cap >= 1e10:
        return "Large"
    if market_cap >= 2e9:
        return "Mid"
    if market_cap >= 25e7:
        return "Small"
    if market_cap >= 1e8:
        return "Micro"
    return "Nano"


def _finite_metric_value(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _normalize_peer_universe(universe: pd.DataFrame) -> pd.DataFrame:
    """Return locally eligible common-stock peer candidates."""
    required = (
        "Symbol",
        "Name",
        "AssetType",
        "Exchange",
        "MarketCapitalization",
        "Sector",
        "Industry",
    )
    if universe is None or universe.empty:
        return pd.DataFrame(columns=required)

    normalized = universe.copy()
    for column in required:
        if column not in normalized.columns:
            normalized[column] = None

    normalized["Symbol"] = (
        normalized["Symbol"].fillna("").astype(str).str.strip().str.upper()
    )
    normalized["AssetType"] = (
        normalized["AssetType"].fillna("").astype(str).str.strip().str.upper()
    )
    normalized["Exchange"] = (
        normalized["Exchange"].fillna("").astype(str).str.strip().str.upper()
    )
    normalized["Name"] = normalized["Name"].fillna("").astype(str)
    normalized["Sector"] = (
        normalized["Sector"].fillna("").astype(str).str.strip().str.upper()
    )
    normalized["Industry"] = (
        normalized["Industry"].fillna("").astype(str).str.strip().str.upper()
    )
    normalized["MarketCapitalization"] = pd.to_numeric(
        normalized["MarketCapitalization"],
        errors="coerce",
    )

    unsupported_name = normalized["Name"].str.upper().str.contains(
        r"WARRANT|PREFERRED",
        regex=True,
    )
    normalized = normalized[
        normalized["Symbol"].ne("")
        & normalized["AssetType"].eq("COMMON STOCK")
        & normalized["Exchange"].isin(SUPPORTED_US_EXCHANGES)
        & normalized["MarketCapitalization"].ge(
            MINIMUM_ANALYSIS_MARKET_CAP
        )
        & ~unsupported_name
    ].copy()
    normalized["_market_cap_group"] = normalized[
        "MarketCapitalization"
    ].map(_market_cap_group)
    return normalized.drop_duplicates("Symbol", keep="first")


def _peer_comparison_tiers(
    universe: pd.DataFrame,
    result: SecurityAnalysisResult,
    *,
    deduplicate_membership: bool = True,
) -> list[tuple[str, str, tuple[str, ...]]]:
    """Build narrow-to-broad peer cohorts from documented policy."""
    ticker = result.ticker.upper()
    sector = str(result.sector or "").strip().upper()
    industry = str(result.industry or "").strip().upper()
    cap_group = str(result.market_cap_group or "").strip().title()
    tiers = []

    def add_tier(basis: str, label: str, mask) -> None:
        tickers = set(universe.loc[mask, "Symbol"].tolist())
        tickers.add(ticker)
        normalized_tickers = tuple(sorted(tickers))
        if not normalized_tickers:
            return
        if deduplicate_membership and any(
            existing[2] == normalized_tickers for existing in tiers
        ):
            return
        tiers.append((basis, label, normalized_tickers))

    if industry and cap_group:
        add_tier(
            "Industry + market cap",
            f"{industry.title()} / {cap_group}",
            universe["Industry"].eq(industry)
            & universe["_market_cap_group"].eq(cap_group),
        )
    if industry:
        add_tier(
            "Industry",
            industry.title(),
            universe["Industry"].eq(industry),
        )
    if sector and cap_group:
        add_tier(
            "Sector + market cap",
            f"{sector.title()} / {cap_group}",
            universe["Sector"].eq(sector)
            & universe["_market_cap_group"].eq(cap_group),
        )
    if sector:
        add_tier(
            "Sector",
            sector.title(),
            universe["Sector"].eq(sector),
        )
    add_tier(
        "Eligible market",
        "Eligible U.S. common stocks",
        pd.Series(True, index=universe.index),
    )
    return tiers


def comparable_security_cohort(
    result: SecurityAnalysisResult,
    comparison_basis: str | None = None,
    *,
    universe_provider=None,
) -> ComparableSecurityCohort:
    """Return current peer membership from persisted company metadata.

    When ``comparison_basis`` is omitted, the narrowest metadata cohort with
    at least five eligible members is returned. Pass a
    ``FinancialMetricDistribution`` object's ``comparison_basis`` to retrieve
    the exact membership behind that metric's current distribution without
    running financial analysis for the members.
    """
    if not isinstance(result, SecurityAnalysisResult):
        raise TypeError("result must be a SecurityAnalysisResult")
    if comparison_basis is not None:
        if not isinstance(comparison_basis, str) or not comparison_basis.strip():
            raise ValueError("comparison_basis must be a non-empty string")
        requested_basis = comparison_basis.strip().casefold()
    else:
        requested_basis = None

    if universe_provider is None:
        universe_provider = CompanyDetails().get_peer_metadata
    universe = _normalize_peer_universe(universe_provider())
    tiers = _peer_comparison_tiers(
        universe,
        result,
        deduplicate_membership=False,
    )

    if requested_basis is None:
        selected_tier = next(
            (
                tier
                for tier in tiers
                if len(tier[2]) >= MINIMUM_DISTRIBUTION_SAMPLE
            ),
            tiers[-1] if tiers else None,
        )
    else:
        selected_tier = next(
            (
                tier
                for tier in tiers
                if tier[0].casefold() == requested_basis
            ),
            None,
        )
    if selected_tier is None:
        available = ", ".join(tier[0] for tier in tiers)
        raise ValueError(
            "comparison_basis must be one of the available cohorts: "
            f"{available or 'none'}"
        )

    comparison_basis, comparison_group, tickers = selected_tier
    metadata = {
        row["Symbol"]: row
        for _, row in universe.iterrows()
    }
    selected_ticker = result.ticker.strip().upper()
    members = []
    for ticker in tickers:
        row = metadata.get(ticker)
        if row is None and ticker != selected_ticker:
            continue
        company_name = (
            str(row["Name"]).strip()
            if row is not None
            else str(result.company_name or "").strip()
        )
        industry = (
            str(row["Industry"]).strip().title()
            if row is not None and str(row["Industry"]).strip()
            else result.industry
            if ticker == selected_ticker
            else None
        )
        sector = (
            str(row["Sector"]).strip().title()
            if row is not None and str(row["Sector"]).strip()
            else result.sector
            if ticker == selected_ticker
            else None
        )
        market_cap_group = (
            row["_market_cap_group"]
            if row is not None
            else result.market_cap_group
            if ticker == selected_ticker
            else None
        )
        members.append(
            ComparableSecurity(
                ticker=ticker,
                company_name=company_name,
                industry=industry,
                sector=sector,
                market_cap_group=market_cap_group,
            )
        )

    return ComparableSecurityCohort(
        selected_ticker=selected_ticker,
        comparison_basis=comparison_basis,
        comparison_group=comparison_group,
        members=tuple(members),
    )


def _summarize_metric_distribution(
    *,
    metric: str,
    comparison_basis: str,
    comparison_group: str,
    candidate_count: int,
    values: list[float],
    selected_value: float | None,
) -> FinancialMetricDistribution:
    series = pd.Series(values, dtype="float64").sort_values(
        ignore_index=True
    )
    quantiles = series.quantile([0.10, 0.25, 0.50, 0.75, 0.90])
    percentile = None
    if selected_value is not None:
        less = int(series.lt(selected_value).sum())
        equal = int(series.eq(selected_value).sum())
        percentile = 100 * (less + 0.5 * equal) / len(series)

    return FinancialMetricDistribution(
        metric=metric,
        comparison_basis=comparison_basis,
        comparison_group=comparison_group,
        sample_size=len(series),
        candidate_count=candidate_count,
        values=tuple(float(value) for value in series),
        selected_value=selected_value,
        percentile=percentile,
        p10=float(quantiles.loc[0.10]),
        p25=float(quantiles.loc[0.25]),
        median=float(quantiles.loc[0.50]),
        mean=float(series.mean()),
        p75=float(quantiles.loc[0.75]),
        p90=float(quantiles.loc[0.90]),
    )


def financial_profile_distributions(
    result: SecurityAnalysisResult,
    *,
    universe_provider=None,
    metric_provider=None,
    minimum_sample: int = MINIMUM_DISTRIBUTION_SAMPLE,
    metric_fields: tuple[str, ...] = FINANCIAL_PROFILE_FIELDS,
) -> tuple[FinancialMetricDistribution, ...]:
    """Build current peer distributions for requested descriptive metrics.

    Each metric uses the narrowest documented peer cohort with at least
    ``minimum_sample`` finite observations. Metric values continue to come
    from ``FinancialAssessment.to_dict()`` through the default provider.
    """
    if minimum_sample < 2:
        raise ValueError("minimum_sample must be at least 2")
    if not metric_fields or set(metric_fields) - set(DESCRIPTIVE_METRIC_FIELDS):
        raise ValueError("metric_fields must contain supported descriptive fields")
    if universe_provider is None:
        universe_provider = CompanyDetails().get_peer_metadata
    if metric_provider is None:
        def metric_provider(ticker, analysis_date):
            return FA(ticker, date=analysis_date).to_dict()

    universe = _normalize_peer_universe(universe_provider())
    tiers = _peer_comparison_tiers(universe, result)
    if not tiers:
        return ()

    analysis_date = (
        result.analysis_date.isoformat()
        if hasattr(result.analysis_date, "isoformat")
        else str(result.analysis_date)
    )
    selected_ticker = result.ticker.upper()
    metric_cache = {
        selected_ticker: {
            metric: getattr(result, metric)
            for metric in metric_fields
        }
    }
    unresolved = set(metric_fields)
    summaries: dict[str, FinancialMetricDistribution] = {}

    for comparison_basis, comparison_group, tickers in tiers:
        for ticker in tickers:
            if ticker in metric_cache:
                continue
            try:
                provided = metric_provider(ticker, analysis_date) or {}
                metric_cache[ticker] = (
                    asdict(provided)
                    if isinstance(provided, SecurityAnalysisResult)
                    else dict(provided)
                )
            except Exception:
                metric_cache[ticker] = {}

        for metric in tuple(unresolved):
            values = [
                value
                for ticker in tickers
                if (
                    value := _finite_metric_value(
                        metric_cache[ticker].get(metric)
                    )
                )
                is not None
            ]
            if len(values) < minimum_sample:
                continue
            selected_value = _finite_metric_value(getattr(result, metric))
            summaries[metric] = _summarize_metric_distribution(
                metric=metric,
                comparison_basis=comparison_basis,
                comparison_group=comparison_group,
                candidate_count=len(tickers),
                values=values,
                selected_value=selected_value,
            )
            unresolved.remove(metric)

        if not unresolved:
            break

    return tuple(
        summaries[metric]
        for metric in metric_fields
        if metric in summaries
    )


def _historical_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError("analysis_date must be a valid ISO date") from exc


def _default_annual_availability_provider(
    ticker: str,
    analysis_date: str,
) -> list[dict]:
    conn = get_connection(readonly=True)
    try:
        return annual_statement_availability_history(
            conn,
            ticker=ticker,
            analysis_date=analysis_date,
        )
    finally:
        conn.close()


def _default_historical_metric_provider(
    ticker: str,
    annual_statement_date: str,
    statement_availability_date: str,
) -> dict:
    return FA(
        ticker,
        date=annual_statement_date,
        market_price_date=statement_availability_date,
    ).to_dict()


def _historical_metric_records(
    *,
    ticker: str,
    metric: str,
    analysis_date: dt.date,
    availability_provider,
    metric_provider,
) -> list[dict]:
    available = availability_provider(ticker, analysis_date.isoformat()) or ()
    normalized = []
    seen_dates = set()
    for raw_record in available:
        record = dict(raw_record)
        try:
            fiscal_date = _historical_date(
                record["annual_statement_date"]
            )
            availability_date = _historical_date(
                record["statement_availability_date"]
            )
        except (KeyError, TypeError, ValueError):
            continue
        if (
            fiscal_date in seen_dates
            or fiscal_date > analysis_date
            or availability_date > analysis_date
            or availability_date < fiscal_date
        ):
            continue
        seen_dates.add(fiscal_date)
        normalized.append((fiscal_date, availability_date))
    normalized.sort(reverse=True)

    history = []
    prior_fiscal_year = None
    seen_fiscal_years = set()
    for fiscal_date, availability_date in normalized:
        fiscal_year = fiscal_date.year
        if fiscal_year in seen_fiscal_years:
            continue
        seen_fiscal_years.add(fiscal_year)
        if (
            prior_fiscal_year is not None
            and prior_fiscal_year - fiscal_year != 1
        ):
            break
        try:
            provided = metric_provider(
                ticker,
                fiscal_date.isoformat(),
                availability_date.isoformat(),
            ) or {}
            values = (
                asdict(provided)
                if isinstance(provided, SecurityAnalysisResult)
                else dict(provided)
            )
        except Exception:
            values = {}

        selected_statement_date = values.get(
            "annual_financial_statement_analysis_date"
        )
        value = _finite_metric_value(values.get(metric))
        price_date = None
        valid = selected_statement_date == fiscal_date.isoformat()
        if metric == HISTORICAL_EOEY_FIELD:
            try:
                selected_price_date = _historical_date(values.get("price_date"))
            except ValueError:
                valid = False
            else:
                valid = valid and selected_price_date <= availability_date
                price_date = selected_price_date.isoformat()
        if not valid or value is None:
            if history:
                break
            continue

        history.append({
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "annual_statement_date": fiscal_date.isoformat(),
            "statement_availability_date": availability_date.isoformat(),
            "price_date": price_date,
            "value": value,
        })
        prior_fiscal_year = fiscal_year
    return history


def _available_historical_periods(
    history_length: int,
) -> tuple[HistoricalComparisonPeriod, ...]:
    if history_length < 1:
        return ()
    numeric = tuple(
        period
        for period in HISTORICAL_COMPARISON_PERIODS
        if period <= history_length
    )
    return (*numeric, "all")


def _applied_historical_period(
    requested_period: HistoricalComparisonPeriod,
    history_length: int,
) -> int:
    if history_length < 1:
        return 0
    if requested_period == "all":
        return history_length
    if history_length >= requested_period:
        return requested_period
    return max(
        period
        for period in HISTORICAL_COMPARISON_PERIODS
        if period <= history_length and period < requested_period
    )


def historical_financial_profile_comparison(
    result: SecurityAnalysisResult,
    metric: str,
    requested_period: HistoricalComparisonPeriod = 5,
    peer_ticker: str | None = None,
    *,
    availability_provider=None,
    metric_provider=None,
) -> HistoricalMetricComparison:
    """Build availability-aware annual history for one profile metric."""
    if not isinstance(result, SecurityAnalysisResult):
        raise TypeError("result must be a SecurityAnalysisResult")
    if metric not in FINANCIAL_PROFILE_FIELDS:
        raise ValueError("metric must be one of the Financial Profile fields")
    if isinstance(requested_period, bool) or requested_period not in (
        *HISTORICAL_COMPARISON_PERIODS,
        "all",
    ):
        raise ValueError("requested_period must be 1, 3, 5, 7, 10, or 'all'")

    selected_ticker = result.ticker.strip().upper()
    normalized_peer = (
        peer_ticker.strip().upper()
        if isinstance(peer_ticker, str) and peer_ticker.strip()
        else None
    )
    if normalized_peer == selected_ticker:
        normalized_peer = None
    analysis_date = _historical_date(result.analysis_date)
    availability_provider = (
        availability_provider or _default_annual_availability_provider
    )
    metric_provider = metric_provider or _default_historical_metric_provider

    selected_history = _historical_metric_records(
        ticker=selected_ticker,
        metric=metric,
        analysis_date=analysis_date,
        availability_provider=availability_provider,
        metric_provider=metric_provider,
    )
    peer_history = []
    if normalized_peer is not None:
        peer_history = _historical_metric_records(
            ticker=normalized_peer,
            metric=metric,
            analysis_date=analysis_date,
            availability_provider=availability_provider,
            metric_provider=metric_provider,
        )

    has_comparable_peer = normalized_peer is not None and bool(peer_history)
    comparable_length = (
        min(len(selected_history), len(peer_history))
        if has_comparable_peer
        else len(selected_history)
    )
    available_periods = _available_historical_periods(comparable_length)
    applied_period = _applied_historical_period(
        requested_period,
        comparable_length,
    )

    limiting_tickers = []
    if requested_period == "all":
        if has_comparable_peer and len(selected_history) != len(peer_history):
            limiting_length = min(len(selected_history), len(peer_history))
            if len(selected_history) == limiting_length:
                limiting_tickers.append(selected_ticker)
            if len(peer_history) == limiting_length:
                limiting_tickers.append(normalized_peer)
        elif normalized_peer is not None and not peer_history:
            limiting_tickers.append(normalized_peer)
    else:
        if len(selected_history) < requested_period:
            limiting_tickers.append(selected_ticker)
        if normalized_peer is not None and len(peer_history) < requested_period:
            limiting_tickers.append(normalized_peer)

    observations = []
    selected_window = selected_history[:applied_period]
    peer_window = peer_history[:applied_period] if has_comparable_peer else []
    max_offset_days = 0
    for index in reversed(range(applied_period)):
        selected_record = selected_window[index]
        anchor_year = selected_record["fiscal_year"]
        observations.append(HistoricalMetricObservation(
            **selected_record,
            anchor_fiscal_year=anchor_year,
        ))
        if peer_window:
            peer_record = peer_window[index]
            observations.append(HistoricalMetricObservation(
                **peer_record,
                anchor_fiscal_year=anchor_year,
            ))
            offset = abs((
                _historical_date(selected_record["annual_statement_date"])
                - _historical_date(peer_record["annual_statement_date"])
            ).days)
            max_offset_days = max(max_offset_days, offset)

    warnings = []
    if limiting_tickers:
        warnings.append("limited_history")
    if normalized_peer is not None and not peer_history:
        warnings.append("no_comparable_history")
    if max_offset_days > 183:
        warnings.append("fiscal_period_offset")

    anchor_years = tuple(
        record["fiscal_year"] for record in reversed(selected_window)
    )
    return HistoricalMetricComparison(
        metric=metric,
        analysis_date=analysis_date,
        requested_period=requested_period,
        applied_period=applied_period,
        available_periods=available_periods,
        selected_ticker=selected_ticker,
        peer_ticker=normalized_peer,
        anchor_fiscal_years=anchor_years,
        series=tuple(observations),
        limiting_tickers=tuple(limiting_tickers),
        max_fiscal_period_offset_days=max_offset_days,
        warning_codes=tuple(warnings),
    )


def assess_security_eligibility(
    ticker: str,
    *,
    details_provider=None,
    history_checker=None,
) -> SecurityEligibilityAssessment:
    """Evaluate the documented Reveal v1 common-stock entry criteria."""
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("ticker must be a non-empty string")

    ticker = ticker.strip().upper()
    if details_provider is None:
        details_provider = _company_details
    if history_checker is None:
        history_checker = has_minimum_annual_history

    details = details_provider(ticker) or {}
    if not details:
        return SecurityEligibilityAssessment(
            ticker=ticker,
            eligible=False,
            reasons=(f"{ticker} was not found in the local security database.",),
        )

    company_name = str(details.get("Name") or "")
    asset_type = details.get("AssetType")
    exchange = details.get("Exchange")
    reasons = []

    normalized_asset_type = str(asset_type or "").strip().upper()
    normalized_name = company_name.upper()
    excluded_name = "WARRANT" in normalized_name or "PREFERRED" in normalized_name
    if normalized_asset_type != "COMMON STOCK" or excluded_name:
        displayed_type = asset_type or "an unsupported security type"
        reasons.append(
            f"{ticker} is classified as {displayed_type}, not eligible common stock."
        )

    normalized_exchange = str(exchange or "").strip().upper()
    if normalized_exchange not in SUPPORTED_US_EXCHANGES:
        displayed_exchange = exchange or "an unknown exchange"
        reasons.append(
            f"{ticker} is listed on {displayed_exchange}, not a supported major "
            "U.S. exchange."
        )

    raw_market_cap = details.get("MarketCapitalization")
    market_cap = pd.to_numeric(raw_market_cap, errors="coerce")
    market_cap = None if pd.isna(market_cap) else float(market_cap)
    if market_cap is None:
        reasons.append(f"{ticker} has no usable market-capitalization value.")
    elif market_cap < MINIMUM_ANALYSIS_MARKET_CAP:
        reasons.append(
            f"{ticker} has a market capitalization below the $250 million "
            "minimum."
        )

    try:
        has_history = bool(history_checker(ticker, 5))
    except (KeyError, TypeError, ValueError):
        has_history = False
    if not has_history:
        reasons.append(
            f"{ticker} does not have the required five years of financial "
            "and market-price history."
        )

    return SecurityEligibilityAssessment(
        ticker=ticker,
        eligible=not reasons,
        company_name=company_name,
        asset_type=str(asset_type) if asset_type is not None else None,
        exchange=str(exchange) if exchange is not None else None,
        market_cap=market_cap,
        reasons=tuple(reasons),
    )


# helper function to simplify mapping
def apply_map(target: dict, source: dict, field_map: dict) -> None:
    for result_field, source_key in field_map.items():
        if source_key in source:
            target[result_field] = _normalize_contract_value(source[source_key])


def _normalize_contract_value(value):
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def _criteria_at_date(criteria: pd.DataFrame, analysis_date: str | None) -> dict:
    if criteria.empty or "fiscalDateEnding" not in criteria.columns:
        return {}

    criteria = criteria.copy()
    criteria["fiscalDateEnding"] = pd.to_datetime(
        criteria["fiscalDateEnding"], errors="coerce"
    )
    cutoff = pd.to_datetime(analysis_date or dt.date.today())
    available = criteria[
        criteria["fiscalDateEnding"].notna()
        & (criteria["fiscalDateEnding"] <= cutoff)
    ].sort_values("fiscalDateEnding", ascending=False)
    if available.empty:
        return {}
    return available.iloc[0].drop(labels=["fiscalDateEnding"]).to_dict()


def _applicability_metadata(
    result_data: dict,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    sector = str(result_data.get("sector") or "").strip().upper()
    not_applicable = set()
    explanations = {}

    if sector in FINANCIAL_OR_INDUSTRIAL_SECTORS:
        fields = DEFENSIVE_UTILITY_FIELDS
        reason = (
            "The Utility debt-to-book-equity test does not apply to this "
            "sector."
        )
    elif sector in UTILITY_SECTORS:
        fields = DEFENSIVE_WORKING_CAPITAL_FIELDS
        reason = (
            "Utilities use the debt-to-book-equity test instead of the "
            "Industrial/Financial working-capital tests."
        )
    else:
        fields = DEFENSIVE_WORKING_CAPITAL_FIELDS | DEFENSIVE_UTILITY_FIELDS
        reason = (
            "This sector does not use the sector-specific Defensive liquidity "
            "or Utility leverage tests."
        )
    not_applicable.update(fields)
    explanations.update({field: reason for field in fields})

    magic_formula_excluded_sectors = UTILITY_SECTORS | {
        "FINANCE",
        "FINANCIAL SERVICES",
        "FINANCIALS",
    }
    if sector in magic_formula_excluded_sectors:
        reason = (
            "Magic Formula ranking excludes Utilities and Financial companies "
            "under the documented methodology."
        )
        not_applicable.update(MAGIC_FORMULA_FIELDS)
        explanations.update({field: reason for field in MAGIC_FORMULA_FIELDS})

    return (
        tuple(sorted(not_applicable)),
        tuple(sorted(explanations.items())),
    )


def _criteria_summary(
    result_data: dict,
    criterion_fields,
    not_applicable_fields=(),
) -> bool | None:
    excluded = set(not_applicable_fields)
    values = [
        result_data.get(field)
        for field in criterion_fields
        if field not in excluded
    ]
    if any(value is False for value in values):
        return False
    if not values or any(value is None for value in values):
        return None
    return all(values)


#
def build_security_analysis_result(
    financial_metrics: dict,
    defensive_values: dict,
    enterprising_values: dict,
    defensive_criteria: dict | None = None,
    enterprising_criteria: dict | None = None,
    calculation_warnings: tuple[str, ...] = (),
) -> SecurityAnalysisResult:
    result_data = {}

    apply_map(result_data, financial_metrics, FINANCIAL_ASSESSMENT_MAP)
    apply_map(result_data, defensive_values, DEFENSIVE_GRAHAM_MAP)
    apply_map(result_data, enterprising_values, ENTERPRISING_GRAHAM_MAP)
    apply_map(result_data, defensive_criteria or {}, DEFENSIVE_CRITERIA_MAP)
    apply_map(result_data, enterprising_criteria or {}, ENTERPRISING_CRITERIA_MAP)

    not_applicable_fields, field_explanations = _applicability_metadata(
        result_data
    )
    result_data["not_applicable_fields"] = not_applicable_fields
    result_data["field_explanations"] = field_explanations

    result_data["defensive_criteria_met"] = _criteria_summary(
        result_data,
        DEFENSIVE_CRITERIA_MAP,
        not_applicable_fields,
    )
    result_data["enterprising_criteria_met"] = _criteria_summary(
        result_data, ENTERPRISING_CRITERIA_MAP
    )

    analysis_date = result_data.get("analysis_date")
    if isinstance(analysis_date, str):
        result_data["analysis_date"] = pd.to_datetime(analysis_date).date()
    elif analysis_date is None:
        result_data["analysis_date"] = dt.date.today()

    valid_fields = {field.name for field in fields(SecurityAnalysisResult)}
    result_data = {
        key: value
        for key, value in result_data.items()
        if key in valid_fields
    }

    required_fields = ("ticker", "company_name", "analysis_date")
    missing_fields = tuple(
        field for field in required_fields
        if result_data.get(field) in (None, "")
    )

    calculation_warnings = tuple(calculation_warnings)
    result_data.setdefault("ticker", "")
    result_data.setdefault("company_name", "")
    result_data.setdefault("analysis_date", dt.date.today())
    result_data["missing_fields"] = missing_fields
    result_data["calculation_warnings"] = calculation_warnings
    result_data["data_complete"] = (
        len(missing_fields) == 0 and len(calculation_warnings) == 0
    )

    return SecurityAnalysisResult(**result_data)


def analyze_security(ticker: str, analysis_date: str | None = None) -> SecurityAnalysisResult:
    """
    Analyze a security and return the available Reveal metrics.

    Financial assessment metrics are always attempted. Graham Defensive and
    Enterprising values are added only when the ticker has enough supporting
    history; skipped sections are recorded in calculation_warnings.
    """
    warnings = []

    financial_metrics = FA(ticker, date=analysis_date).to_dict()

    defensive_values = {}
    defensive_criteria = {}
    if has_defensive_history(ticker):
        defensive_analyzer = DICV(ticker)
        defensive_values = defensive_analyzer.get_by_date(analysis_date)
        minimum_revenue = defensive_min_revenue_for_sector(
            financial_metrics.get("sector")
        )
        defensive_criteria = _criteria_at_date(
            DefensiveInvestor.from_values(
                defensive_analyzer
            ).criteria_dataframe(minimum_revenue=minimum_revenue),
            analysis_date,
        )
    else:
        warnings.append("Insufficient data for Defensive Graham analysis")

    enterprising_values = {}
    enterprising_criteria = {}
    if has_enterprising_history(ticker):
        enterprising_analyzer = EICV(ticker)
        enterprising_values = enterprising_analyzer.get_by_date(analysis_date)
        enterprising_criteria = _criteria_at_date(
            EnterprisingInvestor.from_values(
                enterprising_analyzer
            ).criteria_dataframe(),
            analysis_date,
        )
    else:
        warnings.append("Insufficient data for Enterprising Graham analysis")

    result = build_security_analysis_result(
        financial_metrics,
        defensive_values,
        enterprising_values,
        defensive_criteria=defensive_criteria,
        enterprising_criteria=enterprising_criteria,
        calculation_warnings=tuple(warnings),
    )

    return result


def eligible_common_stock_tickers(years: int = 10) -> list[str]:
    conn = get_connection(readonly=True)
    try:
        tickers = pd.read_sql_query(
            """
            SELECT Symbol
            FROM company_details
            WHERE AssetType = 'Common Stock'
              AND UPPER(COALESCE(Name, '')) NOT LIKE '% PREFERRED%'
              AND UPPER(COALESCE(Name, '')) NOT LIKE '% WARRANT%'
            ORDER BY Symbol
            """,
            conn,
        )["Symbol"].dropna().tolist()
    finally:
        conn.close()

    eligible_tickers = [
        ticker for ticker in tickers if has_minimum_annual_history(ticker, years)
    ]

    return eligible_tickers

def display_security_analysis(
        ticker: str,
        analysis_date: None | str = None,
        investor_type: None | str = None
) -> None:
    """
    takes the Security Analysis for a given ticker and prints it to the console;
    ticker and investor_type are not case-sensitive;
    investor_type is either None, defensive, or enterprising;
    date should be of string form YYYY-MM-DD

    :param ticker:
    :param analysis_date:
    :param investor_type:
    :return:
    """
    if not ticker or not isinstance(ticker, str):
        raise ValueError("ticker must be a string")
    if investor_type and investor_type.lower() not in ('defensive', 'enterprising', None):
        raise ValueError("investor_type must be None, defensive, or enterprising")
    if analysis_date and not isinstance(analysis_date, str):
        raise ValueError("analysis_date must be a string")
    elif analysis_date:
        split_d = analysis_date.split('-')
        if len(split_d) < 3 or not all((split_d[0].isnumeric(),split_d[1].isnumeric(),split_d[2].isnumeric())):
            raise ValueError("analysis_date must be of string form YYYY-MM-DD")
    ticker = ticker if ticker.isupper() else ticker.upper()
    investor_type = investor_type.lower() if investor_type else None

    analysis = analyze_security(ticker, analysis_date=analysis_date)
    header = (
        f"Security Analysis for {ticker} as of "
        f"{analysis_date or dt.date.today().strftime('%Y-%m-%d')}"
    )
    print(
        f"{header:^s}",
        "\n",f"{'_'*90:^s}",
        f"\n\t{analysis.company_name} :\tMarket Price for {analysis.analysis_date} :\t${analysis.market_price_for_period}"
    )
    for key in FINANCIAL_ASSESSMENT_MAP.keys():
        split_key = key.split("_")
        title_key = " ".join(k.title() for k in split_key)
        if key not in ('ticker','analysis_date','market_price_for_period','company_name'):
            analyzed_key = analysis.__getattribute__(key)
            if isinstance(analyzed_key, str):
                ak = analyzed_key.split()
                if len(ak) == 2:
                    if all([ak[0].isnumeric(), ak[1].isnumeric()]):
                        analyzed_key = ''.join((ak[0], '.', ak[1][:2]))
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key, (float, int)):
                if isinstance(analyzed_key, int):
                    analyzed_key = f"{analyzed_key:,d}"
                else:
                    analyzed_key = f"{analyzed_key:,.2f}"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key, bool):
                if analyzed_key:
                    analyzed_key = "True"
                else:
                    analyzed_key = "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key is None:
                analyzed_key = "None"
            elif analyzed_key == "0" or analyzed_key == "1":
                ak = {"0": True, "1": False}
                analyzed_key = "True" if ak.get(analyzed_key) else "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            else:
                analyzed_key = str(analyzed_key)
                print(f"{title_key:>60s}  :\t{analyzed_key}")

    if investor_type is None:
        print(
            "\nFinancial Assessment using Ben Graham's metrics for both Defensive and Enterprising investors:",
            "\n----------------------------------------------------------------------------------------------",
        )
        for key in ENTERPRISING_GRAHAM_MAP.keys():
            split_key = key.split("_")
            title_key = " ".join(k.title() for k in split_key)
            analyzed_key = analysis.__getattribute__(key)
            if isinstance(analyzed_key,str):
                ak = analyzed_key.split()
                if len(ak) == 2:
                    if all([ak[0].isnumeric(),ak[1].isnumeric()]):
                        analyzed_key = ''.join((ak[0],'.',ak[1][:2]))
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key,(float,int)):
                if isinstance(analyzed_key,int):
                    analyzed_key = f"{analyzed_key:,d}"
                else:
                    analyzed_key = f"{analyzed_key:,.2f}"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key, bool):
                if analyzed_key:
                    analyzed_key = "True"
                else:
                    analyzed_key = "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key is None:
                analyzed_key = "None"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key == "0" or analyzed_key == "1":
                ak = {"0": True, "1": False}
                analyzed_key = "True" if ak.get(analyzed_key) else "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            else:
                analyzed_key = str(analyzed_key)
                print(f"{title_key:>60s}  :\t{analyzed_key}")

        for key in DEFENSIVE_GRAHAM_MAP.keys():
            split_key = key.split("_")
            title_key = " ".join(k.title() for k in split_key)
            analyzed_key = analysis.__getattribute__(key)
            if isinstance(analyzed_key,str):
                ak = analyzed_key.split()
                if len(ak) == 2:
                    if all([ak[0].isnumeric(),ak[1].isnumeric()]):
                        analyzed_key = ''.join((ak[0],'.',ak[1][:2]))
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key,(float,int)):
                if isinstance(analyzed_key,int):
                    analyzed_key = f"{analyzed_key:,d}"
                else:
                    analyzed_key = f"{analyzed_key:,.2f}"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key, bool):
                if analyzed_key:
                    analyzed_key = "True"
                else:
                    analyzed_key = "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key is None:
                analyzed_key = "None"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key == "0" or analyzed_key == "1":
                ak = {"0": True, "1": False}
                analyzed_key = "True" if ak.get(analyzed_key) else "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            else:
                analyzed_key = str(analyzed_key)
                print(f"{title_key:>60s}  :\t{analyzed_key}")

        for key in (*DEFENSIVE_CRITERIA_MAP, *ENTERPRISING_CRITERIA_MAP):
            title_key = " ".join(part.title() for part in key.split("_"))
            analyzed_key = analysis.__getattribute__(key)
            if isinstance(analyzed_key,str):
                ak = analyzed_key.split()
                if len(ak) == 2:
                    if all([ak[0].isnumeric(),ak[1].isnumeric()]):
                        analyzed_key = ''.join((ak[0],'.',ak[1][:2]))
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key,(float,int)):
                if isinstance(analyzed_key,int):
                    analyzed_key = f"{analyzed_key:,d}"
                else:
                    analyzed_key = f"{analyzed_key:,.2f}"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key, bool):
                if analyzed_key:
                    analyzed_key = "True"
                else:
                    analyzed_key = "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key is None:
                analyzed_key = "None"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key == "0" or  analyzed_key == "1":
                ak = {"0":True, "1":False}
                analyzed_key = "True" if ak.get(analyzed_key) else "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            else:
                analyzed_key = str(analyzed_key)
                print(f"{title_key:>60s}  :\t{analyzed_key}")

    elif investor_type == 'enterprising':
        print(
            "\nFinancial Assessment using Ben Graham's metrics for the Enterprising investor:",
            "\n------------------------------------------------------------------------------"
        )
        for key in ENTERPRISING_GRAHAM_MAP.keys():
            split_key = key.split("_")
            title_key = " ".join(k.title() for k in split_key)
            analyzed_key = analysis.__getattribute__(key)
            if isinstance(analyzed_key,str):
                ak = analyzed_key.split()
                if len(ak) == 2:
                    if all([ak[0].isnumeric(),ak[1].isnumeric()]):
                        analyzed_key = ''.join([ak[0],'.',ak[1][:2]])
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key,(float,int)):
                if isinstance(analyzed_key,int):
                    analyzed_key = f"{analyzed_key:,d}"
                else:
                    analyzed_key = f"{analyzed_key:,.2f}"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key, bool):
                if analyzed_key:
                    analyzed_key = "True"
                else:
                    analyzed_key = "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key is None:
                analyzed_key = "None"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key == "0" or analyzed_key == "1":
                ak = {"0": True, "1": False}
                analyzed_key = "True" if ak.get(analyzed_key) else "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            else:
                analyzed_key = str(analyzed_key)
                print(f"{title_key:>60s}  :\t{analyzed_key}")

        for key in ENTERPRISING_CRITERIA_MAP:
            title_key = " ".join(part.title() for part in key.split("_"))
            analyzed_key = analysis.__getattribute__(key)
            if isinstance(analyzed_key,str):
                ak = analyzed_key.split()
                if len(ak) == 2:
                    if all([ak[0].isnumeric(),ak[1].isnumeric()]):
                        analyzed_key = ''.join([ak[0],'.',ak[1][:2]])
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key,(float,int)):
                if isinstance(analyzed_key,int):
                    analyzed_key = f"{analyzed_key:,d}"
                else:
                    analyzed_key = f"{analyzed_key:,.2f}"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key, bool):
                if analyzed_key:
                    analyzed_key = "True"
                else:
                    analyzed_key = "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key is None:
                analyzed_key = "None"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key == "0" or analyzed_key == "1":
                ak = {"0": True, "1": False}
                analyzed_key = "True" if ak.get(analyzed_key) else "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            else:
                analyzed_key = str(analyzed_key)
                print(f"{title_key:>60s}  :\t{analyzed_key}")

    elif investor_type == 'defensive':
        print(
            "\nFinancial Assessment using Ben Graham's metrics for the Defensive investor:",
            "\n---------------------------------------------------------------------------",
        )
        for key in DEFENSIVE_GRAHAM_MAP.keys():
            split_key = key.split("_")
            title_key = " ".join(k.title() for k in split_key)
            analyzed_key = analysis.__getattribute__(key)
            if isinstance(analyzed_key,str):
                ak = analyzed_key.split('.')
                if len(ak) == 2:
                    if all([ak[0].isnumeric(),ak[1].isnumeric()]):
                        analyzed_key = ''.join([ak[0],'.',ak[1][:2]])
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key,(float,int)):
                if isinstance(analyzed_key,int):
                    analyzed_key = f"{analyzed_key:,d}"
                else:
                    analyzed_key = f"{analyzed_key:,.2f}"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key, bool):
                if analyzed_key:
                    analyzed_key = "True"
                else:
                    analyzed_key = "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key is None:
                analyzed_key = "None"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key == "0" or analyzed_key == "1":
                ak = {"0": True, "1": False}
                analyzed_key = "True" if ak.get(analyzed_key) else "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            else:
                analyzed_key = str(analyzed_key)
                print(f"{title_key:>60s}  :\t{analyzed_key}")

        for key in DEFENSIVE_CRITERIA_MAP:
            title_key = " ".join(part.title() for part in key.split("_"))
            analyzed_key = analysis.__getattribute__(key)
            if isinstance(analyzed_key,str):
                ak = analyzed_key.split()
                if len(ak) == 2:
                    if all([ak[0].isnumeric(),ak[1].isnumeric()]):
                        analyzed_key = ''.join([ak[0],'.',ak[1][:2]])
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key,(float,int)):
                if isinstance(analyzed_key,int):
                    analyzed_key = f"{analyzed_key:,d}"
                else:
                    analyzed_key = f"{analyzed_key:,.2f}"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif isinstance(analyzed_key, bool):
                if analyzed_key:
                    analyzed_key = "True"
                else:
                    analyzed_key = "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key is None:
                analyzed_key = "None"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            elif analyzed_key == "0" or analyzed_key == "1":
                ak = {"0": True, "1": False}
                analyzed_key = 'True' if ak.get(analyzed_key) else "False"
                print(f"{title_key:>60s}  :\t{analyzed_key}")
            else:
                analyzed_key = str(analyzed_key)
                print(f"{title_key:>60s}  :\t{analyzed_key}")


def _security_analysis_to_contract_dict(
        analysis: SecurityAnalysisResult,
        investor_type: str | None = None,
) -> dict:
    result = asdict(analysis)
    if isinstance(result.get("analysis_date"), dt.date):
        result["analysis_date"] = result["analysis_date"].isoformat()

    allowed_fields = set(FINANCIAL_ASSESSMENT_MAP)
    allowed_fields.add("period_three_year_average_eps")
    if investor_type is None:
        allowed_fields.update(DEFENSIVE_GRAHAM_MAP)
        allowed_fields.update(ENTERPRISING_GRAHAM_MAP)
        allowed_fields.update(DEFENSIVE_CRITERIA_MAP)
        allowed_fields.update(ENTERPRISING_CRITERIA_MAP)
        allowed_fields.update({
            "defensive_criteria_met",
            "enterprising_criteria_met",
        })
    elif investor_type == "defensive":
        allowed_fields.update(DEFENSIVE_GRAHAM_MAP)
        allowed_fields.update(DEFENSIVE_CRITERIA_MAP)
        allowed_fields.add("defensive_criteria_met")
    elif investor_type == "enterprising":
        allowed_fields.update(ENTERPRISING_GRAHAM_MAP)
        allowed_fields.update(ENTERPRISING_CRITERIA_MAP)
        allowed_fields.add("enterprising_criteria_met")

    allowed_fields.update(
        {
            "data_complete",
            "missing_fields",
            "calculation_warnings",
            "not_applicable_fields",
            "field_explanations",
        }
    )
    return {
        key: value
        for key, value in result.items()
        if key in allowed_fields
    }


def eligible_common_stock_analysis(
        ticker: None | str = None,
        analysis_date: None | str = None,
        investor_type: None | str = None
) -> dict:

    """"
    Produce a dictionary containing all Reveal analysis metrics. If no ticker is given, it will give
    a dictionary where keys are the ticker symbols, and the values are a dictionary of the metrics.
    analysis_date is a string in the form YYYY-MM-DD.
    investor_type is type str 'defensive' or 'enterprising', or type None.
    Neither analysis_date nor investor_type are case-sensitive.
    """

    if ticker is not None and not isinstance(ticker, str):
        raise ValueError("ticker must be a string or None")
    if investor_type and investor_type.lower() not in ('defensive', 'enterprising'):
        raise ValueError("investor_type must be None, defensive, or enterprising")
    if analysis_date and not isinstance(analysis_date, str):
        raise ValueError("analysis_date must be a string")
    elif analysis_date:
        split_d = analysis_date.split('-')
        if len(split_d) < 3 or not all((split_d[0].isnumeric(),split_d[1].isnumeric(),split_d[2].isnumeric())):
            raise ValueError("analysis_date must be of string form YYYY-MM-DD")
    ticker = ticker.upper() if ticker else None
    # investor_type is a string or None
    investor_type = investor_type.lower() if investor_type else None

    # dictionary to return
    analysis = {}

    if ticker is None:
        # run all tickers since one was not selected. the following function takes ~60 sec
        print("No ticker symbol provided, running all eligible tickers...")
        eligible_tickers = eligible_common_stock_tickers()
        for et in eligible_tickers:
            print("Ticker list instantiated, analyzing tickers in list...")
            try:
                analyzer = analyze_security(et, analysis_date=analysis_date)
                contract_result = _security_analysis_to_contract_dict(
                    analyzer,
                    investor_type=investor_type,
                )
                analysis[et] = _investment_criteria_met(
                    contract_result,
                    investor_type=investor_type,
                )
            except Exception as e:
                analysis[et] = {
                    "ticker": et,
                    "data_complete": False,
                    "missing_fields": (),
                    "calculation_warnings": (f"Error analyzing ticker {et}: {e}",),
                }

        return analysis
    else:
        try:
            analyzer = analyze_security(ticker, analysis_date=analysis_date)
            analysis = _security_analysis_to_contract_dict(
                analyzer,
                investor_type=investor_type,
            )
            return _investment_criteria_met(
                analysis,
                investor_type=investor_type,
            )
        except Exception as e:
            print(f"Error analyzing ticker {ticker}: {e}")
            return {}


def _investment_criteria_met(
        stock_analysis_dict: dict,
        investor_type: None | str = None,
) -> dict:
    """Add legacy-prefixed criterion keys without recalculating analysis."""
    if not isinstance(stock_analysis_dict, dict):
        raise TypeError("stock_analysis_dict must be a dictionary")

    result = dict(stock_analysis_dict)
    ticker = result.get("ticker")
    if not isinstance(ticker, str) or not ticker:
        return result

    if investor_type is not None and not isinstance(investor_type, str):
        raise TypeError("investor_type must be a string or None")
    normalized_type = investor_type.lower() if investor_type else None
    if normalized_type == "enterprise":
        normalized_type = "enterprising"
    if normalized_type not in (None, "defensive", "enterprising"):
        raise ValueError(
            "investor_type must be None, defensive, or enterprising"
        )

    strategies = {
        "defensive": (
            DEFENSIVE_CRITERIA_MAP,
            "defensive_criteria_",
            "defensive_criteria_met",
        ),
        "enterprising": (
            ENTERPRISING_CRITERIA_MAP,
            "enterprising_criteria_",
            "enterprising_criteria_met",
        ),
    }
    selected = (
        strategies
        if normalized_type is None
        else {normalized_type: strategies[normalized_type]}
    )

    for _, (
            criteria_map,
            prefix,
            summary_field,
    ) in selected.items():
        for result_field, source_key in criteria_map.items():
            value = result.get(result_field)
            if value is not None:
                result[f"{prefix}{source_key}"] = bool(value)
        result.setdefault(
            summary_field,
            _criteria_summary(result, criteria_map),
        )

    return result
