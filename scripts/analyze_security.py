"""Command-line entry point for Reveal security analysis."""

from dataclasses import asdict, is_dataclass
from datetime import date
import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mvp import service as mvp_service  # noqa: E402


def _json_default(value):
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"{value!r} is not JSON serializable")


def _result_to_dict(result) -> dict:
    if is_dataclass(result):
        return asdict(result)
    return dict(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Reveal analysis for one or more securities."
    )
    parser.add_argument("tickers", nargs="+", help="Ticker symbol(s) to analyze.")
    parser.add_argument(
        "--analysis-date",
        help="Optional analysis date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format. Defaults to json.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results = [
        _result_to_dict(
            mvp_service.analyze_security(
                ticker.upper(),
                analysis_date=args.analysis_date,
            )
        )
        for ticker in args.tickers
    ]

    if args.format == "json":
        output = results[0] if len(results) == 1 else results
        print(json.dumps(output, default=_json_default, indent=2, sort_keys=True))
        return 0

    for result in results:
        warnings = result.get("calculation_warnings") or ()
        print(f"{result.get('ticker', '')}: {result.get('company_name', '')}")
        print(f"analysis_date: {result.get('analysis_date', '')}")
        print(f"data_complete: {result.get('data_complete', False)}")
        if warnings:
            print("warnings: " + "; ".join(warnings))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
