from pathlib import Path
import tomllib

from scripts import setup_project


def _write_template(project_root: Path) -> None:
    (project_root / "requirements.lock").write_text(
        "numpy==2.4.2\n",
        encoding="utf-8",
    )


def test_install_target_selects_requested_dependency_groups(tmp_path):
    assert setup_project._install_target(
        tmp_path,
        include_dev=False,
        include_notebooks=False,
    ) == str(tmp_path)
    assert (
        setup_project._install_target(
            tmp_path,
            include_dev=True,
            include_notebooks=True,
        )
        == f"{tmp_path}[dev,notebooks]"
    )


def test_main_dry_run_does_not_create_environment_or_configuration(
    tmp_path,
    monkeypatch,
    capsys,
):
    _write_template(tmp_path)
    monkeypatch.setattr(setup_project, "PROJECT_ROOT", tmp_path)

    assert setup_project.main(["--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "[dev]" in output
    assert "requirements.lock" in output
    assert "pip check" in output
    assert not (tmp_path / ".venv").exists()
    assert not (tmp_path / "configuration.py").exists()


def test_legacy_no_config_flag_remains_accepted():
    args = setup_project.build_parser().parse_args(["--no-config", "--dry-run"])
    assert args.no_config is True


def test_lock_includes_pinned_runtime_and_development_dependencies():
    project_root = Path(__file__).resolve().parents[1]
    with (project_root / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    expected = set(pyproject["project"]["dependencies"])
    expected.update(pyproject["project"]["optional-dependencies"]["dev"])
    locked = {
        line.strip()
        for line in (project_root / "requirements.lock")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert expected <= locked
