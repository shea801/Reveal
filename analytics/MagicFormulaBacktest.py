"""Availability-aware Magic Formula cohort and return calculations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import datetime as dt
import sqlite3

import pandas as pd

from analytics.MyMagicFormula import magic_formula_ranked_securities
from data_access.SECFilingMetadata import (
    is_usable_backtest_match,
    required_matches_for_quarter,
)
from Securities_DB.magic_formula_database import RESULT_TABLE
from Securities_DB.ohlcv_database import OHLCV_TABLE


class BacktestDataError(RuntimeError):
    """Raised when a strict backtest prerequisite is unavailable."""


class AdjustedPriceDataUnavailableError(BacktestDataError):
    """Raised when split/dividend-aware prices cannot support a cohort."""


def build_availability_aware_cohort(
    investment_conn: sqlite3.Connection,
    results_conn: sqlite3.Connection,
    *,
    quarter_date: str,
    ranking_fn: Callable[..., pd.DataFrame] = magic_formula_ranked_securities,
    maximum_trading_delay_days: int = 10,
) -> dict:
    """Build and rerank one quarter after every included filing is public."""
    rank_rows = results_conn.execute(f"""
        SELECT ticker, quarter_date, associated_annual_date
        FROM {RESULT_TABLE}
        WHERE quarter_date = ?
        ORDER BY ticker
    """, (quarter_date,)).fetchall()
    if not rank_rows:
        raise BacktestDataError(f"No persisted Magic Formula cohort for {quarter_date}")

    included = []
    excluded = []
    availability = {}
    for row in rank_rows:
        record = dict(row)
        matches = required_matches_for_quarter(
            investment_conn,
            ticker=record["ticker"],
            quarter_date=quarter_date,
            associated_annual_date=record["associated_annual_date"],
        )
        if len(matches) != 5:
            excluded.append({
                "ticker": record["ticker"],
                "reason": "missing_required_statement_match",
            })
            continue
        unusable = [match for match in matches if not is_usable_backtest_match(match)]
        if unusable:
            excluded.append({
                "ticker": record["ticker"],
                "reason": _match_exclusion_reason(unusable),
            })
            continue
        included.append(record["ticker"])
        availability[record["ticker"]] = max(
            match["acceptance_datetime_utc"] for match in matches
        )

    if not included:
        raise BacktestDataError(
            f"No {quarter_date} securities have five usable SEC statement matches"
        )

    information_cutoff_utc = max(availability.values())
    included, missing_purchase_prices = _tickers_with_purchase_price_window(
        investment_conn,
        included,
        information_cutoff_utc,
        maximum_delay_days=maximum_trading_delay_days,
    )
    excluded.extend({
        "ticker": ticker,
        "reason": "missing_adjusted_purchase_price",
    } for ticker in missing_purchase_prices)
    if not included:
        raise AdjustedPriceDataUnavailableError(
            f"No {quarter_date} securities have an adjusted purchase price "
            f"within {maximum_trading_delay_days} days after the SEC cutoff"
        )
    purchase_date = _common_trading_date(
        investment_conn,
        included,
        information_cutoff_utc,
        maximum_delay_days=maximum_trading_delay_days,
    )
    ranking = ranking_fn(
        tickers_list=included,
        date=quarter_date,
        market_price_date=purchase_date,
    )
    if ranking is None or ranking.empty:
        raise BacktestDataError(f"Reranking produced no values for {quarter_date}")
    ranking = ranking.copy()
    ranking["information_cutoff_utc"] = information_cutoff_utc
    ranking["purchase_date"] = purchase_date

    ranked_tickers = set(ranking["ticker"])
    for ticker in sorted(set(included).difference(ranked_tickers)):
        excluded.append({"ticker": ticker, "reason": "metric_calculation_unavailable"})

    return {
        "quarter_date": quarter_date,
        "information_cutoff_utc": information_cutoff_utc,
        "purchase_date": purchase_date,
        "source_ticker_count": len(rank_rows),
        "eligible_ticker_count": len(ranking.index),
        "excluded": sorted(excluded, key=lambda item: item["ticker"]),
        "ranking": ranking,
        "financial_value_limitation": (
            "Normalized financial values are not accession-pinned; SEC metadata "
            "controls timing but cannot detect later restatements."
        ),
    }


def _tickers_with_purchase_price_window(
    conn: sqlite3.Connection,
    tickers: list[str],
    cutoff_utc: str,
    *,
    maximum_delay_days: int,
) -> tuple[list[str], list[str]]:
    cutoff_date = dt.date.fromisoformat(cutoff_utc[:10])
    first_candidate = cutoff_date + dt.timedelta(days=1)
    last_candidate = first_candidate + dt.timedelta(
        days=maximum_delay_days
    )
    available = set()
    for start in range(0, len(tickers), 500):
        chunk = tickers[start:start + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(f"""
            SELECT DISTINCT ticker
            FROM {OHLCV_TABLE}
            WHERE ticker IN ({placeholders})
              AND date BETWEEN ? AND ?
              AND close IS NOT NULL
              AND adjusted_close IS NOT NULL
        """, [
            *chunk,
            first_candidate.isoformat(),
            last_candidate.isoformat(),
        ]).fetchall()
        available.update(row["ticker"] for row in rows)
    return (
        [ticker for ticker in tickers if ticker in available],
        [ticker for ticker in tickers if ticker not in available],
    )


def calculate_one_year_returns(
    investment_conn: sqlite3.Connection,
    ranking: pd.DataFrame,
    *,
    top_n: int = 30,
    maximum_exit_delay_days: int = 10,
) -> pd.DataFrame:
    """Calculate split/dividend-aware one-year returns for top-ranked rows."""
    if not isinstance(top_n, int) or top_n < 1:
        raise ValueError("top_n must be a positive integer")
    required = {"ticker", "purchase_date", "magic_formula_rank"}
    if ranking is None or ranking.empty or not required.issubset(ranking.columns):
        return pd.DataFrame()

    rows = []
    selected = ranking.sort_values("magic_formula_rank").head(top_n)
    for record in selected.to_dict(orient="records"):
        purchase = _adjusted_price_on_date(
            investment_conn,
            record["ticker"],
            record["purchase_date"],
        )
        if purchase is None:
            raise AdjustedPriceDataUnavailableError(
                f"Missing adjusted purchase price for {record['ticker']} "
                f"on {record['purchase_date']}"
            )
        target_exit = _add_year(record["purchase_date"])
        exit_price = _first_adjusted_price_on_or_after(
            investment_conn,
            record["ticker"],
            target_exit,
            maximum_delay_days=maximum_exit_delay_days,
        )
        if exit_price is None:
            raise AdjustedPriceDataUnavailableError(
                f"Missing adjusted one-year exit price for {record['ticker']} "
                f"on or after {target_exit}"
            )
        if exit_price["source"] != purchase["source"]:
            raise AdjustedPriceDataUnavailableError(
                f"Adjusted price source changed for {record['ticker']} between "
                f"{record['purchase_date']} and {exit_price['date']}"
            )
        rows.append({
            **record,
            "purchase_adjusted_close": purchase["adjusted_close"],
            "exit_date": exit_price["date"],
            "exit_adjusted_close": exit_price["adjusted_close"],
            "one_year_total_return": (
                exit_price["adjusted_close"] / purchase["adjusted_close"] - 1
            ),
            "adjusted_price_source": purchase["source"],
        })
    return pd.DataFrame(rows)


def run_magic_formula_backtest(
    investment_conn: sqlite3.Connection,
    results_conn: sqlite3.Connection,
    *,
    quarter_dates: Iterable[str],
    top_n: int = 30,
    ranking_fn: Callable[..., pd.DataFrame] = magic_formula_ranked_securities,
) -> dict:
    """Run the strict eight-stage workflow for explicit quarterly cohorts."""
    cohorts = []
    positions = []
    exclusions = []
    for quarter_date in sorted(set(quarter_dates)):
        cohort = build_availability_aware_cohort(
            investment_conn,
            results_conn,
            quarter_date=quarter_date,
            ranking_fn=ranking_fn,
        )
        cohort_returns = calculate_one_year_returns(
            investment_conn,
            cohort["ranking"],
            top_n=top_n,
        )
        cohorts.append({
            key: value
            for key, value in cohort.items()
            if key not in {"ranking", "excluded"}
        })
        positions.extend(cohort_returns.to_dict(orient="records"))
        exclusions.extend([
            {"quarter_date": quarter_date, **record}
            for record in cohort["excluded"]
        ])
    positions_frame = pd.DataFrame(positions)
    period_returns = _equal_weighted_period_returns(positions_frame)
    return {
        "cohorts": pd.DataFrame(cohorts),
        "positions": positions_frame,
        "period_returns": period_returns,
        "exclusions": pd.DataFrame(exclusions),
    }


def _common_trading_date(
    conn: sqlite3.Connection,
    tickers: list[str],
    cutoff_utc: str,
    *,
    maximum_delay_days: int,
) -> str:
    cutoff_date = dt.date.fromisoformat(cutoff_utc[:10])
    first_candidate = cutoff_date + dt.timedelta(days=1)
    last_candidate = first_candidate + dt.timedelta(days=maximum_delay_days)
    adjusted_dates = _ticker_dates_in_range(
        conn,
        tickers,
        first_candidate.isoformat(),
        last_candidate.isoformat(),
        required_price_column="adjusted_close",
    )
    raw_dates = _ticker_dates_in_range(
        conn,
        tickers,
        first_candidate.isoformat(),
        last_candidate.isoformat(),
        required_price_column="close",
    )
    required = set(tickers)
    for offset in range(maximum_delay_days + 1):
        candidate = (first_candidate + dt.timedelta(days=offset)).isoformat()
        if adjusted_dates.get(candidate) == required and raw_dates.get(candidate) == required:
            return candidate
    raise AdjustedPriceDataUnavailableError(
        "No common raw and adjusted trading date exists for the cohort within "
        f"{maximum_delay_days} days after {cutoff_utc}"
    )


def _ticker_dates_in_range(
    conn: sqlite3.Connection,
    tickers: list[str],
    start_date: str,
    end_date: str,
    *,
    required_price_column: str,
) -> dict[str, set[str]]:
    if required_price_column not in {"close", "adjusted_close"}:
        raise ValueError("Unsupported OHLCV price column")
    result: dict[str, set[str]] = {}
    for start in range(0, len(tickers), 500):
        chunk = tickers[start:start + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(f"""
            SELECT ticker, date
            FROM {OHLCV_TABLE}
            WHERE ticker IN ({placeholders})
              AND date BETWEEN ? AND ?
              AND {required_price_column} IS NOT NULL
        """, [*chunk, start_date, end_date]).fetchall()
        for row in rows:
            result.setdefault(row["date"], set()).add(row["ticker"])
    return result


def _adjusted_price_on_date(
    conn: sqlite3.Connection,
    ticker: str,
    date: str,
) -> dict | None:
    row = conn.execute(f"""
        SELECT date, adjusted_close, price_source AS source
        FROM {OHLCV_TABLE}
        WHERE ticker = ? AND date = ?
        LIMIT 1
    """, (ticker, date)).fetchone()
    return dict(row) if row is not None else None


def _first_adjusted_price_on_or_after(
    conn: sqlite3.Connection,
    ticker: str,
    date: str,
    *,
    maximum_delay_days: int,
) -> dict | None:
    maximum = (
        dt.date.fromisoformat(date) + dt.timedelta(days=maximum_delay_days)
    ).isoformat()
    row = conn.execute(f"""
        SELECT date, adjusted_close, price_source AS source
        FROM {OHLCV_TABLE}
        WHERE ticker = ? AND date BETWEEN ? AND ?
        ORDER BY date
        LIMIT 1
    """, (ticker, date, maximum)).fetchone()
    return dict(row) if row is not None else None


def _equal_weighted_period_returns(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame(columns=[
            "quarter_date", "position_count", "equal_weighted_total_return"
        ])
    return (
        positions.groupby("quarter_date", as_index=False)
        .agg(
            position_count=("ticker", "count"),
            equal_weighted_total_return=("one_year_total_return", "mean"),
        )
        .sort_values("quarter_date")
        .reset_index(drop=True)
    )


def _match_exclusion_reason(unusable: list[dict]) -> str:
    identities = {record.get("identity_status") for record in unusable}
    if "predates_current_cik_history" in identities or "ambiguous" in identities:
        return "ambiguous_ticker_cik_identity"
    if any(record.get("confidence") == "low" for record in unusable):
        return "low_confidence_statement_match"
    return "unresolved_statement_match"


def _add_year(value: str) -> str:
    date = dt.date.fromisoformat(value)
    try:
        return date.replace(year=date.year + 1).isoformat()
    except ValueError:
        return date.replace(year=date.year + 1, day=28).isoformat()
