import json
import sqlite3
import zipfile

from data_access.SECFilingMetadata import (
    annual_statement_availability_history,
    is_usable_backtest_match,
    match_source_statements,
)
from Securities_DB import sec_metadata_database as sec_db


def _connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sec_tickers (ticker TEXT PRIMARY KEY, cik TEXT)")
    conn.execute("""
        CREATE TABLE earnings_annual (
            ticker TEXT, fiscalDateEnding TEXT
        )
    """)
    for table in (
        "balance_sheet_annual",
        "cash_flow_annual",
        "income_annual",
    ):
        conn.execute(f"""
            CREATE TABLE {table} (
                ticker TEXT, fiscalDateEnding TEXT
            )
        """)
    conn.execute("""
        CREATE TABLE income_quarterly (
            ticker TEXT, fiscalDateEnding TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE earnings_quarterly (
            ticker TEXT, fiscalDateEnding TEXT, reportedDate TEXT
        )
    """)
    sec_db.create_sec_metadata_schema(conn)
    return conn


def _columnar(filings):
    keys = {
        "accessionNumber",
        "filingDate",
        "reportDate",
        "acceptanceDateTime",
        "form",
        "primaryDocument",
    }
    return {key: [filing.get(key) for filing in filings] for key in keys}


def test_sec_metadata_schema_keeps_accessions_and_identity_separate():
    conn = _connection()

    filing_columns = [
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({sec_db.SEC_FILING_TABLE})"
        )
    ]
    identity_primary_key = [
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({sec_db.SEC_IDENTITY_TABLE})"
        )
        if row["pk"]
    ]

    assert "ticker" not in filing_columns
    assert {"cik", "accession_number", "acceptance_datetime_utc"}.issubset(
        filing_columns
    )
    assert identity_primary_key == ["ticker", "cik"]


def test_archive_import_reads_recent_and_historical_members(tmp_path):
    conn = _connection()
    conn.execute(
        "INSERT INTO sec_tickers (ticker, cik) VALUES ('AAA', '1234')"
    )
    archive = tmp_path / "submissions.zip"
    recent = [{
        "accessionNumber": "0001-24-000001",
        "filingDate": "2024-05-02",
        "reportDate": "2024-03-31",
        "acceptanceDateTime": "20240502163000",
        "form": "10-Q",
        "primaryDocument": "q1.htm",
    }, {
        "accessionNumber": "0001-24-000002",
        "filingDate": "2024-05-03",
        "reportDate": "",
        "acceptanceDateTime": "20240503120000",
        "form": "8-K",
        "primaryDocument": "event.htm",
    }]
    historical = [{
        "accessionNumber": "0001-23-000003",
        "filingDate": "2023-02-20",
        "reportDate": "2022-12-31",
        "acceptanceDateTime": "20230220170000",
        "form": "10-K",
        "primaryDocument": "annual.htm",
    }]
    main = {
        "filings": {
            "recent": _columnar(recent),
            "files": [{"name": "CIK0000001234-submissions-001.json"}],
        }
    }
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("CIK0000001234.json", json.dumps(main))
        output.writestr(
            "CIK0000001234-submissions-001.json",
            json.dumps(_columnar(historical)),
        )

    summary = sec_db.import_sec_submissions_archive(
        conn,
        archive,
        tickers=["AAA"],
    )

    rows = conn.execute(f"""
        SELECT accession_number, form, acceptance_datetime_utc
        FROM {sec_db.SEC_FILING_TABLE}
        ORDER BY accession_number
    """).fetchall()
    assert summary["upserted_filing_count"] == 2
    assert [(row["accession_number"], row["form"]) for row in rows] == [
        ("0001-23-000003", "10-K"),
        ("0001-24-000001", "10-Q"),
    ]
    assert rows[1]["acceptance_datetime_utc"] == "2024-05-02T16:30:00Z"


def test_statement_matching_records_exact_and_reported_date_fallbacks():
    conn = _connection()
    conn.execute(
        "INSERT INTO sec_tickers (ticker, cik) VALUES ('AAA', '1234')"
    )
    sec_db.seed_current_ticker_identities(conn)
    conn.execute(
        "INSERT INTO earnings_annual VALUES ('AAA', '2023-12-31')"
    )
    conn.executemany(
        "INSERT INTO income_quarterly VALUES ('AAA', ?)",
        [("2023-09-30",), ("2023-12-31",), ("2024-03-31",)],
    )
    conn.executemany(
        "INSERT INTO earnings_quarterly VALUES ('AAA', ?, ?)",
        [
            ("2023-09-30", "2023-11-15"),
            ("2023-12-31", "2024-02-15"),
            ("2024-03-31", "2024-04-25"),
        ],
    )
    filings = [
        (
            "prior",
            "10-K",
            "2022-12-31",
            "2023-02-16",
            "2023-02-16T17:00:00Z",
        ),
        ("a", "10-K", "2023-12-31", "2024-02-16", "2024-02-16T17:00:00Z"),
        ("q1", "10-Q", "2024-03-31", "2024-04-26", "2024-04-26T17:00:00Z"),
        ("q0", "10-Q", None, "2023-11-16", "2023-11-16T17:00:00Z"),
    ]
    conn.executemany(f"""
        INSERT INTO {sec_db.SEC_FILING_TABLE} (
            cik, accession_number, form, report_date, filing_date,
            acceptance_datetime_utc, source_member, is_amendment,
            imported_at_utc
        ) VALUES ('0000001234', ?, ?, ?, ?, ?, 'test.json', 0, 'now')
    """, filings)

    summary = match_source_statements(conn, tickers=["AAA"])
    matches = conn.execute(f"""
        SELECT fiscal_date, statement_scope, form, match_method, confidence
        FROM {sec_db.SEC_MATCH_TABLE}
        ORDER BY fiscal_date, statement_scope
    """).fetchall()

    assert summary == {
        "statement_count": 4,
        "high": 3,
        "medium": 1,
        "low": 0,
        "unresolved": 0,
    }
    assert [tuple(row) for row in matches] == [
        (
            "2023-09-30",
            "quarterly",
            "10-Q",
            "source_reported_date_to_filing",
            "medium",
        ),
        ("2023-12-31", "annual", "10-K", "report_date_exact", "high"),
        (
            "2023-12-31",
            "quarterly",
            "10-K",
            "report_date_exact",
            "high",
        ),
        ("2024-03-31", "quarterly", "10-Q", "report_date_exact", "high"),
    ]


def test_current_cik_history_boundary_is_not_usable():
    conn = _connection()
    conn.execute(
        "INSERT INTO sec_tickers (ticker, cik) VALUES ('NEW', '9999')"
    )
    sec_db.seed_current_ticker_identities(conn)
    conn.execute(
        "INSERT INTO earnings_annual VALUES ('NEW', '2010-12-31')"
    )
    conn.execute(f"""
        INSERT INTO {sec_db.SEC_FILING_TABLE} (
            cik, accession_number, form, report_date, filing_date,
            acceptance_datetime_utc, source_member, is_amendment,
            imported_at_utc
        ) VALUES (
            '0000009999', 'recent', '10-K', '2020-12-31', '2021-02-20',
            '2021-02-20T17:00:00Z', 'test.json', 0, 'now'
        )
    """)

    match_source_statements(conn, tickers=["NEW"])
    record = dict(conn.execute(
        f"SELECT * FROM {sec_db.SEC_MATCH_TABLE}"
    ).fetchone())

    assert record["identity_status"] == "predates_current_cik_history"
    assert record["confidence"] == "unresolved"
    assert is_usable_backtest_match(record) is False


def test_annual_availability_history_filters_cutoff_and_unusable_matches():
    conn = _connection()
    conn.executemany(f"""
        INSERT INTO {sec_db.SEC_FILING_TABLE} (
            cik, accession_number, form, report_date, filing_date,
            acceptance_datetime_utc, source_member, is_amendment,
            imported_at_utc
        ) VALUES ('0000001234', ?, '10-K', ?, ?, ?, 'test.json', 0, 'now')
    """, [
        ("a", "2023-12-31", "2024-02-16", "2024-02-16T17:00:00Z"),
        ("b", "2022-12-31", "2023-02-15", "2023-02-15T17:00:00Z"),
        ("c", "2021-12-31", "2022-02-15", "2022-02-15T17:00:00Z"),
    ])
    rows = [
        (
            "AAA", "annual", "2023-12-31", "0000001234", "a", "10-K",
            "2024-02-16T17:00:00Z", "high", "confirmed_current_cik",
        ),
        (
            "AAA", "annual", "2022-12-31", "0000001234", "b", "10-K",
            "2023-02-15T17:00:00Z", "medium", "confirmed_historical_cik",
        ),
        (
            "AAA", "annual", "2021-12-31", "0000001234", "c", "10-K",
            "2022-02-15T17:00:00Z", "low", "confirmed_current_cik",
        ),
    ]
    conn.executemany(f"""
        INSERT INTO {sec_db.SEC_MATCH_TABLE} (
            ticker, statement_scope, fiscal_date, cik, accession_number,
            form, acceptance_datetime_utc, match_method, confidence,
            identity_status, matched_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'test', ?, ?, 'now')
    """, rows)

    history = annual_statement_availability_history(
        conn,
        ticker="aaa",
        analysis_date="2024-02-15",
    )

    assert history == [{
        "ticker": "AAA",
        "annual_statement_date": "2022-12-31",
        "statement_availability_date": "2023-02-15",
        "acceptance_datetime_utc": "2023-02-15T17:00:00Z",
        "confidence": "medium",
        "identity_status": "confirmed_historical_cik",
    }]


def test_foreign_interim_match_uses_accession_as_stable_tie_breaker():
    conn = _connection()
    conn.execute(
        "INSERT INTO sec_tickers (ticker, cik) VALUES ('ADR', '5678')"
    )
    sec_db.seed_current_ticker_identities(conn)
    conn.execute(
        "INSERT INTO income_quarterly VALUES ('ADR', '2024-03-31')"
    )
    conn.execute(
        "INSERT INTO earnings_quarterly VALUES "
        "('ADR', '2024-03-31', '2024-05-01')"
    )
    conn.executemany(f"""
        INSERT INTO {sec_db.SEC_FILING_TABLE} (
            cik, accession_number, form, report_date, filing_date,
            acceptance_datetime_utc, source_member, is_amendment,
            imported_at_utc
        ) VALUES (
            '0000005678', ?, '6-K', NULL, '2024-05-01', ?,
            'test.json', 0, 'now'
        )
    """, [
        ("second", "2024-05-01T18:00:00Z"),
        ("first", "2024-05-01T17:00:00Z"),
    ])

    summary = match_source_statements(conn, tickers=["ADR"])
    record = conn.execute(f"""
        SELECT accession_number, match_method, confidence
        FROM {sec_db.SEC_MATCH_TABLE}
    """).fetchone()

    assert summary["low"] == 1
    assert tuple(record) == (
        "first",
        "foreign_interim_reported_date",
        "low",
    )
