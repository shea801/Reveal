"""Installed launcher for the Reveal dashboard."""

from __future__ import annotations

def main(argv: list[str] | None = None) -> int:
    from dashboard.app import main as run_dashboard

    return run_dashboard(argv)


if __name__ == "__main__":
    raise SystemExit(main())
