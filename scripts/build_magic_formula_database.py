"""CLI helper for reviewing/building the Magic Formula results database."""

from pathlib import Path
import argparse
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Securities_DB.magic_formula_database import (  # noqa: E402
    build_magic_formula_results_database,
    default_magic_formula_db_path,
    default_ticker_backup_path,
    rebuild_magic_formula_results_database,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the quarterly Magic Formula results database."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually build/update the database. Omit for review-only mode.",
    )
    parser.add_argument(
        "--database-path",
        default=str(default_magic_formula_db_path()),
        help="SQLite output path for Magic Formula results.",
    )
    parser.add_argument(
        "--ticker-backup-path",
        default=str(default_ticker_backup_path()),
        help="CSV backup path for the eligible Magic Formula ticker universe.",
    )
    parser.add_argument(
        "--analysis-date",
        action="append",
        dest="analysis_dates",
        help=(
            "Quarter-end analysis date to build. Repeat for multiple dates. "
            "When omitted, dates are inferred from available source data."
        ),
    )
    parser.add_argument(
        "--ticker",
        action="append",
        dest="tickers",
        help=(
            "Optional ticker universe seed for testing. Repeat for multiple "
            "tickers. When omitted, the full eligible universe is generated."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-ticker eligibility and calculation messages.",
    )
    build_mode = parser.add_mutually_exclusive_group()
    build_mode.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Reuse the existing Magic Formula ticker universe and skip "
            "analysis dates already present in the results database."
        ),
    )
    build_mode.add_argument(
        "--rebuild",
        action="store_true",
        help=(
            "Build a complete rank-only database in a temporary file, then "
            "atomically replace the existing database after validation."
        ),
    )
    build_mode.add_argument(
        "--refresh-existing",
        action="store_true",
        help=(
            "Reuse the stored historical ticker universe and atomically "
            "replace explicitly requested quarter dates."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.refresh_existing and not args.analysis_dates:
        parser.error("--refresh-existing requires at least one --analysis-date")
    if not args.execute:
        print("Review-only mode. No database was created or updated.")
        print(f"database_path: {args.database_path}")
        print(f"ticker_backup_path: {args.ticker_backup_path}")
        print(f"analysis_dates: {args.analysis_dates or 'inferred'}")
        ticker_source = args.tickers or (
            "stored historical universe"
            if args.refresh_existing or args.resume
            else "eligible universe"
        )
        print(f"tickers: {ticker_source}")
        print(f"rebuild: {args.rebuild}")
        print(f"refresh_existing: {args.refresh_existing}")
        print("Run again with --execute after reviewing the process.")
        return 0

    builder = (
        rebuild_magic_formula_results_database
        if args.rebuild
        else build_magic_formula_results_database
    )
    summary = builder(
        db_path=args.database_path,
        analysis_dates=args.analysis_dates,
        ticker_list=args.tickers,
        backup_path=args.ticker_backup_path,
        quiet=not args.verbose,
        refresh_symbols=not (args.resume or args.refresh_existing),
        skip_completed_dates=args.resume,
    )
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
