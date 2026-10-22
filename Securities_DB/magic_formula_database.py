"""Build and query the quarterly Magic Formula ranking database."""

from __future__ import annotations

import csv
from contextlib import contextmanager, nullcontext, redirect_stdout
import datetime as dt
import os
from pathlib import Path
import sqlite3
from typing import Callable, Iterable

import pandas as pd

from analytics.MyMagicFormula import (
    _eligible_magic_formula_tickers,
    magic_formula_ranked_securities,
)
from runtime_config import get_data_root, magic_formula_db_path
from Securities_DB.db_connection import get_connection


MAGIC_FORMULA_TICKERS_BACKUP = "magic_formula_ranked_securities.csv"
RESULT_TABLE = "magic_formula_quarterly_results"
ORDERED_VIEW = "magic_formula_rankings_ordered"
ANNUAL_SOURCE_TABLES = frozenset({
    "balance_sheet_annual",
    "cash_flow_annual",
    "income_annual",
    "earnings_annual",
})

RESULT_COLUMNS = (
    "ticker",
    "quarter_date",
    "associated_annual_date",
    "financial_statement_availability_date",
    "magic_formula_rank",
    "return_on_capital_rank",
    "earnings_yield_rank",
    "total_roc_ey_score",
)


def default_magic_formula_db_path() -> Path:
    return magic_formula_db_path()


def default_ticker_backup_path() -> Path:
    return get_data_root() / "notebooks" / MAGIC_FORMULA_TICKERS_BACKUP


def connect_magic_formula_db(
    db_path: str | Path | None = None,
    readonly: bool = False,
) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else default_magic_formula_db_path()
    if readonly:
        if not path.is_file():
            raise FileNotFoundError("Magic Formula database is missing.")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_magic_formula_schema(
    conn: sqlite3.Connection,
    rebuild: bool = False,
) -> None:
    """Create the rank-only schema, optionally replacing an older schema."""
    conn.execute("PRAGMA foreign_keys=ON")
    if rebuild:
        conn.execute(f"DROP VIEW IF EXISTS {ORDERED_VIEW}")
        conn.execute(f"DROP TABLE IF EXISTS {RESULT_TABLE}")
        conn.execute("DROP TABLE IF EXISTS magic_formula_symbols")
    else:
        _raise_for_incompatible_schema(conn)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS magic_formula_symbols (
            ticker TEXT PRIMARY KEY
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {RESULT_TABLE} (
            ticker TEXT NOT NULL,
            quarter_date TEXT NOT NULL,
            associated_annual_date TEXT NOT NULL,
            financial_statement_availability_date TEXT,
            magic_formula_rank INTEGER NOT NULL
                CHECK (magic_formula_rank >= 1),
            return_on_capital_rank INTEGER NOT NULL
                CHECK (return_on_capital_rank >= 1),
            earnings_yield_rank INTEGER NOT NULL
                CHECK (earnings_yield_rank >= 1),
            total_roc_ey_score INTEGER NOT NULL
                CHECK (
                    total_roc_ey_score =
                    return_on_capital_rank + earnings_yield_rank
                ),
            PRIMARY KEY (ticker, quarter_date),
            FOREIGN KEY (ticker)
                REFERENCES magic_formula_symbols(ticker)
                ON DELETE CASCADE
        )
    """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_mf_quarter_rank
        ON {RESULT_TABLE}(quarter_date, magic_formula_rank, ticker)
    """)
    conn.execute(f"""
        CREATE VIEW IF NOT EXISTS {ORDERED_VIEW} AS
        SELECT {", ".join(RESULT_COLUMNS)}
        FROM {RESULT_TABLE}
        ORDER BY quarter_date, magic_formula_rank, ticker
    """)
    conn.commit()


def normalize_tickers(tickers: Iterable[str]) -> list[str]:
    return sorted({
        ticker.strip().upper()
        for ticker in tickers
        if isinstance(ticker, str) and ticker.strip()
    })


def write_magic_formula_ticker_backup(
    tickers: Iterable[str],
    backup_path: str | Path | None = None,
) -> Path:
    path = Path(backup_path) if backup_path else default_ticker_backup_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as backup_file:
        writer = csv.writer(backup_file, lineterminator="\n")
        writer.writerow(["ticker"])
        writer.writerows((ticker,) for ticker in normalize_tickers(tickers))
    return path


def read_magic_formula_ticker_backup(
    backup_path: str | Path | None = None,
) -> list[str]:
    path = Path(backup_path) if backup_path else default_ticker_backup_path()
    if not path.exists():
        return []
    with path.open(newline="") as backup_file:
        reader = csv.DictReader(backup_file)
        if reader.fieldnames and "ticker" in reader.fieldnames:
            return normalize_tickers(row.get("ticker", "") for row in reader)
    return []


def magic_formula_symbols_from_results_db(
    conn: sqlite3.Connection,
) -> list[str]:
    create_magic_formula_schema(conn)
    rows = conn.execute(
        "SELECT ticker FROM magic_formula_symbols ORDER BY ticker"
    ).fetchall()
    return [row["ticker"] for row in rows]


def refresh_magic_formula_symbols(
    conn: sqlite3.Connection,
    ticker_list: list[str] | None = None,
    backup_path: str | Path | None = None,
    eligible_tickers_fn: Callable[..., list[str]] = (
        _eligible_magic_formula_tickers
    ),
) -> list[str]:
    create_magic_formula_schema(conn)
    eligible = (
        eligible_tickers_fn(ticker_list=ticker_list)
        if ticker_list
        else eligible_tickers_fn()
    )
    tickers = normalize_tickers(eligible)
    existing = set(magic_formula_symbols_from_results_db(conn))
    conn.executemany(
        "INSERT OR IGNORE INTO magic_formula_symbols (ticker) VALUES (?)",
        [(ticker,) for ticker in tickers],
    )
    removed = existing.difference(tickers)
    conn.executemany(
        "DELETE FROM magic_formula_symbols WHERE ticker = ?",
        [(ticker,) for ticker in removed],
    )
    conn.commit()
    write_magic_formula_ticker_backup(tickers, backup_path=backup_path)
    return tickers


def quarter_end_dates(
    start_date: str | dt.date,
    end_date: str | dt.date,
) -> list[str]:
    start = _as_date(start_date)
    end = _as_date(end_date)
    if start > end:
        return []
    dates = []
    for year in range(start.year, end.year + 1):
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
            quarter_end = dt.date(year, month, day)
            if start <= quarter_end <= end:
                dates.append(quarter_end.isoformat())
    return dates


def infer_quarter_end_dates(
    investment_conn: sqlite3.Connection,
    minimum_history_years: int = 5,
) -> list[str]:
    """Infer rankable quarter ends without requiring forward price data."""
    minimums = []
    maximums = []
    for table_name, date_column in _source_date_tables():
        row = investment_conn.execute(f"""
            SELECT MIN({date_column}) AS min_date,
                   MAX({date_column}) AS max_date
            FROM {table_name}
            WHERE {date_column} IS NOT NULL
        """).fetchone()
        if row and row["min_date"] and row["max_date"]:
            minimums.append(_as_date(row["min_date"]))
            maximum = _as_date(row["max_date"])
            if table_name in ANNUAL_SOURCE_TABLES:
                maximum = _add_years(maximum, 1)
            maximums.append(maximum)
    if not minimums or not maximums:
        return []
    start = _add_years(max(minimums), minimum_history_years - 1)
    return quarter_end_dates(start, min(maximums))


def eligible_ticker_quarter_batches(
    investment_conn: sqlite3.Connection,
    tickers: list[str],
    minimum_history_years: int = 5,
) -> dict[str, list[str]]:
    """Map quarter ends to tickers with sufficient source-date coverage."""
    normalized = normalize_tickers(tickers)
    if not normalized:
        return {}

    tables = _source_date_tables()
    lower_bounds = {ticker: [] for ticker in normalized}
    upper_bounds = {ticker: [] for ticker in normalized}
    for table_name, date_column in tables:
        bounds = _date_bounds_by_ticker(
            investment_conn,
            table_name,
            date_column,
            normalized,
        )
        for ticker, (minimum, maximum) in bounds.items():
            if table_name in ANNUAL_SOURCE_TABLES:
                maximum = _add_years(maximum, 1)
            lower_bounds[ticker].append(minimum)
            upper_bounds[ticker].append(maximum)

    batches: dict[str, list[str]] = {}
    required_table_count = len(tables)
    for ticker in normalized:
        if (
            len(lower_bounds[ticker]) != required_table_count
            or len(upper_bounds[ticker]) != required_table_count
        ):
            continue
        start = _add_years(
            max(lower_bounds[ticker]),
            minimum_history_years - 1,
        )
        end = min(upper_bounds[ticker])
        for quarter_date in quarter_end_dates(start, end):
            batches.setdefault(quarter_date, []).append(ticker)
    return {
        quarter_date: sorted(date_tickers)
        for quarter_date, date_tickers in sorted(batches.items())
    }


def financial_statement_availability_date(
    investment_conn: sqlite3.Connection,
    ticker: str,
    quarter_date: str,
    associated_annual_date: str,
) -> str | None:
    """Return when all four TTM reports and the annual report were available."""
    quarterly_rows = investment_conn.execute(
        """
        SELECT reportedDate
        FROM earnings_quarterly
        WHERE ticker = ?
          AND fiscalDateEnding <= ?
          AND reportedDate IS NOT NULL
        ORDER BY fiscalDateEnding DESC
        LIMIT 4
        """,
        (ticker, quarter_date),
    ).fetchall()
    if len(quarterly_rows) != 4:
        return None

    annual_row = investment_conn.execute(
        """
        SELECT reportedDate
        FROM earnings_quarterly
        WHERE ticker = ?
          AND fiscalDateEnding = ?
          AND reportedDate IS NOT NULL
        LIMIT 1
        """,
        (ticker, associated_annual_date),
    ).fetchone()
    if annual_row is None:
        return None

    dates = [_as_date(row["reportedDate"]) for row in quarterly_rows]
    dates.append(_as_date(annual_row["reportedDate"]))
    return max(dates).isoformat()


def magic_formula_records_for_date(
    tickers: list[str],
    quarter_date: str,
    investment_conn: sqlite3.Connection | None = None,
    ranking_fn: Callable[..., pd.DataFrame] = magic_formula_ranked_securities,
) -> list[dict]:
    ranking = ranking_fn(tickers_list=tickers, date=quarter_date)
    if ranking is None or ranking.empty:
        return []

    records = []
    for raw_record in ranking.to_dict(orient="records"):
        record = _normalize_record(raw_record, quarter_date=quarter_date)
        if investment_conn is not None:
            record["financial_statement_availability_date"] = (
                financial_statement_availability_date(
                    investment_conn,
                    record["ticker"],
                    record["quarter_date"],
                    record["associated_annual_date"],
                )
            )
        records.append(record)
    return records


def upsert_magic_formula_records(
    conn: sqlite3.Connection,
    records: Iterable[dict],
) -> int:
    create_magic_formula_schema(conn)
    rows = []
    for record in records:
        normalized = _normalize_record(record)
        rows.append(tuple(normalized[column] for column in RESULT_COLUMNS))
    if not rows:
        return 0

    conn.executemany(
        "INSERT OR IGNORE INTO magic_formula_symbols (ticker) VALUES (?)",
        [(row[0],) for row in rows],
    )
    placeholders = ", ".join("?" for _ in RESULT_COLUMNS)
    updates = ", ".join(
        f"{column}=excluded.{column}"
        for column in RESULT_COLUMNS
        if column not in ("ticker", "quarter_date")
    )
    conn.executemany(f"""
        INSERT INTO {RESULT_TABLE} ({", ".join(RESULT_COLUMNS)})
        VALUES ({placeholders})
        ON CONFLICT(ticker, quarter_date) DO UPDATE SET {updates}
    """, rows)
    conn.commit()
    return len(rows)


def replace_magic_formula_quarter_records(
    conn: sqlite3.Connection,
    quarter_date: str,
    records: Iterable[dict],
) -> int:
    """Atomically replace one quarter without changing other rank periods."""
    create_magic_formula_schema(conn)
    normalized_quarter = _iso_date(quarter_date)
    normalized_records = [_normalize_record(record) for record in records]
    if any(
        record["quarter_date"] != normalized_quarter
        for record in normalized_records
    ):
        raise ValueError("Every replacement record must match quarter_date")

    existing_count = conn.execute(f"""
        SELECT COUNT(*) FROM {RESULT_TABLE} WHERE quarter_date = ?
    """, (normalized_quarter,)).fetchone()[0]
    if existing_count and not normalized_records:
        raise RuntimeError(
            f"Refusing to replace populated quarter {normalized_quarter} "
            "with no calculated records"
        )

    rows = [
        tuple(record[column] for column in RESULT_COLUMNS)
        for record in normalized_records
    ]
    placeholders = ", ".join("?" for _ in RESULT_COLUMNS)
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO magic_formula_symbols (ticker) VALUES (?)",
            [(row[0],) for row in rows],
        )
        conn.execute(
            f"DELETE FROM {RESULT_TABLE} WHERE quarter_date = ?",
            (normalized_quarter,),
        )
        conn.executemany(f"""
            INSERT INTO {RESULT_TABLE} ({", ".join(RESULT_COLUMNS)})
            VALUES ({placeholders})
        """, rows)
    return len(rows)


def completed_quarter_dates(conn: sqlite3.Connection) -> set[str]:
    create_magic_formula_schema(conn)
    rows = conn.execute(
        f"SELECT DISTINCT quarter_date FROM {RESULT_TABLE}"
    ).fetchall()
    return {row["quarter_date"] for row in rows}


def magic_formula_rankings_for_quarter(
    conn: sqlite3.Connection,
    quarter_date: str,
) -> pd.DataFrame:
    return pd.read_sql_query(
        f"""
        SELECT {", ".join(RESULT_COLUMNS)}
        FROM {RESULT_TABLE}
        WHERE quarter_date = ?
        ORDER BY magic_formula_rank, ticker
        """,
        conn,
        params=(quarter_date,),
    )


def validate_magic_formula_database(conn: sqlite3.Connection) -> dict:
    _raise_for_incompatible_schema(conn)
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (RESULT_TABLE,),
    ).fetchone()
    if not exists:
        raise RuntimeError("Magic Formula results table does not exist")
    columns = [
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({RESULT_TABLE})")
    ]
    if columns != list(RESULT_COLUMNS):
        raise RuntimeError(f"Unexpected Magic Formula columns: {columns}")

    duplicate_count = conn.execute(f"""
        SELECT COUNT(*)
        FROM (
            SELECT ticker, quarter_date
            FROM {RESULT_TABLE}
            GROUP BY ticker, quarter_date
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    invalid_score_count = conn.execute(f"""
        SELECT COUNT(*)
        FROM {RESULT_TABLE}
        WHERE total_roc_ey_score !=
              return_on_capital_rank + earnings_yield_rank
    """).fetchone()[0]
    invalid_rank_quarters = conn.execute(f"""
        SELECT COUNT(*)
        FROM (
            SELECT quarter_date,
                   COUNT(*) AS row_count,
                   COUNT(DISTINCT magic_formula_rank) AS distinct_rank_count,
                   MIN(magic_formula_rank) AS minimum_rank,
                   MAX(magic_formula_rank) AS maximum_rank,
                   COUNT(DISTINCT return_on_capital_rank) AS roc_rank_count,
                   MIN(return_on_capital_rank) AS minimum_roc_rank,
                   MAX(return_on_capital_rank) AS maximum_roc_rank,
                   COUNT(DISTINCT earnings_yield_rank) AS ey_rank_count,
                   MIN(earnings_yield_rank) AS minimum_ey_rank,
                   MAX(earnings_yield_rank) AS maximum_ey_rank
            FROM {RESULT_TABLE}
            GROUP BY quarter_date
            HAVING distinct_rank_count != row_count
                OR minimum_rank != 1
                OR maximum_rank != row_count
                OR roc_rank_count != row_count
                OR minimum_roc_rank != 1
                OR maximum_roc_rank != row_count
                OR ey_rank_count != row_count
                OR minimum_ey_rank != 1
                OR maximum_ey_rank != row_count
        )
    """).fetchone()[0]
    invalid_order_count = conn.execute(f"""
        SELECT COUNT(*)
        FROM (
            SELECT magic_formula_rank,
                   ROW_NUMBER() OVER (
                       PARTITION BY quarter_date
                       ORDER BY total_roc_ey_score,
                                return_on_capital_rank,
                                earnings_yield_rank,
                                ticker
                   ) AS expected_rank
            FROM {RESULT_TABLE}
        )
        WHERE magic_formula_rank != expected_rank
    """).fetchone()[0]
    if (
        duplicate_count
        or invalid_score_count
        or invalid_rank_quarters
        or invalid_order_count
    ):
        raise RuntimeError(
            "Magic Formula database validation failed: "
            f"duplicates={duplicate_count}, "
            f"invalid_scores={invalid_score_count}, "
            f"invalid_rank_quarters={invalid_rank_quarters}, "
            f"invalid_order_rows={invalid_order_count}"
        )

    summary = conn.execute(f"""
        SELECT COUNT(*) AS result_row_count,
               COUNT(DISTINCT ticker) AS ranked_ticker_count,
               COUNT(DISTINCT quarter_date) AS quarter_date_count,
               MIN(quarter_date) AS first_quarter_date,
               MAX(quarter_date) AS last_quarter_date,
               SUM(financial_statement_availability_date IS NOT NULL)
                   AS availability_date_count
        FROM {RESULT_TABLE}
    """).fetchone()
    return dict(summary)


def build_magic_formula_results_database(
    db_path: str | Path | None = None,
    analysis_dates: list[str] | None = None,
    ticker_list: list[str] | None = None,
    backup_path: str | Path | None = None,
    investment_conn: sqlite3.Connection | None = None,
    ranking_fn: Callable[..., pd.DataFrame] = magic_formula_ranked_securities,
    eligible_tickers_fn: Callable[..., list[str]] = (
        _eligible_magic_formula_tickers
    ),
    quiet: bool = False,
    refresh_symbols: bool = True,
    skip_completed_dates: bool = False,
    rebuild_schema: bool = False,
) -> dict:
    """Build or update one rank-only row per ticker and quarter."""
    owns_investment_conn = investment_conn is None
    if investment_conn is None:
        investment_conn = get_connection(readonly=True)
    results_conn = connect_magic_formula_db(db_path)
    try:
        create_magic_formula_schema(results_conn, rebuild=rebuild_schema)
        if refresh_symbols:
            with _quiet_context(quiet):
                tickers = refresh_magic_formula_symbols(
                    results_conn,
                    ticker_list=ticker_list,
                    backup_path=backup_path,
                    eligible_tickers_fn=eligible_tickers_fn,
                )
        else:
            tickers = magic_formula_symbols_from_results_db(results_conn)
            if not tickers:
                tickers = read_magic_formula_ticker_backup(backup_path)
                results_conn.executemany(
                    "INSERT OR IGNORE INTO magic_formula_symbols VALUES (?)",
                    [(ticker,) for ticker in tickers],
                )
                results_conn.commit()

        if analysis_dates is None:
            ticker_batches = eligible_ticker_quarter_batches(
                investment_conn,
                tickers,
            )
        else:
            ticker_batches = {
                _iso_date(date): tickers
                for date in sorted(set(analysis_dates))
            }

        upserted_rows = 0
        processed_ticker_dates = 0
        skipped_quarter_dates = 0
        completed = (
            completed_quarter_dates(results_conn)
            if skip_completed_dates
            else set()
        )
        for quarter_date, date_tickers in ticker_batches.items():
            if quarter_date in completed:
                skipped_quarter_dates += 1
                continue
            with _quiet_context(quiet):
                records = magic_formula_records_for_date(
                    date_tickers,
                    quarter_date,
                    investment_conn=investment_conn,
                    ranking_fn=ranking_fn,
                )
            upserted_rows += replace_magic_formula_quarter_records(
                results_conn,
                quarter_date,
                records,
            )
            processed_ticker_dates += len(date_tickers)

        validation = validate_magic_formula_database(results_conn)
        return {
            "database_path": str(
                Path(db_path) if db_path else default_magic_formula_db_path()
            ),
            "ticker_count": len(tickers),
            "requested_quarter_date_count": len(ticker_batches),
            "processed_ticker_date_count": processed_ticker_dates,
            "skipped_quarter_date_count": skipped_quarter_dates,
            "upserted_result_row_count": upserted_rows,
            **validation,
        }
    finally:
        results_conn.close()
        if owns_investment_conn:
            investment_conn.close()


def rebuild_magic_formula_results_database(**kwargs) -> dict:
    """Build into a temporary SQLite file and atomically replace the target."""
    target = Path(
        kwargs.pop("db_path", None) or default_magic_formula_db_path()
    )
    kwargs.pop("skip_completed_dates", None)
    kwargs.pop("rebuild_schema", None)
    temporary = target.with_name(f".{target.name}.rebuild")
    _remove_sqlite_files(temporary)
    try:
        summary = build_magic_formula_results_database(
            db_path=temporary,
            rebuild_schema=True,
            skip_completed_dates=False,
            **kwargs,
        )
        check_conn = connect_magic_formula_db(temporary, readonly=True)
        try:
            validation = validate_magic_formula_database(check_conn)
        finally:
            check_conn.close()
        _checkpoint_database(target)
        _remove_sqlite_sidecars(target)
        os.replace(temporary, target)
        summary.update(validation)
        summary["database_path"] = str(target)
        return summary
    except Exception:
        _remove_sqlite_files(temporary)
        raise


def _source_date_tables() -> tuple[tuple[str, str], ...]:
    return (
        ("balance_sheet_annual", "fiscalDateEnding"),
        ("cash_flow_annual", "fiscalDateEnding"),
        ("income_annual", "fiscalDateEnding"),
        ("earnings_annual", "fiscalDateEnding"),
        ("balance_sheet_quarterly", "fiscalDateEnding"),
        ("income_quarterly", "fiscalDateEnding"),
        ("earnings_quarterly", "fiscalDateEnding"),
        ("ohlcv_daily", "date"),
    )


def _raise_for_incompatible_schema(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (RESULT_TABLE,),
    ).fetchone()
    if not exists:
        return
    columns = [
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({RESULT_TABLE})")
    ]
    if columns != list(RESULT_COLUMNS):
        raise RuntimeError(
            "Existing Magic Formula schema is incompatible. "
            "Run the builder with rebuild enabled."
        )


def _date_bounds_by_ticker(
    conn: sqlite3.Connection,
    table_name: str,
    date_column: str,
    tickers: list[str],
) -> dict[str, tuple[dt.date, dt.date]]:
    bounds = {}
    for start in range(0, len(tickers), 500):
        chunk = tickers[start:start + 500]
        placeholders = ", ".join("?" for _ in chunk)
        rows = conn.execute(f"""
            SELECT ticker,
                   MIN({date_column}) AS min_date,
                   MAX({date_column}) AS max_date
            FROM {table_name}
            WHERE ticker IN ({placeholders})
              AND {date_column} IS NOT NULL
            GROUP BY ticker
        """, chunk).fetchall()
        for row in rows:
            bounds[str(row["ticker"]).upper()] = (
                _as_date(row["min_date"]),
                _as_date(row["max_date"]),
            )
    return bounds


def _normalize_record(
    record: dict,
    quarter_date: str | None = None,
) -> dict:
    ticker = record.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("Magic Formula record requires a ticker")
    normalized = {column: None for column in RESULT_COLUMNS}
    normalized.update(record)
    normalized["ticker"] = ticker.strip().upper()
    normalized["quarter_date"] = _iso_date(
        normalized.get("quarter_date") or quarter_date
    )
    normalized["associated_annual_date"] = _iso_date(
        normalized.get("associated_annual_date")
    )
    normalized["financial_statement_availability_date"] = _iso_date(
        normalized.get("financial_statement_availability_date")
    )
    for column in (
        "magic_formula_rank",
        "return_on_capital_rank",
        "earnings_yield_rank",
        "total_roc_ey_score",
    ):
        normalized[column] = _to_int(normalized.get(column))
    if not normalized["quarter_date"]:
        raise ValueError("Magic Formula record requires a quarter_date")
    if not normalized["associated_annual_date"]:
        raise ValueError(
            "Magic Formula record requires an associated_annual_date"
        )
    return normalized


def _as_date(value: str | dt.date) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def _iso_date(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return _as_date(value).isoformat()


def _add_years(value: dt.date, years: int) -> dt.date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year + years)


def _to_int(value) -> int:
    if value is None or pd.isna(value):
        raise ValueError("Magic Formula rank values cannot be null")
    return int(value)


def _checkpoint_database(path: Path) -> None:
    if not path.exists():
        return
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _remove_sqlite_sidecars(path: Path) -> None:
    for sidecar in (
        path.with_name(f"{path.name}-wal"),
        path.with_name(f"{path.name}-shm"),
    ):
        if sidecar.exists():
            sidecar.unlink()


def _remove_sqlite_files(path: Path) -> None:
    if path.exists():
        path.unlink()
    _remove_sqlite_sidecars(path)


@contextmanager
def _quiet_context(quiet: bool):
    if not quiet:
        with nullcontext():
            yield
        return
    with open(os.devnull, "w") as devnull, redirect_stdout(devnull):
        yield
