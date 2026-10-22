"""The starter archive must be selective, valid, and non-destructive."""

import hashlib
import json
import sqlite3
import zipfile

import pytest

from Securities_DB import package_databases
from Securities_DB.create_database import create_database
from Securities_DB.magic_formula_database import create_magic_formula_schema
from Securities_DB.package_databases import (
    export_starter_data,
    install_starter_data,
)


@pytest.fixture
def starter_bundle(monkeypatch, tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    monkeypatch.setenv("REVEAL_DATA_ROOT", str(source_root))
    create_database()
    source_db = source_root / "Securities_DB" / "investment.db"
    with sqlite3.connect(source_db) as conn:
        conn.execute(
            "INSERT INTO sec_tickers VALUES ('AAA', '1', 'Example A')"
        )
        conn.execute(
            "INSERT INTO sec_tickers VALUES ('BBB', '2', 'Example B')"
        )
        conn.execute("""
            INSERT INTO ohlcv_daily (ticker, date, close, adjusted_close)
            VALUES ('AAA', '2024-05-01', 10, 10),
                   ('BBB', '2024-05-01', 20, 20)
        """)
    source_magic = source_root / "Securities_DB" / "magic_formula_results.db"
    with sqlite3.connect(source_magic) as conn:
        create_magic_formula_schema(conn)
        conn.execute("INSERT INTO magic_formula_symbols VALUES ('AAA')")
        conn.execute("INSERT INTO magic_formula_symbols VALUES ('BBB')")

    bundle = tmp_path / "starter.zip"
    manifest = export_starter_data(source_root, bundle, ["aaa"])
    assert manifest["tickers"] == ["AAA"]
    assert manifest["row_counts"]["ohlcv_daily"] == 1
    assert bundle.is_file()
    return bundle, source_db, source_magic


def test_starter_archive_export_and_install(starter_bundle, tmp_path):
    bundle, source_db, source_magic = starter_bundle
    archive_bytes = bundle.read_bytes()

    installed_root = tmp_path / "installed"
    install_starter_data(bundle, installed_root)
    installed_db = installed_root / "Securities_DB" / "investment.db"
    installed_magic = (
        installed_root / "Securities_DB" / "magic_formula_results.db"
    )
    with sqlite3.connect(installed_db) as conn:
        assert conn.execute("SELECT ticker FROM sec_tickers").fetchall() == [
            ("AAA",)
        ]
        count = conn.execute("SELECT count(*) FROM ohlcv_daily").fetchone()[0]
        assert count == 1
    with sqlite3.connect(installed_magic) as conn:
        assert conn.execute(
            "SELECT ticker FROM magic_formula_symbols"
        ).fetchall() == [("AAA",)]
    with pytest.raises(FileExistsError):
        install_starter_data(bundle, installed_root)
    assert bundle.read_bytes() == archive_bytes
    with sqlite3.connect(source_db) as conn:
        count = conn.execute("SELECT count(*) FROM sec_tickers").fetchone()[0]
        assert count == 2
    with sqlite3.connect(source_magic) as conn:
        count = conn.execute(
            "SELECT count(*) FROM magic_formula_symbols"
        ).fetchone()[0]
        assert count == 2


@pytest.mark.parametrize("existing_name", package_databases.DATABASE_NAMES)
def test_install_refuses_either_existing_database(
    starter_bundle, tmp_path, existing_name,
):
    bundle, _, _ = starter_bundle
    archive_bytes = bundle.read_bytes()
    database_dir = tmp_path / "installed" / "Securities_DB"
    database_dir.mkdir(parents=True)
    existing = database_dir / existing_name
    existing.write_bytes(b"original database sentinel")

    with pytest.raises(FileExistsError, match="will not replace"):
        install_starter_data(bundle, database_dir.parent)

    assert existing.read_bytes() == b"original database sentinel"
    assert sorted(path.name for path in database_dir.iterdir()) == [
        existing_name
    ]
    assert bundle.read_bytes() == archive_bytes


@pytest.mark.parametrize("raise_after_link", [False, True])
def test_second_install_failure_restores_existing_directory(
    starter_bundle, tmp_path, monkeypatch, raise_after_link,
):
    bundle, _, _ = starter_bundle
    archive_bytes = bundle.read_bytes()
    database_dir = tmp_path / "installed" / "Securities_DB"
    database_dir.mkdir(parents=True)
    marker = database_dir / "keep.txt"
    marker.write_text("untouched", encoding="utf-8")
    actual_link = package_databases.os.link

    def fail_on_second(source, target):
        if target.name == "magic_formula_results.db":
            if raise_after_link:
                actual_link(source, target)
            raise OSError("simulated second database failure")
        actual_link(source, target)

    monkeypatch.setattr(package_databases.os, "link", fail_on_second)
    with pytest.raises(OSError, match="simulated second database failure"):
        install_starter_data(bundle, database_dir.parent)

    assert sorted(path.name for path in database_dir.iterdir()) == [
        "keep.txt"
    ]
    assert marker.read_text(encoding="utf-8") == "untouched"
    assert bundle.read_bytes() == archive_bytes


def test_second_install_failure_removes_new_destination_directories(
    starter_bundle, tmp_path, monkeypatch,
):
    bundle, _, _ = starter_bundle
    data_root = tmp_path / "new" / "data-root"
    actual_link = package_databases.os.link

    def fail_on_second(source, target):
        if target.name == "magic_formula_results.db":
            raise OSError("simulated second database failure")
        actual_link(source, target)

    monkeypatch.setattr(package_databases.os, "link", fail_on_second)
    with pytest.raises(OSError, match="simulated second database failure"):
        install_starter_data(bundle, data_root)

    assert not data_root.exists()
    assert not data_root.parent.exists()


def test_both_files_are_validated_before_creating_destination(
    starter_bundle, tmp_path, monkeypatch,
):
    bundle, _, _ = starter_bundle
    data_root = tmp_path / "new-data-root"
    original_sha256 = package_databases._sha256

    def corrupt_second_checksum(path):
        if path.name == "magic_formula_results.db":
            return "wrong checksum"
        return original_sha256(path)

    monkeypatch.setattr(
        package_databases, "_sha256", corrupt_second_checksum
    )
    with pytest.raises(ValueError, match="Checksum mismatch"):
        install_starter_data(bundle, data_root)

    assert not data_root.exists()


@pytest.mark.parametrize("broken_database", package_databases.DATABASE_NAMES)
@pytest.mark.parametrize("destination_exists", [False, True])
def test_foreign_key_violation_rejects_archive_without_installing(
    starter_bundle, tmp_path, broken_database, destination_exists,
):
    bundle, _, _ = starter_bundle
    original_archive = bundle.read_bytes()
    with zipfile.ZipFile(bundle) as archive:
        members = {
            name: archive.read(name) for name in archive.namelist()
        }

    database_copy = tmp_path / broken_database
    database_copy.write_bytes(members[broken_database])
    with sqlite3.connect(database_copy) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        if broken_database == "investment.db":
            conn.execute(
                "INSERT INTO ohlcv_meta (ticker) VALUES ('MISSING')"
            )
        else:
            conn.execute("""
                INSERT INTO magic_formula_quarterly_results (
                    ticker, quarter_date, associated_annual_date,
                    magic_formula_rank, return_on_capital_rank,
                    earnings_yield_rank, total_roc_ey_score
                ) VALUES ('MISSING', '2024-03-31', '2023-12-31', 1, 1, 1, 2)
            """)
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchone()

    members[broken_database] = database_copy.read_bytes()
    manifest = json.loads(members["manifest.json"])
    manifest["sha256"][broken_database] = hashlib.sha256(
        members[broken_database]
    ).hexdigest()
    members["manifest.json"] = json.dumps(manifest).encode()
    tampered_archive = tmp_path / "orphaned.zip"
    with zipfile.ZipFile(tampered_archive, "w") as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)
    archive_bytes = tampered_archive.read_bytes()

    destination = tmp_path / "untouched-destination"
    if destination_exists:
        destination.mkdir()
        (destination / "keep.txt").write_text("original", encoding="utf-8")
    with pytest.raises(
        ValueError, match=f"foreign-key check failed for {broken_database}"
    ):
        install_starter_data(tampered_archive, destination)

    if destination_exists:
        assert sorted(path.name for path in destination.iterdir()) == [
            "keep.txt"
        ]
        assert (destination / "keep.txt").read_text(
            encoding="utf-8"
        ) == "original"
    else:
        assert not destination.exists()
    assert bundle.read_bytes() == original_archive
    assert tampered_archive.read_bytes() == archive_bytes
