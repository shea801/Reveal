"""Prepare local SEC metadata and adjusted prices for strict backtesting."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Securities_DB.db_connection import get_connection  # noqa: E402
from Securities_DB.ohlcv_database import (  # noqa: E402
    adjusted_price_coverage,
    ensure_ohlcv_schema,
    retire_empty_legacy_adjusted_price_table,
)
from Securities_DB.sec_metadata_database import (  # noqa: E402
    SEC_FILING_TABLE,
    SEC_IDENTITY_TABLE,
    SEC_MATCH_TABLE,
    create_sec_metadata_schema,
    import_sec_submissions_archive,
)
from data_access.SECFilingMetadata import match_source_statements  # noqa: E402
from runtime_config import get_data_root  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare SEC filing metadata and adjusted price data."
    )
    parser.add_argument(
        "action",
        choices=("initialize", "import-sec", "match", "status"),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes. Omit to review the selected action.",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
        help="Path to the downloaded SEC submissions.zip archive.",
    )
    parser.add_argument(
        "--ticker",
        action="append",
        dest="tickers",
        help="Limit SEC import/matching to a ticker. Repeat as needed.",
    )
    parser.add_argument(
        "--all-sec-tickers",
        action="store_true",
        help="Use every sec_tickers row instead of the Magic Formula universe.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.execute and args.action != "status":
        print("Review-only mode. No database changes were made.")
        print(f"action: {args.action}")
        if args.action == "import-sec":
            print(f"archive: {args.archive or get_data_root() / 'submissions.zip'}")
        print(f"tickers: {args.tickers or 'Magic Formula universe'}")
        print("Run again with --execute after reviewing the action.")
        return 0

    conn = get_connection(readonly=args.action == "status")
    try:
        if args.action != "status":
            create_sec_metadata_schema(conn)
            ensure_ohlcv_schema(conn)
        tickers = _selected_tickers(conn, args)
        if args.action == "initialize":
            retired = retire_empty_legacy_adjusted_price_table(conn)
            print("SEC/backtest source schema initialized.")
            if retired:
                print("Removed empty superseded adjusted_ohlcv_daily table.")
        elif args.action == "import-sec":
            summary = import_sec_submissions_archive(
                conn,
                args.archive or get_data_root() / "submissions.zip",
                tickers=tickers,
            )
            _print_summary(summary)
        elif args.action == "match":
            summary = match_source_statements(conn, tickers=tickers)
            _print_summary(summary)
        else:
            _print_summary(_status(conn))
    finally:
        conn.close()
    return 0


def _selected_tickers(conn, args) -> list[str] | None:
    if args.tickers:
        return sorted({ticker.strip().upper() for ticker in args.tickers})
    if args.all_sec_tickers:
        return None
    try:
        rows = conn.execute(
            "SELECT ticker FROM magic_formula_symbols ORDER BY ticker"
        ).fetchall()
    except Exception:
        return None
    return [row["ticker"] for row in rows] or None


def _status(conn) -> dict[str, int]:
    return {
        "filing_count": conn.execute(
            f"SELECT COUNT(*) FROM {SEC_FILING_TABLE}"
        ).fetchone()[0],
        "identity_count": conn.execute(
            f"SELECT COUNT(*) FROM {SEC_IDENTITY_TABLE}"
        ).fetchone()[0],
        "statement_match_count": conn.execute(
            f"SELECT COUNT(*) FROM {SEC_MATCH_TABLE}"
        ).fetchone()[0],
        **adjusted_price_coverage(conn),
    }


def _print_summary(summary: dict) -> None:
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
