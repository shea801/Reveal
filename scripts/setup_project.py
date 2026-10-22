"""Create a local environment and install the project reproducibly."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import venv


MINIMUM_PYTHON = (3, 11)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE_NAME = "requirements.lock"


def _venv_python(venv_path: Path, *, windows: bool | None = None) -> Path:
    is_windows = os.name == "nt" if windows is None else windows
    if is_windows:
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def _install_target(
    project_root: Path,
    *,
    include_dev: bool,
    include_notebooks: bool,
) -> str:
    extras = []
    if include_dev:
        extras.append("dev")
    if include_notebooks:
        extras.append("notebooks")

    suffix = f"[{','.join(extras)}]" if extras else ""
    return f"{project_root}{suffix}"


def _display_command(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _run(command: list[str], *, dry_run: bool) -> None:
    print(f"+ {_display_command(command)}")
    if not dry_run:
        subprocess.run(command, check=True)


def _activation_command(venv_path: Path) -> str:
    if os.name == "nt":
        return str(venv_path / "Scripts" / "Activate.ps1")
    return f"source {shlex.quote(str(venv_path / 'bin' / 'activate'))}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a virtual environment, install the Investment project, "
            "and verify its Python dependencies."
        )
    )
    parser.add_argument(
        "--venv",
        type=Path,
        default=Path(".venv"),
        help="Virtual-environment path. Defaults to .venv in the project root.",
    )
    parser.add_argument(
        "--runtime-only",
        action="store_true",
        help="Install only runtime dependencies, without pytest and ruff.",
    )
    parser.add_argument(
        "--with-notebooks",
        action="store_true",
        help="Also install Jupyter notebook dependencies.",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Deprecated compatibility flag; setup never creates configuration.py.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show setup actions without creating or installing anything.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(str(value) for value in MINIMUM_PYTHON)
        current = ".".join(str(value) for value in sys.version_info[:3])
        print(
            f"Python {required} or newer is required; found {current}.",
            file=sys.stderr,
        )
        return 2

    project_root = PROJECT_ROOT.resolve()
    lock_file = project_root / LOCK_FILE_NAME
    if not lock_file.is_file():
        print(f"Missing dependency constraints: {lock_file}", file=sys.stderr)
        return 2

    venv_path = args.venv
    if not venv_path.is_absolute():
        venv_path = project_root / venv_path
    venv_path = venv_path.resolve()

    python_path = _venv_python(venv_path)
    if not python_path.is_file():
        print(f"Creating virtual environment: {venv_path}")
        if not args.dry_run:
            venv.EnvBuilder(with_pip=True).create(venv_path)
    else:
        print(f"Using existing virtual environment: {venv_path}")

    install_target = _install_target(
        project_root,
        include_dev=not args.runtime_only,
        include_notebooks=args.with_notebooks,
    )
    python_command = str(python_path)
    _run(
        [
            python_command,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--constraint",
            str(lock_file),
            "--editable",
            install_target,
        ],
        dry_run=args.dry_run,
    )
    _run(
        [python_command, "-m", "pip", "check"],
        dry_run=args.dry_run,
    )
    _run(
        [
            python_command,
            "-c",
            (
                "import dash, dash_bootstrap_components, dashboard.launcher, "
                "numpy, pandas, requests; print('Runtime imports passed.')"
            ),
        ],
        dry_run=args.dry_run,
    )

    print("Setup complete.")
    print(f"Activate with: {_activation_command(venv_path)}")
    if not args.runtime_only:
        print("Run tests with: pytest -p no:cacheprovider Tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
