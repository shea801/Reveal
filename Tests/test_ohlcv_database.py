import sqlite3

from Securities_DB import ohlcv_database as ohlcv_db


def _connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE sec_tickers (ticker TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO sec_tickers VALUES ('AAA')")
    return conn


def _adjusted_record(adjusted_close="231.4"):
    return {
        "1. open": "231.0",
        "2. high": "233.09",
        "3. low": "229.9",
        "4. close": "231.4",
        "5. adjusted close": adjusted_close,
        "6. volume": "3240341",
        "7. dividend amount": "0.2600",
        "8. split coefficient": "1.0",
    }


def test_schema_migration_preserves_raw_rows_and_adds_adjusted_columns():
    conn = _connection()
    conn.execute("""
        CREATE TABLE ohlcv_daily (
            ticker TEXT, date TEXT, open REAL, high REAL, low REAL,
            close REAL, volume INTEGER,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.execute("""
        INSERT INTO ohlcv_daily
        VALUES ('AAA', '2024-01-02', 10, 11, 9, 10.5, 100)
    """)

    added = ohlcv_db.ensure_ohlcv_schema(conn)
    row = conn.execute(
        "SELECT close, adjusted_close FROM ohlcv_daily"
    ).fetchone()

    assert added == [
        "adjusted_close",
        "dividend_amount",
        "split_coefficient",
        "price_source",
        "loaded_at_utc",
    ]
    assert tuple(row) == (10.5, None)


def test_adjusted_payload_maps_new_volume_dividend_and_split_keys():
    record = ohlcv_db.parse_alpha_vantage_daily_record(
        "aaa",
        "2026-09-01",
        _adjusted_record(),
        loaded_at_utc="2026-09-02T12:00:00Z",
    )

    assert record == {
        "ticker": "AAA",
        "date": "2026-09-01",
        "open": 231.0,
        "high": 233.09,
        "low": 229.9,
        "close": 231.4,
        "adjusted_close": 231.4,
        "volume": 3240341,
        "dividend_amount": 0.26,
        "split_coefficient": 1.0,
        "price_source": ohlcv_db.ALPHA_VANTAGE_ADJUSTED_SOURCE,
        "loaded_at_utc": "2026-09-02T12:00:00Z",
    }


def test_legacy_raw_payload_remains_readable():
    record = ohlcv_db.parse_alpha_vantage_daily_record(
        "AAA",
        "2026-09-01",
        {
            "1. open": "231.0000",
            "2. high": "233.0900",
            "3. low": "229.9000",
            "4. close": "231.4000",
            "5. volume": "3240341",
        },
        loaded_at_utc="2026-09-02T12:00:00Z",
    )

    assert record["adjusted_close"] is None
    assert record["volume"] == 3240341
    assert record["price_source"] == ohlcv_db.ALPHA_VANTAGE_RAW_SOURCE


def test_raw_upsert_does_not_erase_existing_adjusted_values():
    conn = _connection()
    ohlcv_db.upsert_ohlcv_payload(
        conn,
        "AAA",
        {"2026-09-01": _adjusted_record("200.0")},
    )
    ohlcv_db.upsert_ohlcv_payload(
        conn,
        "AAA",
        {"2026-09-01": {
            "1. open": "231.0",
            "2. high": "233.09",
            "3. low": "229.9",
            "4. close": "231.4",
            "5. volume": "3240341",
        }},
    )

    row = conn.execute("""
        SELECT adjusted_close, dividend_amount, split_coefficient, price_source
        FROM ohlcv_daily
    """).fetchone()
    assert tuple(row) == (
        200.0,
        0.26,
        1.0,
        ohlcv_db.ALPHA_VANTAGE_ADJUSTED_SOURCE,
    )
