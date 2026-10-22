"""Schema migration and persistence for Alpha Vantage daily adjusted data."""

from __future__ import annotations

from collections.abc import Mapping
import datetime as dt
import sqlite3


OHLCV_TABLE = "ohlcv_daily"
ALPHA_VANTAGE_ADJUSTED_SOURCE = "alpha_vantage_daily_adjusted"
ALPHA_VANTAGE_RAW_SOURCE = "alpha_vantage_daily_raw"

OHLCV_COLUMNS = (
    "ticker",
    "date",
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "volume",
    "dividend_amount",
    "split_coefficient",
    "price_source",
    "loaded_at_utc",
)

ADJUSTED_COLUMN_DEFINITIONS = {
    "adjusted_close": (
        "REAL CHECK (adjusted_close IS NULL OR adjusted_close > 0)"
    ),
    "dividend_amount": "REAL",
    "split_coefficient": (
        "REAL CHECK (split_coefficient IS NULL OR split_coefficient > 0)"
    ),
    "price_source": "TEXT",
    "loaded_at_utc": "TEXT",
}


def ensure_ohlcv_schema(
    conn: sqlite3.Connection,
    *,
    commit: bool = True,
) -> list[str]:
    """Create or migrate OHLCV storage without rewriting existing rows."""
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {OHLCV_TABLE} (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            adjusted_close REAL
                CHECK (adjusted_close IS NULL OR adjusted_close > 0),
            volume INTEGER,
            dividend_amount REAL,
            split_coefficient REAL
                CHECK (split_coefficient IS NULL OR split_coefficient > 0),
            price_source TEXT,
            loaded_at_utc TEXT,
            PRIMARY KEY (ticker, date),
            FOREIGN KEY (ticker) REFERENCES sec_tickers(ticker)
        )
    """)
    existing = {
        row[1] for row in conn.execute(f"PRAGMA table_info({OHLCV_TABLE})")
    }
    added = []
    for column, definition in ADJUSTED_COLUMN_DEFINITIONS.items():
        if column in existing:
            continue
        conn.execute(
            f"ALTER TABLE {OHLCV_TABLE} ADD COLUMN {column} {definition}"
        )
        added.append(column)
    if commit:
        conn.commit()
    return added


def parse_alpha_vantage_daily_record(
    ticker: str,
    date: str,
    prices: Mapping[str, object],
    *,
    loaded_at_utc: str | None = None,
) -> dict:
    """Normalize either adjusted or legacy raw Alpha Vantage daily fields."""
    ticker = str(ticker).strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    try:
        dt.date.fromisoformat(date)
    except (TypeError, ValueError) as exc:
        raise ValueError("date must use YYYY-MM-DD format") from exc

    adjusted_close = _optional_float(prices.get("5. adjusted close"))
    is_adjusted = adjusted_close is not None
    volume_key = "6. volume" if is_adjusted else "5. volume"
    return {
        "ticker": ticker,
        "date": date,
        "open": _optional_float(prices.get("1. open")),
        "high": _optional_float(prices.get("2. high")),
        "low": _optional_float(prices.get("3. low")),
        "close": _optional_float(prices.get("4. close")),
        "adjusted_close": adjusted_close,
        "volume": _optional_int(prices.get(volume_key)),
        "dividend_amount": _optional_float(
            prices.get("7. dividend amount")
        ),
        "split_coefficient": _optional_float(
            prices.get("8. split coefficient")
        ),
        "price_source": (
            ALPHA_VANTAGE_ADJUSTED_SOURCE
            if is_adjusted
            else ALPHA_VANTAGE_RAW_SOURCE
        ),
        "loaded_at_utc": loaded_at_utc or _utc_now(),
    }


def upsert_ohlcv_payload(
    conn: sqlite3.Connection,
    ticker: str,
    payload: Mapping[str, object],
    *,
    commit: bool = True,
) -> int:
    """Upsert one ticker's daily payload while preserving adjusted values."""
    ensure_ohlcv_schema(conn, commit=False)
    loaded_at = _utc_now()
    records = []
    for date, prices in payload.items():
        if not isinstance(prices, Mapping):
            continue
        try:
            record = parse_alpha_vantage_daily_record(
                ticker,
                str(date),
                prices,
                loaded_at_utc=loaded_at,
            )
        except ValueError:
            continue
        records.append(tuple(record[column] for column in OHLCV_COLUMNS))

    if not records:
        return 0
    placeholders = ", ".join("?" for _ in OHLCV_COLUMNS)
    conn.executemany(f"""
        INSERT INTO {OHLCV_TABLE} ({", ".join(OHLCV_COLUMNS)})
        VALUES ({placeholders})
        ON CONFLICT(ticker, date) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            adjusted_close = COALESCE(
                excluded.adjusted_close,
                {OHLCV_TABLE}.adjusted_close
            ),
            volume = excluded.volume,
            dividend_amount = COALESCE(
                excluded.dividend_amount,
                {OHLCV_TABLE}.dividend_amount
            ),
            split_coefficient = COALESCE(
                excluded.split_coefficient,
                {OHLCV_TABLE}.split_coefficient
            ),
            price_source = CASE
                WHEN excluded.adjusted_close IS NOT NULL
                    THEN excluded.price_source
                ELSE COALESCE({OHLCV_TABLE}.price_source, excluded.price_source)
            END,
            loaded_at_utc = excluded.loaded_at_utc
    """, records)
    if commit:
        conn.commit()
    return len(records)


def adjusted_price_coverage(conn: sqlite3.Connection) -> dict[str, int]:
    """Summarize migration/backfill progress without reading price values."""
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (OHLCV_TABLE,),
    ).fetchone()
    if table_exists is None:
        return {
            "total_price_rows": 0,
            "adjusted_price_rows": 0,
            "adjusted_ticker_count": 0,
        }
    columns = {
        row[1] for row in conn.execute(f"PRAGMA table_info({OHLCV_TABLE})")
    }
    if "adjusted_close" not in columns:
        total = conn.execute(
            f"SELECT COUNT(*) FROM {OHLCV_TABLE}"
        ).fetchone()[0]
        return {
            "total_price_rows": total,
            "adjusted_price_rows": 0,
            "adjusted_ticker_count": 0,
        }
    row = conn.execute(f"""
        SELECT COUNT(*) AS total_rows,
               COUNT(adjusted_close) AS adjusted_rows,
               COUNT(DISTINCT CASE
                   WHEN adjusted_close IS NOT NULL THEN ticker
               END) AS adjusted_tickers
        FROM {OHLCV_TABLE}
    """).fetchone()
    return {
        "total_price_rows": row[0],
        "adjusted_price_rows": row[1],
        "adjusted_ticker_count": row[2],
    }


def retire_empty_legacy_adjusted_price_table(
    conn: sqlite3.Connection,
) -> bool:
    """Drop the superseded duplicate table only when it contains no rows."""
    legacy_table = "adjusted_ohlcv_daily"
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (legacy_table,),
    ).fetchone()
    if exists is None:
        return False
    row_count = conn.execute(
        f"SELECT COUNT(*) FROM {legacy_table}"
    ).fetchone()[0]
    if row_count:
        raise RuntimeError(
            f"{legacy_table} contains {row_count} rows and was left unchanged"
        )
    conn.execute(f"DROP TABLE {legacy_table}")
    conn.commit()
    return True


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
