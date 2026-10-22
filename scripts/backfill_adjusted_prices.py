"""Review or execute resumable Alpha Vantage adjusted-price backfills."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from maintenance.adjusted_price_backfill import (  # noqa: E402
    connect_investment_db,
    historical_magic_formula_tickers,
    run_adjusted_price_backfill,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill daily adjusted prices without refreshing financial data."
        )
    )
    parser.add_argument("tickers", nargs="*", help="Explicit ticker symbols.")
    parser.add_argument(
        "--magic-formula",
        action="store_true",
        help="Use all tickers present in historical Magic Formula rankings.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process at most this many incomplete tickers.",
    )
    parser.add_argument(
        "--stage",
        default="manual",
        help="Short label stored with the run history.",
    )
    parser.add_argument(
        "--include-complete",
        action="store_true",
        help="Refresh tickers that already have complete adjusted coverage.",
    )
    parser.add_argument(
        "--exclude-ticker",
        action="append",
        default=[],
        help=(
            "Skip a known source anomaly in this run. Repeat for multiple "
            "tickers."
        ),
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print progress after this many successful tickers.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop after the first failed ticker.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Download and load data. Omit for review-only mode.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if bool(args.tickers) == bool(args.magic_formula):
        raise SystemExit(
            "Provide explicit tickers or --magic-formula, but not both."
        )
    tickers = (
        historical_magic_formula_tickers()
        if args.magic_formula
        else args.tickers
    )
    excluded = {ticker.strip().upper() for ticker in args.exclude_ticker}
    tickers = [ticker for ticker in tickers if ticker not in excluded]
    conn = connect_investment_db()
    try:
        summary = run_adjusted_price_backfill(
            conn,
            tickers,
            execute=args.execute,
            limit=args.limit,
            include_complete=args.include_complete,
            stage=args.stage,
            progress_every=args.progress_every,
            stop_on_error=args.stop_on_error,
        )
    finally:
        conn.close()

    if not args.execute:
        print("Review-only mode. No API calls or database writes were made.")
    for key, value in summary.items():
        if key == "planned_tickers":
            preview = ", ".join(value[:25])
            if len(value) > 25:
                preview += f", ... ({len(value)} total)"
            print(f"{key}: {preview or 'none'}")
        else:
            print(f"{key}: {value}")
    return int(
        args.execute
        and (summary["failed_count"] > 0 or summary["partial_count"] > 0)
    )


if __name__ == "__main__":
    raise SystemExit(main())
