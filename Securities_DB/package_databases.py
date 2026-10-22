"""Export and install a small, explicitly selected Reveal SQLite starter set.

This command never changes source databases. Review the selected tickers and
the resulting archive before including it in a public release.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import zipfile

from runtime_config import get_data_root


PACKAGE_NAME = "reveal_starter_data.zip"
PACKAGE_VERSION = 1
MAX_ARCHIVE_BYTES = 95 * 1024 * 1024
FINANCIAL_TABLES = (
    "balance_sheet_annual", "balance_sheet_quarterly",
    "cash_flow_annual", "cash_flow_quarterly",
    "income_annual", "income_quarterly",
    "earnings_annual", "earnings_quarterly",
)
TICKER_TABLES = (
    "sec_tickers", "company_details", *FINANCIAL_TABLES,
    "ohlcv_daily", "ohlcv_meta", "market_capitalization",
    "magic_formula_symbols", "sec_ticker_cik_identity",
    "sec_statement_matches",
)
DATABASE_NAMES = ("investment.db", "magic_formula_results.db")


def _connect_readonly(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _schema_sql(conn: sqlite3.Connection, kind: str, name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type=? AND name=?",
        (kind, name),
    ).fetchone()
    if row is None or not row["sql"]:
        raise ValueError(f"Source database lacks {kind} {name}")
    return row["sql"]


def _copy_rows(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    table: str,
    column: str,
    values: list[str],
) -> int:
    if not values:
        return 0
    columns = [
        row["name"] for row in source.execute(f"PRAGMA table_info({table})")
    ]
    if column not in columns:
        raise ValueError(f"Source table {table} lacks {column}")
    quoted = ", ".join(f'"{name}"' for name in columns)
    placeholders = ", ".join("?" for _ in columns)
    insert = f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})'
    count = 0
    for start in range(0, len(values), 400):
        chunk = values[start:start + 400]
        selected = ", ".join("?" for _ in chunk)
        cursor = source.execute(
            f'SELECT {quoted} FROM "{table}" WHERE "{column}" IN ({selected})',
            chunk,
        )
        while rows := cursor.fetchmany(1000):
            target.executemany(insert, [tuple(row) for row in rows])
            count += len(rows)
    return count


def _copy_investment_db(
    source_path: Path,
    target_path: Path,
    tickers: list[str],
) -> dict[str, int]:
    with closing(_connect_readonly(source_path)) as source:
        source.execute("BEGIN")
        target = sqlite3.connect(target_path)
        try:
            target.execute("PRAGMA foreign_keys=OFF")
            for table in ("sec_filing_metadata", *TICKER_TABLES):
                target.execute(_schema_sql(source, "table", table))
            counts = {}
            for table in TICKER_TABLES:
                column = "Symbol" if table == "company_details" else "ticker"
                counts[table] = _copy_rows(
                    source, target, table, column, tickers
                )
            if counts["sec_tickers"] != len(tickers):
                raise ValueError(
                    "Every selected ticker must exist in sec_tickers"
                )
            ciks = [row[0] for row in target.execute(
                "SELECT DISTINCT cik FROM sec_statement_matches "
                "WHERE cik IS NOT NULL"
            )]
            counts["sec_filing_metadata"] = _copy_rows(
                source, target, "sec_filing_metadata", "cik", ciks
            )
            for row in source.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND sql IS NOT NULL AND tbl_name IN ("
                + ",".join(
                    "?" for _ in ("sec_filing_metadata", *TICKER_TABLES)
                )
                + ")",
                ("sec_filing_metadata", *TICKER_TABLES),
            ):
                target.execute(row["sql"])
            target.commit()
            target.execute("PRAGMA foreign_keys=ON")
            if target.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError(
                    "Starter investment database has broken references"
                )
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError(
                    "Starter investment database failed integrity check"
                )
            target.execute("VACUUM")
            return counts
        finally:
            target.close()


def _copy_magic_db(
    source_path: Path,
    target_path: Path,
    tickers: list[str],
) -> int:
    with closing(_connect_readonly(source_path)) as source:
        source.execute("BEGIN")
        target = sqlite3.connect(target_path)
        target.row_factory = sqlite3.Row
        try:
            for table in (
                "magic_formula_symbols", "magic_formula_quarterly_results"
            ):
                target.execute(_schema_sql(source, "table", table))
            _copy_rows(
                source, target, "magic_formula_symbols", "ticker", tickers
            )
            count = _copy_rows(
                source, target, "magic_formula_quarterly_results",
                "ticker", tickers,
            )
            for row in source.execute(
                "SELECT type, sql FROM sqlite_master WHERE sql IS NOT NULL "
                "AND type IN ('index', 'view')"
            ):
                target.execute(row["sql"])
            target.commit()
            if target.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError(
                    "Starter ranking database has broken references"
                )
            target.execute("VACUUM")
            return count
        finally:
            target.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_starter_data(
    source_root: Path,
    output: Path,
    tickers: list[str],
) -> dict:
    """Build a reviewable ZIP from selected rows; leave sources intact."""
    selected = sorted({
        ticker.strip().upper() for ticker in tickers if ticker.strip()
    })
    if not selected:
        raise ValueError("Select at least one ticker with --ticker")
    if output.exists():
        raise FileExistsError(output)
    source_dir = source_root / "Securities_DB"
    with tempfile.TemporaryDirectory(prefix="reveal-starter-") as scratch:
        temp_dir = Path(scratch)
        investment = temp_dir / DATABASE_NAMES[0]
        magic = temp_dir / DATABASE_NAMES[1]
        counts = _copy_investment_db(
            source_dir / DATABASE_NAMES[0], investment, selected
        )
        rank_count = _copy_magic_db(
            source_dir / DATABASE_NAMES[1], magic, selected
        )
        manifest = {
            "format_version": PACKAGE_VERSION,
            "tickers": selected,
            "row_counts": {**counts, "magic_formula_results": rank_count},
            "sha256": {
                name: _sha256(temp_dir / name) for name in DATABASE_NAMES
            },
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=".reveal-starter-", suffix=".zip",
            dir=output.parent, delete=False,
        ) as stream:
            temporary_output = Path(stream.name)
        try:
            with zipfile.ZipFile(
                temporary_output, "w", compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                for name in DATABASE_NAMES:
                    archive.write(temp_dir / name, arcname=name)
                archive.writestr(
                    "manifest.json", json.dumps(manifest, indent=2)
                )
            if temporary_output.stat().st_size > MAX_ARCHIVE_BYTES:
                raise ValueError(
                    "Starter archive exceeds GitHub's 100 MB file limit"
                )
            os.replace(temporary_output, output)
        finally:
            temporary_output.unlink(missing_ok=True)
    return manifest


def install_starter_data(bundle: Path, data_root: Path) -> dict:
    """Validate both SQLite files before publishing either one."""
    if not bundle.is_file():
        raise FileNotFoundError(
            f"Starter archive is absent: {bundle}. Export and review it first."
        )
    database_dir = data_root / "Securities_DB"
    if any(os.path.lexists(database_dir / name) for name in DATABASE_NAMES):
        raise FileExistsError(
            "A database already exists; starter install will not replace it"
        )
    with zipfile.ZipFile(bundle) as archive:
        if set(archive.namelist()) != {*DATABASE_NAMES, "manifest.json"}:
            raise ValueError("Starter archive contains unexpected members")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format_version") != PACKAGE_VERSION:
            raise ValueError("Unsupported starter archive format")
        missing_directories = []
        staging_parent = data_root
        while not staging_parent.exists():
            missing_directories.append(staging_parent)
            staging_parent = staging_parent.parent
        if not staging_parent.is_dir():
            raise NotADirectoryError(staging_parent)
        created_database_dir = False
        try:
            with tempfile.TemporaryDirectory(
                prefix=".reveal-install-", dir=staging_parent
            ) as scratch:
                temp_dir = Path(scratch)
                for name in DATABASE_NAMES:
                    path = temp_dir / name
                    with archive.open(name) as source, path.open("wb") as target:
                        for chunk in iter(
                            lambda: source.read(1024 * 1024), b""
                        ):
                            target.write(chunk)
                    if _sha256(path) != manifest["sha256"][name]:
                        raise ValueError(f"Checksum mismatch for {name}")
                    with closing(_connect_readonly(path)) as conn:
                        valid = conn.execute(
                            "PRAGMA integrity_check"
                        ).fetchone()[0]
                        if valid != "ok":
                            raise ValueError(
                                f"SQLite integrity check failed for {name}"
                            )
                        if conn.execute(
                            "PRAGMA foreign_key_check"
                        ).fetchone() is not None:
                            raise ValueError(
                                f"SQLite foreign-key check failed for {name}"
                            )

                if any(
                    os.path.lexists(database_dir / name)
                    for name in DATABASE_NAMES
                ):
                    raise FileExistsError(
                        "A database already exists; starter install will not replace it"
                    )
                data_root.mkdir(parents=True, exist_ok=True)
                created_database_dir = not database_dir.exists()
                database_dir.mkdir(exist_ok=True)
                try:
                    for name in DATABASE_NAMES:
                        os.link(temp_dir / name, database_dir / name)
                except BaseException:
                    for name in DATABASE_NAMES:
                        staged = temp_dir / name
                        installed = database_dir / name
                        if os.path.lexists(installed) and os.path.samefile(
                            staged, installed
                        ):
                            installed.unlink()
                    raise
        except BaseException:
            if created_database_dir and database_dir.is_dir():
                database_dir.rmdir()
            for directory in missing_directories:
                if directory.is_dir():
                    directory.rmdir()
            raise
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    export = actions.add_parser(
        "export", help="Create a selected starter archive"
    )
    export.add_argument("--source-root", type=Path)
    export.add_argument(
        "--output", type=Path, default=Path(__file__).parent / PACKAGE_NAME
    )
    export.add_argument("--ticker", action="append", required=True)
    install = actions.add_parser(
        "install", help="Install the bundled starter archive"
    )
    install.add_argument(
        "--bundle", type=Path, default=Path(__file__).parent / PACKAGE_NAME
    )
    install.add_argument("--data-root", type=Path)
    args = parser.parse_args(argv)
    if args.action == "export":
        result = export_starter_data(
            args.source_root or get_data_root(), args.output, args.ticker
        )
    else:
        result = install_starter_data(
            args.bundle, args.data_root or get_data_root()
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
