"""Recurring local security data update job.

This module coordinates the existing data_access classes with a small amount
of bookkeeping so the job can be run repeatedly from cron, launchd, or a shell.
It intentionally does not download the entire SEC ticker universe on first run.
Instead, it updates securities that are already stored locally and tracks the
SEC ticker registry so future runs can detect genuinely new registry entries.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import sqlite3
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from runtime_config import get_data_root, investment_db_path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass(frozen=True)
class SecurityRecord:
    ticker: str
    title: str | None = None
    cik: str | None = None


@dataclass(frozen=True)
class ExistingUpdatePlan:
    update_ohlcv: bool
    update_financials: bool
    is_equity: bool
    reason: str


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def normalize_ticker(ticker: str | None) -> str | None:
    if not ticker or not isinstance(ticker, str):
        return None
    return ticker.strip().upper() or None


def load_sec_tickers() -> dict[str, SecurityRecord]:
    path = get_data_root() / "company_tickers.json"
    if not path.is_file():
        raise FileNotFoundError("SEC ticker file is missing: company_tickers.json")

    with path.open("r", encoding="utf-8") as handle:
        raw_data = json.load(handle)

    records: dict[str, SecurityRecord] = {}
    for key, value in raw_data.items():
        if not str(key).isnumeric() or not isinstance(value, dict):
            continue
        ticker = normalize_ticker(value.get("ticker"))
        if not ticker:
            continue
        cik_raw = value.get("cik_str")
        cik = str(cik_raw).zfill(10) if cik_raw is not None else None
        records[ticker] = SecurityRecord(
            ticker=ticker,
            title=value.get("title"),
            cik=cik,
        )
    return records


def _ticker_from_directory_name(name: str) -> str | None:
    if not name or name.startswith("."):
        return None
    return normalize_ticker(name.split("__", 1)[0])


def local_security_records() -> dict[str, SecurityRecord]:
    records: dict[str, SecurityRecord] = {}
    for root_dir in (
        get_data_root() / "Securities",
        get_data_root() / "ETF_Securities",
    ):
        if not root_dir.is_dir():
            continue
        for child in root_dir.iterdir():
            if not child.is_dir():
                continue
            ticker = _ticker_from_directory_name(child.name)
            if not ticker:
                continue
            title = child.name.split("__", 1)[1] if "__" in child.name else None
            records[ticker] = SecurityRecord(ticker=ticker, title=title)
    return records


def connect_db() -> sqlite3.Connection:
    path = investment_db_path()
    if not path.is_file():
        raise FileNotFoundError("Investment database is missing: Securities_DB/investment.db")
    conn = sqlite3.connect(f"{path.as_uri()}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_tracking_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sec_ticker_registry_state (
            ticker TEXT PRIMARY KEY,
            cik TEXT,
            title TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS inactive_security_symbols (
            ticker TEXT PRIMARY KEY,
            cik TEXT,
            title TEXT,
            status TEXT NOT NULL,
            reason TEXT,
            first_detected_at TEXT NOT NULL,
            last_checked_at TEXT NOT NULL,
            last_error TEXT,
            attempts INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS security_update_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            dry_run INTEGER NOT NULL DEFAULT 0,
            requested_tickers TEXT,
            updated_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            skipped_count INTEGER NOT NULL DEFAULT 0,
            new_count INTEGER NOT NULL DEFAULT 0,
            inactive_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS security_update_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES security_update_runs(run_id)
        );
        """
    )
    conn.commit()


def seed_or_update_sec_registry(
    conn: sqlite3.Connection,
    sec_records: dict[str, SecurityRecord],
) -> tuple[set[str], set[str], bool]:
    now = utc_now()
    existing_rows = conn.execute(
        "SELECT ticker, is_active FROM sec_ticker_registry_state"
    ).fetchall()
    existing = {row["ticker"]: row for row in existing_rows}
    first_registry_run = not existing
    current = set(sec_records)
    previously_known = set(existing)

    for ticker, record in sec_records.items():
        if ticker in existing:
            conn.execute(
                """
                UPDATE sec_ticker_registry_state
                SET cik = ?, title = ?, last_seen_at = ?, is_active = 1
                WHERE ticker = ?
                """,
                (record.cik, record.title, now, ticker),
            )
        else:
            conn.execute(
                """
                INSERT INTO sec_ticker_registry_state
                    (ticker, cik, title, first_seen_at, last_seen_at, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (ticker, record.cik, record.title, now, now),
            )

    removed = previously_known - current
    for ticker in removed:
        conn.execute(
            """
            UPDATE sec_ticker_registry_state
            SET last_seen_at = ?, is_active = 0
            WHERE ticker = ?
            """,
            (now, ticker),
        )

    conn.commit()
    new_since_last_run = set() if first_registry_run else current - previously_known
    return new_since_last_run, removed, first_registry_run


def upsert_inactive_symbol(
    conn: sqlite3.Connection,
    record: SecurityRecord,
    status: str,
    reason: str,
    last_error: str | None = None,
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO inactive_security_symbols
            (ticker, cik, title, status, reason, first_detected_at,
             last_checked_at, last_error, attempts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(ticker) DO UPDATE SET
            cik = excluded.cik,
            title = COALESCE(excluded.title, inactive_security_symbols.title),
            status = excluded.status,
            reason = excluded.reason,
            last_checked_at = excluded.last_checked_at,
            last_error = excluded.last_error,
            attempts = inactive_security_symbols.attempts + 1
        """,
        (
            record.ticker,
            record.cik,
            record.title,
            status,
            reason,
            now,
            now,
            last_error,
        ),
    )
    conn.commit()


def remove_inactive_symbol(conn: sqlite3.Connection, ticker: str) -> None:
    conn.execute("DELETE FROM inactive_security_symbols WHERE ticker = ?", (ticker,))
    conn.commit()


def record_event(
    conn: sqlite3.Connection,
    run_id: int,
    ticker: str,
    event_type: str,
    status: str,
    message: str,
) -> None:
    conn.execute(
        """
        INSERT INTO security_update_events
            (run_id, ticker, event_type, status, message, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, ticker, event_type, status, message, utc_now()),
    )
    conn.commit()


def insert_sec_ticker(conn: sqlite3.Connection, record: SecurityRecord) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sec_tickers (
            ticker TEXT PRIMARY KEY,
            cik TEXT NOT NULL,
            title TEXT
        )
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO sec_tickers (ticker, cik, title) VALUES (?, ?, ?)",
        (record.ticker, record.cik or "", record.title),
    )
    conn.commit()


def snapshot_files(ticker: str) -> dict[str, int]:
    paths: dict[str, int] = {}
    _, TickerSearch = import_ingestion_classes()

    try:
        file_pathways = TickerSearch().ticker_file_pathways(ticker)
    except Exception:
        file_pathways = {}

    candidate_paths: list[str] = [
        str((get_data_root() / "All_Tickers_Searched") / f"{ticker}_ticker_search_info.json")
    ]

    def add_path(value: object) -> None:
        if isinstance(value, str):
            candidate_paths.append(value)
        elif isinstance(value, dict):
            for child_value in value.values():
                add_path(child_value)

    for value in file_pathways.values():
        add_path(value)

    for candidate in candidate_paths:
        path = Path(candidate)
        if not path.is_file():
            continue
        try:
            paths[str(path)] = path.stat().st_mtime_ns
        except OSError:
            continue

    return paths


def files_changed(before: dict[str, int], after: dict[str, int]) -> bool:
    if set(before) != set(after):
        return True
    return any(before[path] != after[path] for path in before)


def parse_iso_date(value: object) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def month_number(month_name: str | None) -> int:
    if not month_name:
        return 12
    month_lookup = {name: index for index, name in enumerate(calendar.month_name) if name}
    return month_lookup.get(str(month_name).strip().title(), 12)


def fiscal_year_end_after(latest_annual_date: dt.date, fiscal_year_end_month: int) -> dt.date:
    year = latest_annual_date.year + 1
    last_day = calendar.monthrange(year, fiscal_year_end_month)[1]
    return dt.date(year, fiscal_year_end_month, last_day)


def infer_security_type(ticker: str) -> str | None:
    search_path = (get_data_root() / "All_Tickers_Searched") / f"{ticker}_ticker_search_info.json"
    if not search_path.is_file() or search_path.stat().st_size <= 2:
        return None
    try:
        with search_path.open("r", encoding="utf-8") as handle:
            search_data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(search_data, dict):
        return None
    return search_data.get("3. type")


def build_existing_update_plan(
    ticker: str,
    ohlcv_max_age_days: int,
    quarterly_grace_days: int,
    annual_grace_days: int,
) -> ExistingUpdatePlan:
    from data_access.CompanyDetails import CompanyDetails
    from data_access.OHLCVPriceData import OHLCVPriceData

    today = dt.date.today()
    reasons: list[str] = []

    try:
        latest_price = OHLCVPriceData(ticker).latest_price()
    except Exception:
        latest_price = None

    latest_price_date = parse_iso_date(latest_price.get("date")) if latest_price else None
    adjusted_close = latest_price.get("adjusted_close") if latest_price else None
    if latest_price_date is None:
        update_ohlcv = True
        reasons.append("no OHLCV record in database")
    elif adjusted_close is None:
        update_ohlcv = True
        reasons.append("adjusted OHLCV backfill required")
    else:
        ohlcv_age = (today - latest_price_date).days
        update_ohlcv = ohlcv_age >= ohlcv_max_age_days
        if update_ohlcv:
            reasons.append(f"OHLCV is {ohlcv_age} days old")
        else:
            reasons.append(f"OHLCV fresh: latest price {latest_price_date.isoformat()}")

    company_details = CompanyDetails(ticker)
    details = company_details.get_details()
    security_type = infer_security_type(ticker)
    asset_type = details.get("AssetType") if details else None
    is_equity = security_type == "Equity" or asset_type in ("Common Stock", "Equity")

    if not is_equity:
        reasons.append("not an equity; financial statements skipped")
        return ExistingUpdatePlan(update_ohlcv, False, False, "; ".join(reasons))

    latest_quarterly = parse_iso_date(company_details.get_latest_quarterly_fiscal_date())
    if latest_quarterly is None:
        quarterly_due = True
        reasons.append("no quarterly financial date in database")
    else:
        next_quarter_check = latest_quarterly + dt.timedelta(days=90 + quarterly_grace_days)
        quarterly_due = today >= next_quarter_check
        if quarterly_due:
            reasons.append(
                f"quarterly due: latest fiscal date {latest_quarterly.isoformat()}, "
                f"check date {next_quarter_check.isoformat()}"
            )
        else:
            reasons.append(f"quarterly fresh: latest fiscal date {latest_quarterly.isoformat()}")

    latest_annual = parse_iso_date(company_details.get_latest_annual_fiscal_date())
    if latest_annual is None:
        annual_due = True
        reasons.append("no annual financial date in database")
    else:
        fiscal_month = month_number(company_details.get_fiscal_year_end())
        next_fy_end = fiscal_year_end_after(latest_annual, fiscal_month)
        annual_check_date = next_fy_end + dt.timedelta(days=annual_grace_days)
        annual_due = today >= annual_check_date
        if annual_due:
            reasons.append(
                f"annual due: latest fiscal date {latest_annual.isoformat()}, "
                f"check date {annual_check_date.isoformat()}"
            )
        else:
            reasons.append(f"annual fresh: latest fiscal date {latest_annual.isoformat()}")

    return ExistingUpdatePlan(
        update_ohlcv=update_ohlcv,
        update_financials=quarterly_due or annual_due,
        is_equity=True,
        reason="; ".join(reasons),
    )


def import_ingestion_classes():
    from data_ingestion.DataExtraction import DataExtraction
    from data_ingestion.TickerFileSearch import TickerSearch

    return DataExtraction, TickerSearch


def bootstrap_ticker_search_file(
    ticker: str,
    title: str | None,
    dry_run: bool,
) -> tuple[dict | None, str]:
    DataExtraction, _ = import_ingestion_classes()
    search_path = (get_data_root() / "All_Tickers_Searched") / f"{ticker}_ticker_search_info.json"
    if search_path.is_file() and search_path.stat().st_size > 2:
        with search_path.open("r", encoding="utf-8") as handle:
            return json.load(handle), "existing ticker search file"

    if dry_run:
        return None, "dry run would fetch Alpha Vantage symbol search"

    (get_data_root() / "All_Tickers_Searched").mkdir(parents=True, exist_ok=True)
    extractor = DataExtraction(ticker=ticker)
    search_data = extractor.search_ticker_alphavantage_api_call()
    if not search_data or not isinstance(search_data, dict):
        return None, "Alpha Vantage symbol search returned no match"

    if search_data.get("3. type") not in ("ETF", "Equity"):
        return search_data, f"unsupported Alpha Vantage type: {search_data.get('3. type')}"

    if search_data.get("1. symbol") != ticker and search_data.get("2. name") == ticker.title():
        search_data["1. symbol"] = ticker
        if title:
            search_data["2. name"] = title

    if search_data.get("1. symbol") != ticker:
        return search_data, "Alpha Vantage symbol mismatch"

    with search_path.open("w", encoding="utf-8") as handle:
        json.dump(search_data, handle)
    return search_data, "created ticker search file"


def bootstrap_new_security(
    conn: sqlite3.Connection,
    run_id: int,
    record: SecurityRecord,
    dry_run: bool,
) -> bool:
    DataExtraction, TickerSearch = import_ingestion_classes()
    ticker = record.ticker
    search_data, search_msg = bootstrap_ticker_search_file(ticker, record.title, dry_run)
    if not search_data:
        upsert_inactive_symbol(conn, record, "no_alpha_vantage_match", search_msg)
        record_event(conn, run_id, ticker, "new_security", "skipped", search_msg)
        return False

    security_type = search_data.get("3. type")
    if security_type not in ("ETF", "Equity"):
        upsert_inactive_symbol(conn, record, "unsupported_security_type", search_msg)
        record_event(conn, run_id, ticker, "new_security", "skipped", search_msg)
        return False

    if dry_run:
        record_event(conn, run_id, ticker, "new_security", "dry_run", search_msg)
        return True

    insert_sec_ticker(conn, record)
    extractor = DataExtraction(ticker=ticker)
    ticker_search = TickerSearch()
    pathways = ticker_search.ticker_file_pathways(ticker)

    extractor.price_history_api_call_to_file()
    if security_type == "ETF":
        extractor.etf_profile_api_call_to_file()
    else:
        details = extractor.company_details_api_call()
        company_details_path = pathways.get("company_details")
        if details and isinstance(company_details_path, str):
            Path(company_details_path).parent.mkdir(parents=True, exist_ok=True)
            with open(company_details_path, "w", encoding="utf-8") as handle:
                json.dump(details, handle)
        for key in ("balance", "cash", "income", "earnings"):
            result = extractor.financials_api_call_to_file(key)
            if result is False:
                break

    try:
        from Securities_DB.create_database import (
            update_company_details_for_ticker,
            update_financials_for_ticker,
            update_market_capitalization_for_ticker,
            update_ohlcv_for_ticker,
        )

        update_ohlcv_for_ticker(ticker)
        if security_type == "Equity":
            update_company_details_for_ticker(ticker)
            update_financials_for_ticker(ticker)
            update_market_capitalization_for_ticker(ticker)
    except Exception as exc:
        record_event(conn, run_id, ticker, "database_load", "failed", repr(exc))
        raise

    remove_inactive_symbol(conn, ticker)
    record_event(conn, run_id, ticker, "new_security", "updated", search_msg)
    return True


def update_existing_security(
    conn: sqlite3.Connection,
    run_id: int,
    record: SecurityRecord,
    dry_run: bool,
    ohlcv_max_age_days: int,
    quarterly_grace_days: int,
    annual_grace_days: int,
) -> bool:
    DataExtraction, _ = import_ingestion_classes()
    ticker = record.ticker
    plan = build_existing_update_plan(
        ticker,
        ohlcv_max_age_days=ohlcv_max_age_days,
        quarterly_grace_days=quarterly_grace_days,
        annual_grace_days=annual_grace_days,
    )

    if dry_run:
        status = "would_update" if plan.update_ohlcv or plan.update_financials else "would_skip"
        record_event(conn, run_id, ticker, "existing_security", status, plan.reason)
        return plan.update_ohlcv or plan.update_financials

    if not plan.update_ohlcv and not plan.update_financials:
        remove_inactive_symbol(conn, ticker)
        record_event(conn, run_id, ticker, "existing_security", "skipped", plan.reason)
        return False

    before = snapshot_files(ticker)
    extractor = DataExtraction(ticker=ticker)

    if plan.update_ohlcv:
        from Securities_DB.create_database import update_ohlcv_for_ticker

        extractor.price_history_api_call_to_file()
        update_ohlcv_for_ticker(ticker)

    if plan.update_financials:
        from Securities_DB.create_database import (
            update_company_details_for_ticker,
            update_financials_for_ticker,
            update_market_capitalization_for_ticker,
        )

        details = extractor.company_details_api_call()
        _, TickerSearch = import_ingestion_classes()
        pathways = TickerSearch().ticker_file_pathways(ticker)
        company_details_path = pathways.get("company_details")
        if details and isinstance(company_details_path, str):
            Path(company_details_path).parent.mkdir(parents=True, exist_ok=True)
            with open(company_details_path, "w", encoding="utf-8") as handle:
                json.dump(details, handle)

        for fin_key in ("balance", "cash", "income", "earnings"):
            result = extractor.financials_api_call_to_file(fin_key)
            if result is False:
                break

        update_company_details_for_ticker(ticker)
        update_financials_for_ticker(ticker)
        update_market_capitalization_for_ticker(ticker)

    after = snapshot_files(ticker)

    if files_changed(before, after):
        remove_inactive_symbol(conn, ticker)
        record_event(conn, run_id, ticker, "existing_security", "updated", plan.reason)
        return True

    upsert_inactive_symbol(
        conn,
        record,
        "no_new_information",
        f"update completed but no local files changed; {plan.reason}",
    )
    record_event(
        conn,
        run_id,
        ticker,
        "existing_security",
        "no_change",
        f"update completed but no local files changed; {plan.reason}",
    )
    return False


def select_records(
    tickers: Iterable[str],
    sec_records: dict[str, SecurityRecord],
    local_records: dict[str, SecurityRecord],
) -> list[SecurityRecord]:
    selected = []
    for raw_ticker in tickers:
        ticker = normalize_ticker(raw_ticker)
        if not ticker:
            continue
        selected.append(sec_records.get(ticker) or local_records.get(ticker) or SecurityRecord(ticker=ticker))
    return selected


def run_update(args: argparse.Namespace) -> int:
    sec_records = load_sec_tickers()
    local_records = local_security_records()

    conn = connect_db()
    ensure_tracking_tables(conn)

    requested_tickers = ",".join(args.tickers or [])
    run_id = conn.execute(
        """
        INSERT INTO security_update_runs (started_at, dry_run, requested_tickers)
        VALUES (?, ?, ?)
        """,
        (utc_now(), int(args.dry_run), requested_tickers),
    ).lastrowid
    conn.commit()

    counters = {
        "updated_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "new_count": 0,
        "inactive_count": 0,
    }

    try:
        new_tickers, removed_tickers, first_registry_run = seed_or_update_sec_registry(conn, sec_records)

        for ticker in sorted(removed_tickers | (set(local_records) - set(sec_records))):
            record = local_records.get(ticker) or SecurityRecord(ticker=ticker)
            upsert_inactive_symbol(conn, record, "delisted_or_removed_from_sec_registry", "ticker absent from current SEC company_tickers.json")
            record_event(conn, run_id, ticker, "registry_compare", "inactive", "ticker absent from current SEC company_tickers.json")
            counters["inactive_count"] += 1

        if args.tickers:
            existing_records = select_records(args.tickers, sec_records, local_records)
            new_records = []
        else:
            existing_records = [
                sec_records.get(ticker) or local_records[ticker]
                for ticker in sorted(local_records)
                if ticker in sec_records
            ]
            if first_registry_run and not args.bootstrap_new_from_sec:
                new_records = []
            else:
                new_source = set(sec_records) - set(local_records) if args.bootstrap_new_from_sec else new_tickers
                new_records = [sec_records[ticker] for ticker in sorted(new_source)]

        if args.max_existing is not None:
            existing_records = existing_records[: args.max_existing]
        if args.max_new is not None:
            new_records = new_records[: args.max_new]

        print("Reveal data root configured.")
        print(f"Database: {investment_db_path()}")
        print(f"Existing securities queued: {len(existing_records)}")
        print(f"New SEC securities queued: {len(new_records)}")
        if first_registry_run and not args.bootstrap_new_from_sec:
            print("Initialized SEC registry state. Future runs will detect new SEC tickers.")

        for record in existing_records:
            try:
                if not args.dry_run:
                    insert_sec_ticker(conn, record)
                changed = update_existing_security(
                    conn,
                    run_id,
                    record,
                    args.dry_run,
                    ohlcv_max_age_days=args.ohlcv_max_age_days,
                    quarterly_grace_days=args.quarterly_grace_days,
                    annual_grace_days=args.annual_grace_days,
                )
                counters["updated_count" if changed else "skipped_count"] += 1
            except Exception as exc:
                counters["failed_count"] += 1
                message = f"{type(exc).__name__}: {exc}"
                upsert_inactive_symbol(conn, record, "update_failed", "exception during existing security update", message)
                record_event(conn, run_id, record.ticker, "existing_security", "failed", message)
                if args.stop_on_error:
                    raise
                traceback.print_exc()

        for record in new_records:
            try:
                created = bootstrap_new_security(conn, run_id, record, args.dry_run)
                counters["new_count" if created else "skipped_count"] += 1
            except Exception as exc:
                counters["failed_count"] += 1
                message = f"{type(exc).__name__}: {exc}"
                upsert_inactive_symbol(conn, record, "new_security_failed", "exception during new security bootstrap", message)
                record_event(conn, run_id, record.ticker, "new_security", "failed", message)
                if args.stop_on_error:
                    raise
                traceback.print_exc()

        return 0 if counters["failed_count"] == 0 else 1
    finally:
        conn.execute(
            """
            UPDATE security_update_runs
            SET finished_at = ?,
                updated_count = ?,
                failed_count = ?,
                skipped_count = ?,
                new_count = ?,
                inactive_count = ?
            WHERE run_id = ?
            """,
            (
                utc_now(),
                counters["updated_count"],
                counters["failed_count"],
                counters["skipped_count"],
                counters["new_count"],
                counters["inactive_count"],
                run_id,
            ),
        )
        conn.commit()
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update locally stored Investment security data."
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        help="Optional ticker symbols to update instead of the full local set.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create/check bookkeeping and print what would run without Alpha Vantage downloads.",
    )
    parser.add_argument(
        "--max-existing",
        type=int,
        default=None,
        help="Limit the number of existing local securities updated in this run.",
    )
    parser.add_argument(
        "--max-new",
        type=int,
        default=None,
        help="Limit the number of new SEC ticker additions bootstrapped in this run.",
    )
    parser.add_argument(
        "--bootstrap-new-from-sec",
        action="store_true",
        help="Treat every SEC ticker not stored locally as a candidate new security.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the run at the first ticker update failure.",
    )
    parser.add_argument(
        "--ohlcv-max-age-days",
        type=int,
        default=7,
        help="Refresh OHLCV only when the latest database price is at least this many days old.",
    )
    parser.add_argument(
        "--quarterly-grace-days",
        type=int,
        default=45,
        help="Wait this many days after the expected next quarter before refreshing financial statements.",
    )
    parser.add_argument(
        "--annual-grace-days",
        type=int,
        default=75,
        help="Wait this many days after fiscal year end before refreshing annual financial statements.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_update(args)


if __name__ == "__main__":
    raise SystemExit(main())
