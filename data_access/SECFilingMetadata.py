"""Point-in-time access and matching for locally imported SEC filings."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import datetime as dt
import sqlite3

from Securities_DB.sec_metadata_database import (
    ANNUAL_FORMS,
    FOREIGN_INTERIM_FORMS,
    QUARTERLY_FORMS,
    SEC_FILING_TABLE,
    SEC_IDENTITY_TABLE,
    SEC_MATCH_TABLE,
    create_sec_metadata_schema,
)


USABLE_BACKTEST_CONFIDENCE = frozenset({"high", "medium"})


def source_statement_periods(
    conn: sqlite3.Connection,
    tickers: Iterable[str] | None = None,
) -> list[dict]:
    """Return source fiscal dates needed by annual and TTM calculations."""
    normalized = _normalize_tickers(tickers or [])
    params: list[str] = []
    ticker_filter = ""
    if normalized:
        placeholders = ",".join("?" for _ in normalized)
        ticker_filter = f" AND ticker IN ({placeholders})"
        params.extend(normalized)

    annual_sql = f"""
        WITH annual_periods AS (
            SELECT ticker, fiscalDateEnding FROM balance_sheet_annual
            UNION
            SELECT ticker, fiscalDateEnding FROM cash_flow_annual
            UNION
            SELECT ticker, fiscalDateEnding FROM income_annual
            UNION
            SELECT ticker, fiscalDateEnding FROM earnings_annual
        )
        SELECT ticker, 'annual' AS statement_scope,
               fiscalDateEnding AS fiscal_date,
               NULL AS source_reported_date
        FROM annual_periods
        WHERE fiscalDateEnding IS NOT NULL {ticker_filter}
    """
    annual_rows = conn.execute(annual_sql, params).fetchall()

    quarterly_params: list[str] = []
    quarterly_filter = ""
    if normalized:
        placeholders = ",".join("?" for _ in normalized)
        quarterly_filter = f" AND i.ticker IN ({placeholders})"
        quarterly_params.extend(normalized)
    quarterly_rows = conn.execute(f"""
        SELECT i.ticker, 'quarterly' AS statement_scope,
               i.fiscalDateEnding AS fiscal_date,
               e.reportedDate AS source_reported_date
        FROM income_quarterly AS i
        INNER JOIN earnings_quarterly AS e
            ON e.ticker = i.ticker
           AND e.fiscalDateEnding = i.fiscalDateEnding
        WHERE i.fiscalDateEnding IS NOT NULL {quarterly_filter}
    """, quarterly_params).fetchall()

    unique = {}
    for row in [*annual_rows, *quarterly_rows]:
        record = dict(row)
        key = (
            str(record["ticker"]).upper(),
            record["statement_scope"],
            record["fiscal_date"],
        )
        unique[key] = {
            "ticker": key[0],
            "statement_scope": key[1],
            "fiscal_date": key[2],
            "source_reported_date": record.get("source_reported_date"),
        }
    return [unique[key] for key in sorted(unique)]


def match_source_statements(
    conn: sqlite3.Connection,
    tickers: Iterable[str] | None = None,
) -> dict[str, int]:
    """Match local fiscal periods to SEC accessions with auditable confidence."""
    create_sec_metadata_schema(conn)
    periods = source_statement_periods(conn, tickers=tickers)
    identities = _load_identities(conn)
    filings = _load_filings(conn)
    now = _utc_now()
    records = []
    counts = {"high": 0, "medium": 0, "low": 0, "unresolved": 0}

    for period in periods:
        identity = _identity_for_date(
            identities.get(period["ticker"], []),
            period["fiscal_date"],
        )
        match = _match_period(
            period,
            identity,
            filings.get(identity["cik"], []) if identity else [],
        )
        match["matched_at_utc"] = now
        counts[match["confidence"]] += 1
        records.append(match)

    if records:
        conn.executemany(f"""
            INSERT INTO {SEC_MATCH_TABLE} (
                ticker, statement_scope, fiscal_date, source_reported_date,
                cik, accession_number, form, acceptance_datetime_utc,
                match_method, confidence, identity_status,
                report_date_delta_days, reported_date_delta_days,
                matched_at_utc
            ) VALUES (
                :ticker, :statement_scope, :fiscal_date,
                :source_reported_date, :cik, :accession_number, :form,
                :acceptance_datetime_utc, :match_method, :confidence,
                :identity_status, :report_date_delta_days,
                :reported_date_delta_days, :matched_at_utc
            )
            ON CONFLICT(ticker, statement_scope, fiscal_date) DO UPDATE SET
                source_reported_date = excluded.source_reported_date,
                cik = excluded.cik,
                accession_number = excluded.accession_number,
                form = excluded.form,
                acceptance_datetime_utc = excluded.acceptance_datetime_utc,
                match_method = excluded.match_method,
                confidence = excluded.confidence,
                identity_status = excluded.identity_status,
                report_date_delta_days = excluded.report_date_delta_days,
                reported_date_delta_days = excluded.reported_date_delta_days,
                matched_at_utc = excluded.matched_at_utc
        """, records)
        conn.commit()

    return {"statement_count": len(records), **counts}


def required_matches_for_quarter(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    quarter_date: str,
    associated_annual_date: str,
) -> list[dict]:
    """Return the annual match plus the latest four TTM quarterly matches."""
    annual = conn.execute(f"""
        SELECT *
        FROM {SEC_MATCH_TABLE}
        WHERE ticker = ?
          AND statement_scope = 'annual'
          AND fiscal_date = ?
        LIMIT 1
    """, (ticker.upper(), associated_annual_date)).fetchone()
    quarterly = conn.execute(f"""
        SELECT *
        FROM {SEC_MATCH_TABLE}
        WHERE ticker = ?
          AND statement_scope = 'quarterly'
          AND fiscal_date <= ?
        ORDER BY fiscal_date DESC
        LIMIT 4
    """, (ticker.upper(), quarter_date)).fetchall()
    rows = ([annual] if annual is not None else []) + list(quarterly)
    return [dict(row) for row in rows]


def annual_statement_availability_history(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    analysis_date: str | dt.date,
) -> list[dict]:
    """Return usable annual statement dates available by a common cutoff."""
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("ticker must be a non-empty string")
    cutoff = _as_date(analysis_date)
    rows = conn.execute(f"""
        SELECT *
        FROM {SEC_MATCH_TABLE}
        WHERE ticker = ?
          AND statement_scope = 'annual'
        ORDER BY fiscal_date DESC
    """, (ticker.strip().upper(),)).fetchall()

    history = []
    for row in rows:
        record = dict(row)
        if not is_usable_backtest_match(record):
            continue
        fiscal_date = _as_date(record["fiscal_date"])
        availability_date = _as_date(record["acceptance_datetime_utc"])
        if fiscal_date > cutoff or availability_date > cutoff:
            continue
        history.append({
            "ticker": record["ticker"],
            "annual_statement_date": fiscal_date.isoformat(),
            "statement_availability_date": availability_date.isoformat(),
            "acceptance_datetime_utc": record["acceptance_datetime_utc"],
            "confidence": record["confidence"],
            "identity_status": record["identity_status"],
        })
    return history


def is_usable_backtest_match(record: Mapping[str, object]) -> bool:
    return (
        record.get("confidence") in USABLE_BACKTEST_CONFIDENCE
        and record.get("identity_status") in {
            "confirmed_current_cik",
            "confirmed_historical_cik",
        }
        and bool(record.get("cik"))
        and bool(record.get("accession_number"))
        and bool(record.get("form"))
        and bool(record.get("acceptance_datetime_utc"))
    )


def _match_period(
    period: Mapping[str, object],
    identity: Mapping[str, object] | None,
    filings: list[dict],
) -> dict:
    base = {
        **period,
        "cik": identity.get("cik") if identity else None,
        "accession_number": None,
        "form": None,
        "acceptance_datetime_utc": None,
        "match_method": "unresolved",
        "confidence": "unresolved",
        "identity_status": "unresolved" if identity is None else "ambiguous",
        "report_date_delta_days": None,
        "reported_date_delta_days": None,
    }
    if identity is None:
        return base

    identity_status = (
        "confirmed_current_cik"
        if identity["is_current"]
        else "confirmed_historical_cik"
    )
    fiscal_date = _as_date(period["fiscal_date"])
    primary_forms = (
        ANNUAL_FORMS
        if period["statement_scope"] == "annual"
        else QUARTERLY_FORMS | ANNUAL_FORMS
    )
    primary = [
        filing
        for filing in filings
        if filing["form"] in primary_forms and not filing["is_amendment"]
    ]
    identity_history_filings = [
        filing
        for filing in filings
        if filing["form"] in (ANNUAL_FORMS | QUARTERLY_FORMS)
        and not filing["is_amendment"]
    ]
    earliest_report = min(
        (
            _as_date(filing["report_date"])
            for filing in identity_history_filings
            if filing["report_date"]
        ),
        default=None,
    )
    if (
        identity["is_current"]
        and earliest_report is not None
        and fiscal_date < earliest_report - dt.timedelta(days=31)
        and not identity.get("valid_from")
    ):
        base["identity_status"] = "predates_current_cik_history"
        base["match_method"] = "identity_history_boundary"
        return base

    report_candidates = []
    for filing in primary:
        if not filing["report_date"]:
            continue
        delta = (_as_date(filing["report_date"]) - fiscal_date).days
        if abs(delta) <= 31:
            report_candidates.append((
                abs(delta),
                filing["filing_date"],
                filing["accession_number"],
                filing,
                delta,
            ))
    if report_candidates:
        _, _, _, filing, report_delta = min(report_candidates)
        absolute_delta = abs(report_delta)
        if absolute_delta == 0:
            method, confidence = "report_date_exact", "high"
        elif absolute_delta <= 3:
            method, confidence = "report_date_near", "high"
        elif absolute_delta <= 14:
            method, confidence = "report_date_near", "medium"
        else:
            method, confidence = "report_date_near", "low"
        return _resolved_match(
            base,
            filing,
            method=method,
            confidence=confidence,
            identity_status=identity_status,
            report_delta=report_delta,
        )

    reported_date = period.get("source_reported_date")
    if reported_date:
        reported = _as_date(reported_date)
        reported_candidates = []
        for filing in primary:
            delta = (_as_date(filing["filing_date"]) - reported).days
            if -7 <= delta <= 45:
                reported_candidates.append((
                    abs(delta),
                    filing["filing_date"],
                    filing["accession_number"],
                    filing,
                    delta,
                ))
        if reported_candidates:
            _, _, _, filing, reported_delta = min(reported_candidates)
            return _resolved_match(
                base,
                filing,
                method="source_reported_date_to_filing",
                confidence="medium",
                identity_status=identity_status,
                reported_delta=reported_delta,
            )

        if period["statement_scope"] == "quarterly":
            six_k_candidates = []
            for filing in filings:
                if filing["form"] not in FOREIGN_INTERIM_FORMS:
                    continue
                delta = (_as_date(filing["filing_date"]) - reported).days
                if abs(delta) <= 7:
                    six_k_candidates.append((
                        abs(delta),
                        filing["filing_date"],
                        filing["accession_number"],
                        filing,
                        delta,
                    ))
            if six_k_candidates:
                _, _, _, filing, reported_delta = min(six_k_candidates)
                return _resolved_match(
                    base,
                    filing,
                    method="foreign_interim_reported_date",
                    confidence="low",
                    identity_status=identity_status,
                    reported_delta=reported_delta,
                )

    base["identity_status"] = identity_status
    return base


def _resolved_match(
    base: dict,
    filing: Mapping[str, object],
    *,
    method: str,
    confidence: str,
    identity_status: str,
    report_delta: int | None = None,
    reported_delta: int | None = None,
) -> dict:
    return {
        **base,
        "accession_number": filing["accession_number"],
        "form": filing["form"],
        "acceptance_datetime_utc": filing["acceptance_datetime_utc"],
        "match_method": method,
        "confidence": confidence,
        "identity_status": identity_status,
        "report_date_delta_days": report_delta,
        "reported_date_delta_days": reported_delta,
    }


def _load_identities(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for row in conn.execute(f"SELECT * FROM {SEC_IDENTITY_TABLE}"):
        record = dict(row)
        result.setdefault(record["ticker"], []).append(record)
    return result


def _load_filings(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for row in conn.execute(f"SELECT * FROM {SEC_FILING_TABLE}"):
        record = dict(row)
        result.setdefault(record["cik"], []).append(record)
    return result


def _identity_for_date(
    identities: list[dict],
    fiscal_date: str,
) -> dict | None:
    dated = [
        identity
        for identity in identities
        if (not identity["valid_from"] or identity["valid_from"] <= fiscal_date)
        and (not identity["valid_to"] or identity["valid_to"] >= fiscal_date)
        and (identity["valid_from"] or identity["valid_to"])
    ]
    if len(dated) == 1:
        return dated[0]
    if len(dated) > 1:
        return None
    current = [identity for identity in identities if identity["is_current"]]
    if len(current) == 1:
        return current[0]
    return None


def _as_date(value: object) -> dt.date:
    return dt.date.fromisoformat(str(value)[:10])


def _normalize_tickers(tickers: Iterable[str]) -> list[str]:
    return sorted({
        ticker.strip().upper()
        for ticker in tickers
        if isinstance(ticker, str) and ticker.strip()
    })


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
