"""Resumable, price-only Alpha Vantage adjusted-history backfills."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass
import datetime as dt
import io
from pathlib import Path
import sqlite3

from runtime_config import investment_db_path, magic_formula_db_path


@dataclass(frozen=True)
class PriceCoverage:
    ticker: str
    total_rows: int
    adjusted_rows: int
    first_date: str | None
    last_date: str | None
    first_adjusted_date: str | None
    last_adjusted_date: str | None

    @property
    def complete(self) -> bool:
        return self.adjusted_rows > 0 and self.adjusted_rows == self.total_rows


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def normalize_tickers(tickers: Iterable[str]) -> list[str]:
    """Return unique uppercase tickers while retaining caller order."""
    normalized = []
    seen = set()
    for ticker in tickers:
        if not isinstance(ticker, str):
            continue
        ticker = ticker.strip().upper()
        if ticker and ticker not in seen:
            normalized.append(ticker)
            seen.add(ticker)
    return normalized


def historical_magic_formula_tickers(
    db_path: str | Path | None = None,
) -> list[str]:
    """Read the distinct historical ranking universe without changing it."""
    path = Path(db_path) if db_path is not None else magic_formula_db_path()
    if not path.is_file():
        raise FileNotFoundError(f"Magic Formula database not found: {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT ticker
            FROM magic_formula_quarterly_results
            ORDER BY ticker
            """
        ).fetchall()
    finally:
        conn.close()
    return normalize_tickers(row[0] for row in rows)


def connect_investment_db(
    db_path: str | Path | None = None,
) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else investment_db_path()
    if not path.is_file():
        raise FileNotFoundError("Investment database is missing: Securities_DB/investment.db")
    conn = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=rw", uri=True, timeout=30
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_backfill_tracking_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS adjusted_price_backfill_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            requested_count INTEGER NOT NULL,
            planned_count INTEGER NOT NULL,
            updated_count INTEGER NOT NULL DEFAULT 0,
            skipped_count INTEGER NOT NULL DEFAULT 0,
            partial_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS adjusted_price_backfill_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            status TEXT NOT NULL,
            before_total_rows INTEGER NOT NULL,
            before_adjusted_rows INTEGER NOT NULL,
            after_total_rows INTEGER NOT NULL,
            after_adjusted_rows INTEGER NOT NULL,
            first_adjusted_date TEXT,
            last_adjusted_date TEXT,
            message TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id)
                REFERENCES adjusted_price_backfill_runs(run_id)
        );

        CREATE INDEX IF NOT EXISTS idx_adjusted_backfill_event_run
        ON adjusted_price_backfill_events(run_id, status, ticker);
        """
    )
    conn.commit()


def price_coverage(conn: sqlite3.Connection, ticker: str) -> PriceCoverage:
    row = conn.execute(
        """
        SELECT COUNT(*) AS total_rows,
               COUNT(adjusted_close) AS adjusted_rows,
               MIN(date) AS first_date,
               MAX(date) AS last_date,
               MIN(CASE WHEN adjusted_close IS NOT NULL THEN date END)
                   AS first_adjusted_date,
               MAX(CASE WHEN adjusted_close IS NOT NULL THEN date END)
                   AS last_adjusted_date
        FROM ohlcv_daily
        WHERE ticker = ?
        """,
        (ticker,),
    ).fetchone()
    return PriceCoverage(
        ticker=ticker,
        total_rows=row["total_rows"],
        adjusted_rows=row["adjusted_rows"],
        first_date=row["first_date"],
        last_date=row["last_date"],
        first_adjusted_date=row["first_adjusted_date"],
        last_adjusted_date=row["last_adjusted_date"],
    )


def plan_adjusted_price_backfill(
    conn: sqlite3.Connection,
    tickers: Iterable[str],
    *,
    limit: int | None = None,
    include_complete: bool = False,
) -> dict:
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")
    requested = normalize_tickers(tickers)
    planned = []
    complete = []
    for ticker in requested:
        coverage = price_coverage(conn, ticker)
        if coverage.complete and not include_complete:
            complete.append(ticker)
            continue
        if limit is None or len(planned) < limit:
            planned.append(ticker)
    return {
        "requested": requested,
        "planned": planned,
        "complete": complete,
        "deferred_count": len(requested) - len(planned) - len(complete),
    }


def refresh_adjusted_price_from_api(ticker: str) -> str:
    """Download one adjusted payload and load it through the shared parser."""
    from data_ingestion.DataExtraction import DataExtraction
    from Securities_DB.create_database import update_ohlcv_for_ticker

    output = io.StringIO()
    with redirect_stdout(output):
        DataExtraction(ticker).price_history_api_call_to_file()
        update_ohlcv_for_ticker(ticker)
    return " ".join(output.getvalue().split())


def run_adjusted_price_backfill(
    conn: sqlite3.Connection,
    tickers: Iterable[str],
    *,
    execute: bool = False,
    limit: int | None = None,
    include_complete: bool = False,
    stage: str = "manual",
    progress_every: int = 10,
    stop_on_error: bool = False,
    refresh_fn: Callable[[str], str | None] = refresh_adjusted_price_from_api,
) -> dict:
    """Plan or execute a verified adjusted-price backfill batch."""
    plan = plan_adjusted_price_backfill(
        conn,
        tickers,
        limit=limit,
        include_complete=include_complete,
    )
    summary = {
        "stage": stage,
        "requested_count": len(plan["requested"]),
        "planned_count": len(plan["planned"]),
        "already_complete_count": len(plan["complete"]),
        "deferred_count": plan["deferred_count"],
        "updated_count": 0,
        "skipped_count": len(plan["complete"]),
        "partial_count": 0,
        "failed_count": 0,
        "planned_tickers": plan["planned"],
    }
    if not execute:
        return summary

    ensure_backfill_tracking_schema(conn)
    cursor = conn.execute(
        """
        INSERT INTO adjusted_price_backfill_runs
            (stage, started_at, requested_count, planned_count, skipped_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            stage,
            utc_now(),
            summary["requested_count"],
            summary["planned_count"],
            summary["skipped_count"],
        ),
    )
    run_id = cursor.lastrowid
    conn.commit()
    summary["run_id"] = run_id

    for index, ticker in enumerate(plan["planned"], start=1):
        before = price_coverage(conn, ticker)
        message = ""
        try:
            message = refresh_fn(ticker) or ""
            after = price_coverage(conn, ticker)
            if after.complete:
                status = "updated"
            elif after.adjusted_rows > before.adjusted_rows:
                status = "partial"
            else:
                status = "failed"
                message = message or "No adjusted rows were added."
        except Exception as exc:  # continue so later tickers can be recovered
            after = price_coverage(conn, ticker)
            status = "failed"
            message = f"{type(exc).__name__}: {exc}"

        summary[f"{status}_count"] += 1
        conn.execute(
            """
            INSERT INTO adjusted_price_backfill_events (
                run_id, ticker, status, before_total_rows,
                before_adjusted_rows, after_total_rows, after_adjusted_rows,
                first_adjusted_date, last_adjusted_date, message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                ticker,
                status,
                before.total_rows,
                before.adjusted_rows,
                after.total_rows,
                after.adjusted_rows,
                after.first_adjusted_date,
                after.last_adjusted_date,
                message,
                utc_now(),
            ),
        )
        conn.commit()

        if status != "updated" or index % max(progress_every, 1) == 0:
            print(
                f"[{index}/{summary['planned_count']}] {ticker}: {status} "
                f"({after.adjusted_rows}/{after.total_rows} adjusted rows)"
            )
        if status == "failed" and stop_on_error:
            break

    conn.execute(
        """
        UPDATE adjusted_price_backfill_runs
        SET finished_at = ?, updated_count = ?, partial_count = ?,
            failed_count = ?
        WHERE run_id = ?
        """,
        (
            utc_now(),
            summary["updated_count"],
            summary["partial_count"],
            summary["failed_count"],
            run_id,
        ),
    )
    conn.commit()
    summary["completed_count"] = (
        summary["updated_count"]
        + summary["partial_count"]
        + summary["failed_count"]
    )
    return summary


def coverage_as_dict(conn: sqlite3.Connection, ticker: str) -> dict:
    """Expose coverage for concise command-line validation."""
    return asdict(price_coverage(conn, ticker))
