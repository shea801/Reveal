"""SEC filing metadata and backtest-support persistence helpers."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
import datetime as dt
import json
from pathlib import Path
import sqlite3
import zipfile


SEC_FILING_TABLE = "sec_filing_metadata"
SEC_IDENTITY_TABLE = "sec_ticker_cik_identity"
SEC_MATCH_TABLE = "sec_statement_matches"

ANNUAL_FORMS = frozenset({"10-K", "10-KT", "20-F", "40-F"})
QUARTERLY_FORMS = frozenset({"10-Q", "10-QT"})
FOREIGN_INTERIM_FORMS = frozenset({"6-K"})
PERIODIC_FORMS = ANNUAL_FORMS | QUARTERLY_FORMS | FOREIGN_INTERIM_FORMS
IMPORT_FORMS = PERIODIC_FORMS | {f"{form}/A" for form in PERIODIC_FORMS}


def create_sec_metadata_schema(conn: sqlite3.Connection) -> None:
    """Create normalized SEC filing, identity, and statement-match tables."""
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {SEC_FILING_TABLE} (
            cik TEXT NOT NULL,
            accession_number TEXT NOT NULL,
            form TEXT NOT NULL,
            report_date TEXT,
            filing_date TEXT NOT NULL,
            acceptance_datetime_utc TEXT NOT NULL,
            primary_document TEXT,
            source_member TEXT NOT NULL,
            is_amendment INTEGER NOT NULL DEFAULT 0
                CHECK (is_amendment IN (0, 1)),
            imported_at_utc TEXT NOT NULL,
            PRIMARY KEY (cik, accession_number)
        )
    """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_sec_filing_report
        ON {SEC_FILING_TABLE}(cik, report_date, form)
    """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_sec_filing_acceptance
        ON {SEC_FILING_TABLE}(cik, acceptance_datetime_utc)
    """)

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {SEC_IDENTITY_TABLE} (
            ticker TEXT NOT NULL,
            cik TEXT NOT NULL,
            valid_from TEXT,
            valid_to TEXT,
            is_current INTEGER NOT NULL DEFAULT 0
                CHECK (is_current IN (0, 1)),
            confidence TEXT NOT NULL
                CHECK (confidence IN ('high', 'medium', 'low')),
            source TEXT NOT NULL,
            notes TEXT,
            PRIMARY KEY (ticker, cik)
        )
    """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_sec_identity_cik_dates
        ON {SEC_IDENTITY_TABLE}(cik, valid_from, valid_to)
    """)

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {SEC_MATCH_TABLE} (
            ticker TEXT NOT NULL,
            statement_scope TEXT NOT NULL
                CHECK (statement_scope IN ('annual', 'quarterly')),
            fiscal_date TEXT NOT NULL,
            source_reported_date TEXT,
            cik TEXT,
            accession_number TEXT,
            form TEXT,
            acceptance_datetime_utc TEXT,
            match_method TEXT NOT NULL,
            confidence TEXT NOT NULL
                CHECK (confidence IN ('high', 'medium', 'low', 'unresolved')),
            identity_status TEXT NOT NULL
                CHECK (identity_status IN (
                    'confirmed_current_cik',
                    'confirmed_historical_cik',
                    'predates_current_cik_history',
                    'ambiguous',
                    'unresolved'
                )),
            report_date_delta_days INTEGER,
            reported_date_delta_days INTEGER,
            matched_at_utc TEXT NOT NULL,
            PRIMARY KEY (ticker, statement_scope, fiscal_date),
            FOREIGN KEY (cik, accession_number)
                REFERENCES sec_filing_metadata(cik, accession_number)
        )
    """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_sec_match_availability
        ON {SEC_MATCH_TABLE}(
            ticker, statement_scope, fiscal_date, acceptance_datetime_utc
        )
    """)

    conn.commit()


def normalize_cik(value: object) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    if not digits:
        raise ValueError("CIK must contain at least one digit")
    return digits.zfill(10)


def seed_current_ticker_identities(
    conn: sqlite3.Connection,
    tickers: Iterable[str] | None = None,
) -> list[tuple[str, str]]:
    """Seed present-day ticker/CIK mappings without inventing valid-from dates."""
    create_sec_metadata_schema(conn)
    params: list[str] = []
    sql = "SELECT ticker, cik FROM sec_tickers"
    normalized = _normalize_tickers(tickers or [])
    if normalized:
        placeholders = ",".join("?" for _ in normalized)
        sql += f" WHERE ticker IN ({placeholders})"
        params.extend(normalized)
    sql += " ORDER BY ticker"
    mappings = [
        (str(row["ticker"]).upper(), normalize_cik(row["cik"]))
        for row in conn.execute(sql, params).fetchall()
    ]
    conn.executemany(f"""
        INSERT INTO {SEC_IDENTITY_TABLE} (
            ticker, cik, valid_from, valid_to, is_current,
            confidence, source, notes
        ) VALUES (?, ?, NULL, NULL, 1, 'medium', 'sec_tickers', ?)
        ON CONFLICT(ticker, cik) DO UPDATE SET
            is_current = 1,
            source = excluded.source,
            notes = COALESCE({SEC_IDENTITY_TABLE}.notes, excluded.notes)
    """, [
        (
            ticker,
            cik,
            "Current registry mapping; historical validity is not implied.",
        )
        for ticker, cik in mappings
    ])
    conn.commit()
    return mappings


def upsert_ticker_identity(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    cik: str,
    valid_from: str | None,
    valid_to: str | None,
    is_current: bool,
    confidence: str,
    source: str,
    notes: str | None = None,
) -> None:
    """Add a researched historical identity interval."""
    if confidence not in {"high", "medium", "low"}:
        raise ValueError("confidence must be high, medium, or low")
    if valid_from and valid_to and valid_from > valid_to:
        raise ValueError("valid_from cannot be after valid_to")
    create_sec_metadata_schema(conn)
    conn.execute(f"""
        INSERT INTO {SEC_IDENTITY_TABLE} (
            ticker, cik, valid_from, valid_to, is_current,
            confidence, source, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, cik) DO UPDATE SET
            valid_from = excluded.valid_from,
            valid_to = excluded.valid_to,
            is_current = excluded.is_current,
            confidence = excluded.confidence,
            source = excluded.source,
            notes = excluded.notes
    """, (
        ticker.strip().upper(), normalize_cik(cik), valid_from, valid_to,
        int(is_current), confidence, source, notes,
    ))
    conn.commit()


def import_sec_submissions_archive(
    conn: sqlite3.Connection,
    archive_path: str | Path,
    tickers: Iterable[str] | None = None,
    forms: Iterable[str] = IMPORT_FORMS,
) -> dict[str, int]:
    """Import relevant filings for mapped tickers from SEC submissions.zip."""
    archive = Path(archive_path)
    if not archive.is_file():
        raise FileNotFoundError(f"SEC submissions archive not found: {archive}")
    create_sec_metadata_schema(conn)
    mappings = seed_current_ticker_identities(conn, tickers=tickers)
    wanted_forms = {str(form).upper() for form in forms}
    imported_at = _utc_now()
    row_count = 0
    member_count = 0
    cik_count = 0

    with zipfile.ZipFile(archive) as submissions:
        names = submissions.NameToInfo
        for cik in sorted({cik for _, cik in mappings}):
            main_member = f"CIK{cik}.json"
            if main_member not in names:
                continue
            cik_count += 1
            main_payload = _load_json_member(submissions, main_member)
            member_payloads = [
                (main_member, main_payload.get("filings", {}).get("recent", {}))
            ]
            for file_record in main_payload.get("filings", {}).get("files", []):
                member = file_record.get("name")
                if member and member in names:
                    member_payloads.append(
                        (member, _load_json_member(submissions, member))
                    )

            rows = []
            for member, payload in member_payloads:
                member_count += 1
                for filing in _iter_columnar_records(payload):
                    form = str(filing.get("form") or "").upper()
                    if form not in wanted_forms:
                        continue
                    row = _normalize_filing_row(
                        cik=cik,
                        filing=filing,
                        source_member=member,
                        imported_at=imported_at,
                    )
                    if row is not None:
                        rows.append(row)
            if rows:
                conn.executemany(f"""
                    INSERT INTO {SEC_FILING_TABLE} (
                        cik, accession_number, form, report_date, filing_date,
                        acceptance_datetime_utc, primary_document,
                        source_member, is_amendment, imported_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cik, accession_number) DO UPDATE SET
                        form = excluded.form,
                        report_date = excluded.report_date,
                        filing_date = excluded.filing_date,
                        acceptance_datetime_utc = excluded.acceptance_datetime_utc,
                        primary_document = excluded.primary_document,
                        source_member = excluded.source_member,
                        is_amendment = excluded.is_amendment,
                        imported_at_utc = excluded.imported_at_utc
                """, rows)
                row_count += len(rows)
            conn.commit()

    return {
        "mapped_ticker_count": len(mappings),
        "imported_cik_count": cik_count,
        "archive_member_count": member_count,
        "upserted_filing_count": row_count,
    }


def _iter_columnar_records(payload: Mapping[str, object]) -> Iterator[dict]:
    columns = {
        key: value
        for key, value in payload.items()
        if isinstance(value, list)
    }
    if not columns:
        return
    row_count = max(len(values) for values in columns.values())
    for index in range(row_count):
        yield {
            key: values[index] if index < len(values) else None
            for key, values in columns.items()
        }


def _normalize_filing_row(
    *,
    cik: str,
    filing: Mapping[str, object],
    source_member: str,
    imported_at: str,
) -> tuple | None:
    accession = str(filing.get("accessionNumber") or "").strip()
    form = str(filing.get("form") or "").strip().upper()
    filing_date = str(filing.get("filingDate") or "").strip()
    acceptance = _normalize_acceptance_datetime(
        filing.get("acceptanceDateTime"),
    )
    if not accession or not form or not _is_iso_date(filing_date) or not acceptance:
        return None
    report_date = str(filing.get("reportDate") or "").strip() or None
    if report_date and not _is_iso_date(report_date):
        report_date = None
    primary_document = str(filing.get("primaryDocument") or "").strip() or None
    return (
        normalize_cik(cik), accession, form, report_date, filing_date,
        acceptance, primary_document, source_member, int(form.endswith("/A")),
        imported_at,
    )


def _load_json_member(submissions: zipfile.ZipFile, member: str) -> dict:
    with submissions.open(member) as source:
        value = json.load(source)
    return value if isinstance(value, dict) else {}


def _normalize_acceptance_datetime(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if len(raw) == 14 and raw.isdigit():
        parsed = dt.datetime.strptime(raw, "%Y%m%d%H%M%S").replace(
            tzinfo=dt.timezone.utc
        )
        return parsed.isoformat().replace("+00:00", "Z")
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_tickers(tickers: Iterable[str]) -> list[str]:
    return sorted({
        ticker.strip().upper()
        for ticker in tickers
        if isinstance(ticker, str) and ticker.strip()
    })


def _is_iso_date(value: str) -> bool:
    try:
        dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
