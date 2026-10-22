import sqlite3

from maintenance import adjusted_price_backfill as backfill


def _connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE ohlcv_daily (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            adjusted_close REAL,
            PRIMARY KEY (ticker, date)
        )
    """)
    return conn


def _insert_prices(conn, ticker, adjusted_values):
    conn.executemany(
        "INSERT INTO ohlcv_daily VALUES (?, ?, ?)",
        [
            (ticker, f"2024-01-{day:02d}", value)
            for day, value in enumerate(adjusted_values, start=1)
        ],
    )
    conn.commit()


def test_plan_skips_complete_and_limits_incomplete_tickers():
    conn = _connection()
    _insert_prices(conn, "DONE", [10.0, 11.0])
    _insert_prices(conn, "PART", [10.0, None])

    plan = backfill.plan_adjusted_price_backfill(
        conn,
        ["done", "part", "new", "later"],
        limit=2,
    )

    assert plan == {
        "requested": ["DONE", "PART", "NEW", "LATER"],
        "planned": ["PART", "NEW"],
        "complete": ["DONE"],
        "deferred_count": 1,
    }


def test_review_mode_has_no_writes_or_refresh_calls():
    conn = _connection()
    calls = []

    summary = backfill.run_adjusted_price_backfill(
        conn,
        ["AAA"],
        refresh_fn=lambda ticker: calls.append(ticker),
    )

    assert summary["planned_tickers"] == ["AAA"]
    assert calls == []
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'adjusted_price_backfill_runs'"
    ).fetchone() is None


def test_execute_records_updated_partial_and_failed_results():
    conn = _connection()
    _insert_prices(conn, "PART", [10.0, None])
    _insert_prices(conn, "FAIL", [None])

    def refresh(ticker):
        if ticker == "GOOD":
            _insert_prices(conn, ticker, [20.0, 21.0])
        elif ticker == "PART":
            conn.execute(
                "UPDATE ohlcv_daily SET adjusted_close = 11 WHERE ticker = ?",
                (ticker,),
            )
            conn.execute(
                "INSERT INTO ohlcv_daily VALUES (?, ?, NULL)",
                (ticker, "2024-01-03"),
            )
            conn.commit()
        else:
            raise RuntimeError("synthetic failure")
        return "fixture refresh"

    summary = backfill.run_adjusted_price_backfill(
        conn,
        ["GOOD", "PART", "FAIL"],
        execute=True,
        stage="unit-test",
        refresh_fn=refresh,
    )

    assert summary["updated_count"] == 1
    assert summary["partial_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["completed_count"] == 3
    statuses = conn.execute(
        """
        SELECT ticker, status
        FROM adjusted_price_backfill_events
        ORDER BY ticker
        """
    ).fetchall()
    assert [tuple(row) for row in statuses] == [
        ("FAIL", "failed"),
        ("GOOD", "updated"),
        ("PART", "partial"),
    ]


def test_execute_skips_complete_ticker_without_refreshing_it():
    conn = _connection()
    _insert_prices(conn, "DONE", [10.0])
    calls = []

    summary = backfill.run_adjusted_price_backfill(
        conn,
        ["DONE"],
        execute=True,
        refresh_fn=lambda ticker: calls.append(ticker),
    )

    assert calls == []
    assert summary["planned_count"] == 0
    assert summary["skipped_count"] == 1
    run = conn.execute(
        "SELECT planned_count, skipped_count FROM adjusted_price_backfill_runs"
    ).fetchone()
    assert tuple(run) == (0, 1)
