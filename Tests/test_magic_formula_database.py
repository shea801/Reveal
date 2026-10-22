import sqlite3

import pandas as pd
import pytest

from Securities_DB import magic_formula_database as mf_db


def _investment_connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for table in (
        "balance_sheet_annual",
        "cash_flow_annual",
        "income_annual",
        "earnings_annual",
        "balance_sheet_quarterly",
        "income_quarterly",
    ):
        conn.execute(f"""
            CREATE TABLE {table} (
                ticker TEXT,
                fiscalDateEnding TEXT
            )
        """)
    conn.execute("""
        CREATE TABLE earnings_quarterly (
            ticker TEXT,
            fiscalDateEnding TEXT,
            reportedDate TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE ohlcv_daily (
            ticker TEXT,
            date TEXT,
            close REAL
        )
    """)
    return conn


def _rank_record(
    ticker="AAA",
    quarter_date="2024-03-31",
    annual_date="2023-12-31",
    magic_rank=1,
    roc_rank=1,
    ey_rank=1,
):
    return {
        "ticker": ticker,
        "quarter_date": quarter_date,
        "associated_annual_date": annual_date,
        "magic_formula_rank": magic_rank,
        "return_on_capital_rank": roc_rank,
        "earnings_yield_rank": ey_rank,
        "total_roc_ey_score": roc_rank + ey_rank,
    }


def _ranking_frame(tickers, quarter_date):
    records = [
        _rank_record(
            ticker=ticker,
            quarter_date=quarter_date,
            magic_rank=index,
            roc_rank=index,
            ey_rank=index,
        )
        for index, ticker in enumerate(sorted(tickers), start=1)
    ]
    return pd.DataFrame(records)


def test_quarter_end_dates_returns_inclusive_calendar_quarters():
    assert mf_db.quarter_end_dates("2024-04-01", "2024-12-31") == [
        "2024-06-30",
        "2024-09-30",
        "2024-12-31",
    ]


def test_schema_contains_only_rank_metadata_and_composite_primary_key():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    mf_db.create_magic_formula_schema(conn)

    table_info = conn.execute(
        f"PRAGMA table_info({mf_db.RESULT_TABLE})"
    ).fetchall()

    assert [row["name"] for row in table_info] == list(mf_db.RESULT_COLUMNS)
    primary_key = sorted(
        ((row["pk"], row["name"]) for row in table_info if row["pk"]),
    )
    assert primary_key == [(1, "ticker"), (2, "quarter_date")]
    assert not {
        "return_on_capital",
        "earnings_yield",
        "market_price_for_period",
        "market_price_plus_one_year",
    }.intersection(row["name"] for row in table_info)


def test_upsert_uses_ticker_and_quarter_date_primary_key():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    mf_db.create_magic_formula_schema(conn)
    mf_db.upsert_magic_formula_records(
        conn,
        [
            _rank_record(),
            _rank_record(
                magic_rank=2,
                roc_rank=2,
                ey_rank=1,
            ),
            _rank_record(
                quarter_date="2024-06-30",
                annual_date="2023-12-31",
            ),
        ],
    )

    rows = conn.execute(f"""
        SELECT ticker, quarter_date, magic_formula_rank, total_roc_ey_score
        FROM {mf_db.RESULT_TABLE}
        ORDER BY quarter_date
    """).fetchall()

    assert [dict(row) for row in rows] == [
        {
            "ticker": "AAA",
            "quarter_date": "2024-03-31",
            "magic_formula_rank": 2,
            "total_roc_ey_score": 3,
        },
        {
            "ticker": "AAA",
            "quarter_date": "2024-06-30",
            "magic_formula_rank": 1,
            "total_roc_ey_score": 2,
        },
    ]


def test_incompatible_legacy_schema_requires_explicit_rebuild():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(f"""
        CREATE TABLE {mf_db.RESULT_TABLE} (
            ticker TEXT,
            analysis_date TEXT,
            market_price_for_period REAL
        )
    """)

    with pytest.raises(RuntimeError, match="rebuild enabled"):
        mf_db.create_magic_formula_schema(conn)

    mf_db.create_magic_formula_schema(conn, rebuild=True)
    columns = [
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({mf_db.RESULT_TABLE})")
    ]
    assert columns == list(mf_db.RESULT_COLUMNS)


def test_refresh_magic_formula_symbols_writes_table_and_backup(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    backup_path = tmp_path / "magic_formula_ranked_securities.csv"
    calls = []

    def fake_eligible_tickers_fn(ticker_list=None):
        calls.append(ticker_list)
        return ["bbb", "AAA", "aaa"]

    tickers = mf_db.refresh_magic_formula_symbols(
        conn,
        ticker_list=["aaa", "bbb"],
        backup_path=backup_path,
        eligible_tickers_fn=fake_eligible_tickers_fn,
    )

    rows = conn.execute(
        "SELECT ticker FROM magic_formula_symbols ORDER BY ticker"
    ).fetchall()
    assert calls == [["aaa", "bbb"]]
    assert tickers == ["AAA", "BBB"]
    assert [row["ticker"] for row in rows] == ["AAA", "BBB"]
    assert backup_path.read_text().splitlines() == ["ticker", "AAA", "BBB"]


def test_records_add_statement_availability_date_without_financial_values():
    investment_conn = _investment_connection()
    investment_conn.executemany(
        """
        INSERT INTO earnings_quarterly
            (ticker, fiscalDateEnding, reportedDate)
        VALUES (?, ?, ?)
        """,
        [
            ("AAA", "2023-06-30", "2023-07-28"),
            ("AAA", "2023-09-30", "2023-10-27"),
            ("AAA", "2023-12-31", "2024-02-15"),
            ("AAA", "2024-03-31", "2024-04-26"),
        ],
    )

    def fake_ranking_fn(tickers_list=None, date=None):
        assert tickers_list == ["AAA"]
        assert date == "2024-03-31"
        return pd.DataFrame([_rank_record()])

    records = mf_db.magic_formula_records_for_date(
        ["AAA"],
        "2024-03-31",
        investment_conn=investment_conn,
        ranking_fn=fake_ranking_fn,
    )

    assert records == [{
        **_rank_record(),
        "financial_statement_availability_date": "2024-04-26",
    }]
    assert set(records[0]) == set(mf_db.RESULT_COLUMNS)


def test_statement_availability_date_is_null_when_report_history_is_incomplete():
    investment_conn = _investment_connection()
    investment_conn.execute(
        """
        INSERT INTO earnings_quarterly
            (ticker, fiscalDateEnding, reportedDate)
        VALUES (?, ?, ?)
        """,
        ("AAA", "2023-12-31", "2024-02-15"),
    )

    assert mf_db.financial_statement_availability_date(
        investment_conn,
        "AAA",
        "2024-03-31",
        "2023-12-31",
    ) is None


def test_infer_quarter_dates_uses_source_history_without_forward_price():
    conn = _investment_connection()
    for table, date_column in mf_db._source_date_tables():
        extra = ", reportedDate" if table == "earnings_quarterly" else ""
        placeholders = "?, ?, ?" if extra else "?, ?"
        sql = (
            f"INSERT INTO {table} (ticker, {date_column}{extra}) "
            f"VALUES ({placeholders})"
        )
        rows = [
            ("AAA", "2019-01-01", "2019-02-01"),
            ("AAA", "2025-12-31", "2026-02-01"),
        ] if extra else [
            ("AAA", "2019-01-01"),
            ("AAA", "2025-12-31"),
        ]
        conn.executemany(sql, rows)

    dates = mf_db.infer_quarter_end_dates(conn, minimum_history_years=5)

    assert dates[0] == "2023-03-31"
    assert dates[-1] == "2025-12-31"


def test_eligible_ticker_batches_respect_each_tickers_own_history():
    conn = _investment_connection()
    for table, date_column in mf_db._source_date_tables():
        extra = ", reportedDate" if table == "earnings_quarterly" else ""
        placeholders = "?, ?, ?" if extra else "?, ?"
        sql = (
            f"INSERT INTO {table} (ticker, {date_column}{extra}) "
            f"VALUES ({placeholders})"
        )
        rows = [
            ("OLD", "2010-01-01", "2010-02-01"),
            ("OLD", "2025-12-31", "2026-02-01"),
            ("NEW", "2020-01-01", "2020-02-01"),
            ("NEW", "2025-12-31", "2026-02-01"),
        ] if extra else [
            ("OLD", "2010-01-01"),
            ("OLD", "2025-12-31"),
            ("NEW", "2020-01-01"),
            ("NEW", "2025-12-31"),
        ]
        conn.executemany(sql, rows)

    batches = mf_db.eligible_ticker_quarter_batches(conn, ["OLD", "NEW"])

    assert batches["2014-03-31"] == ["OLD"]
    assert batches["2024-03-31"] == ["NEW", "OLD"]


def test_eligible_batches_allow_quarters_after_latest_annual_period():
    conn = _investment_connection()
    for table, date_column in mf_db._source_date_tables():
        extra = ", reportedDate" if table == "earnings_quarterly" else ""
        placeholders = "?, ?, ?" if extra else "?, ?"
        sql = (
            f"INSERT INTO {table} (ticker, {date_column}{extra}) "
            f"VALUES ({placeholders})"
        )
        maximum = (
            "2024-12-31"
            if table in mf_db.ANNUAL_SOURCE_TABLES
            else "2025-06-30"
        )
        rows = [
            ("AAA", "2019-01-01", "2019-02-01"),
            ("AAA", maximum, "2025-08-01"),
        ] if extra else [
            ("AAA", "2019-01-01"),
            ("AAA", maximum),
        ]
        conn.executemany(sql, rows)

    batches = mf_db.eligible_ticker_quarter_batches(conn, ["AAA"])

    assert batches["2025-06-30"] == ["AAA"]


def test_build_database_stores_rank_rows_and_ordered_view(tmp_path):
    investment_conn = _investment_connection()
    db_path = tmp_path / "magic_formula_results.db"
    backup_path = tmp_path / "magic_formula_ranked_securities.csv"

    def fake_eligible_tickers_fn(ticker_list=None):
        assert ticker_list is None
        return ["BBB", "AAA"]

    def fake_ranking_fn(tickers_list=None, date=None):
        return _ranking_frame(tickers_list, date)

    summary = mf_db.build_magic_formula_results_database(
        db_path=db_path,
        analysis_dates=["2024-06-30", "2024-03-31"],
        backup_path=backup_path,
        investment_conn=investment_conn,
        eligible_tickers_fn=fake_eligible_tickers_fn,
        ranking_fn=fake_ranking_fn,
    )

    assert summary["ticker_count"] == 2
    assert summary["requested_quarter_date_count"] == 2
    assert summary["quarter_date_count"] == 2
    assert summary["upserted_result_row_count"] == 4
    assert summary["result_row_count"] == 4
    assert summary["first_quarter_date"] == "2024-03-31"
    assert summary["last_quarter_date"] == "2024-06-30"
    assert backup_path.read_text().splitlines() == ["ticker", "AAA", "BBB"]

    conn = mf_db.connect_magic_formula_db(db_path, readonly=True)
    rows = conn.execute(f"SELECT * FROM {mf_db.ORDERED_VIEW}").fetchall()
    conn.close()
    assert [
        (row["quarter_date"], row["magic_formula_rank"], row["ticker"])
        for row in rows
    ] == [
        ("2024-03-31", 1, "AAA"),
        ("2024-03-31", 2, "BBB"),
        ("2024-06-30", 1, "AAA"),
        ("2024-06-30", 2, "BBB"),
    ]


def test_build_database_can_resume_completed_quarters(tmp_path):
    investment_conn = _investment_connection()
    db_path = tmp_path / "magic_formula_results.db"
    results_conn = mf_db.connect_magic_formula_db(db_path)
    mf_db.create_magic_formula_schema(results_conn)
    mf_db.upsert_magic_formula_records(results_conn, [_rank_record()])
    results_conn.close()

    def fake_ranking_fn(tickers_list=None, date=None):
        return _ranking_frame(tickers_list, date)

    summary = mf_db.build_magic_formula_results_database(
        db_path=db_path,
        analysis_dates=["2024-03-31", "2024-06-30"],
        investment_conn=investment_conn,
        ranking_fn=fake_ranking_fn,
        refresh_symbols=False,
        skip_completed_dates=True,
    )

    assert summary["ticker_count"] == 1
    assert summary["requested_quarter_date_count"] == 2
    assert summary["quarter_date_count"] == 2
    assert summary["skipped_quarter_date_count"] == 1
    assert summary["upserted_result_row_count"] == 1
    assert summary["result_row_count"] == 2


def test_build_database_refresh_replaces_stale_quarter_rows(tmp_path):
    investment_conn = _investment_connection()
    db_path = tmp_path / "magic_formula_results.db"
    results_conn = mf_db.connect_magic_formula_db(db_path)
    mf_db.create_magic_formula_schema(results_conn)
    mf_db.upsert_magic_formula_records(results_conn, [
        _rank_record(ticker="AAA", magic_rank=1, roc_rank=1, ey_rank=1),
        _rank_record(ticker="BBB", magic_rank=2, roc_rank=2, ey_rank=2),
    ])
    results_conn.close()

    summary = mf_db.build_magic_formula_results_database(
        db_path=db_path,
        analysis_dates=["2024-03-31"],
        investment_conn=investment_conn,
        ranking_fn=lambda tickers_list=None, date=None: _ranking_frame(
            ["AAA"],
            date,
        ),
        refresh_symbols=False,
    )

    conn = mf_db.connect_magic_formula_db(db_path, readonly=True)
    rows = conn.execute(f"""
        SELECT ticker, magic_formula_rank
        FROM {mf_db.RESULT_TABLE}
        WHERE quarter_date = '2024-03-31'
    """).fetchall()
    conn.close()
    assert [tuple(row) for row in rows] == [("AAA", 1)]
    assert summary["upserted_result_row_count"] == 1


def test_quarter_refresh_refuses_to_erase_populated_period_with_no_results():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    mf_db.create_magic_formula_schema(conn)
    mf_db.upsert_magic_formula_records(conn, [_rank_record()])

    with pytest.raises(RuntimeError, match="Refusing to replace"):
        mf_db.replace_magic_formula_quarter_records(
            conn,
            "2024-03-31",
            [],
        )

    assert conn.execute(
        f"SELECT COUNT(*) FROM {mf_db.RESULT_TABLE}"
    ).fetchone()[0] == 1


def test_validation_rejects_non_sequential_and_misordered_ranks():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    mf_db.create_magic_formula_schema(conn)
    conn.executemany(
        "INSERT INTO magic_formula_symbols VALUES (?)",
        [("AAA",), ("BBB",)],
    )
    conn.executemany(
        f"""
        INSERT INTO {mf_db.RESULT_TABLE} VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            ("AAA", "2024-03-31", "2023-12-31", None, 2, 1, 1, 2),
            ("BBB", "2024-03-31", "2023-12-31", None, 1, 2, 2, 4),
        ],
    )

    with pytest.raises(RuntimeError, match="invalid_order_rows=2"):
        mf_db.validate_magic_formula_database(conn)

    conn.execute(f"DELETE FROM {mf_db.RESULT_TABLE}")
    conn.executemany(
        f"""
        INSERT INTO {mf_db.RESULT_TABLE} VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            ("AAA", "2024-03-31", "2023-12-31", None, 1, 2, 2, 4),
            ("BBB", "2024-03-31", "2023-12-31", None, 2, 3, 3, 6),
        ],
    )

    with pytest.raises(RuntimeError, match="invalid_rank_quarters=1"):
        mf_db.validate_magic_formula_database(conn)


def test_atomic_rebuild_replaces_legacy_database_only_after_validation(tmp_path):
    investment_conn = _investment_connection()
    db_path = tmp_path / "magic_formula_results.db"
    legacy_conn = sqlite3.connect(db_path)
    legacy_conn.execute(f"""
        CREATE TABLE {mf_db.RESULT_TABLE} (
            ticker TEXT,
            analysis_date TEXT,
            market_price_for_period REAL
        )
    """)
    legacy_conn.commit()
    legacy_conn.close()

    summary = mf_db.rebuild_magic_formula_results_database(
        db_path=db_path,
        backup_path=tmp_path / "magic_formula_ranked_securities.csv",
        analysis_dates=["2024-03-31"],
        investment_conn=investment_conn,
        eligible_tickers_fn=lambda ticker_list=None: ["AAA"],
        ranking_fn=lambda tickers_list=None, date=None: _ranking_frame(
            tickers_list,
            date,
        ),
    )

    assert summary["result_row_count"] == 1
    conn = mf_db.connect_magic_formula_db(db_path, readonly=True)
    columns = [
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({mf_db.RESULT_TABLE})")
    ]
    assert columns == list(mf_db.RESULT_COLUMNS)
    assert mf_db.validate_magic_formula_database(conn)["result_row_count"] == 1
    conn.close()
