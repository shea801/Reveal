"""Run availability-aware Magic Formula backtests from local source data."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analytics.MagicFormulaBacktest import (  # noqa: E402
    run_magic_formula_backtest,
)
from Securities_DB.db_connection import get_connection  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a strict, filing-aware Magic Formula backtest."
    )
    parser.add_argument(
        "--quarter-date",
        action="append",
        required=True,
        dest="quarter_dates",
        help="Quarter date in YYYY-MM-DD format. Repeat for multiple periods.",
    )
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument(
        "--output-directory",
        type=Path,
        help="Optional directory for cohort, position, return, and exclusion CSVs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    investment_conn = get_connection()
    results_conn = get_connection(analysis="magic_formula", readonly=True)
    try:
        result = run_magic_formula_backtest(
            investment_conn,
            results_conn,
            quarter_dates=args.quarter_dates,
            top_n=args.top,
        )
    finally:
        results_conn.close()
        investment_conn.close()

    for name, frame in result.items():
        print(f"{name}_row_count: {len(frame.index)}")
    if args.output_directory:
        args.output_directory.mkdir(parents=True, exist_ok=True)
        for name, frame in result.items():
            frame.to_csv(args.output_directory / f"{name}.csv", index=False)
        print(f"output_directory: {args.output_directory.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
