from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_cli.core.specs import (
    SPECS_END_MARKER,
    SPECS_START_MARKER,
    CpuInfo,
    OsInfo,
    SystemSpecs,
    WslInfo,
)
from llm_cli.main import app

runner = CliRunner()


def _fake_specs() -> SystemSpecs:
    return SystemSpecs(
        cpu=CpuInfo(model="Test CPU", logical_cores=4),
        ram_gb=16,
        gpus=[],
        cuda_runtime="not detected",
        os=OsInfo(description="Test OS"),
        wsl=WslInfo(distro="Ubuntu Test", kernel="x.y.z"),
        systemd_enabled=True,
        repo_root="/test/repo",
        data_root="/test/data",
    )


@pytest.fixture
def patch_detect_all(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "llm_cli.commands.specs.detect_all",
        lambda *a, **kw: _fake_specs(),
    )


def _write_paths(repo: Path, data_root: Path) -> None:
    (repo / "paths.yaml").write_text(
        f"data_root: {data_root}\nruntimes: ${{data_root}}/runtimes\n"
        f"models: ${{data_root}}/models\ncache: ${{data_root}}/cache\n",
        encoding="utf-8",
    )


def test_specs_creates_scaffold_when_file_missing(tmp_path: Path, patch_detect_all) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_paths(repo, tmp_path / "data")

    result = runner.invoke(app, ["specs"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code == 0, result.stdout
    specs_md = repo / "specs.md"
    assert specs_md.is_file()
    contents = specs_md.read_text(encoding="utf-8")
    assert SPECS_START_MARKER in contents
    assert SPECS_END_MARKER in contents
    assert "Test CPU" in contents
    assert "## Notes" in contents


def test_specs_preserves_notes_section(tmp_path: Path, patch_detect_all) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_paths(repo, tmp_path / "data")
    (repo / "specs.md").write_text(
        f"# System Specs\n\n{SPECS_START_MARKER}\nOLD\n{SPECS_END_MARKER}\n\n"
        "## Notes\n- preserved line\n",
        encoding="utf-8",
    )

    runner.invoke(app, ["specs"], env={"LLM_REPO_ROOT": str(repo)})

    contents = (repo / "specs.md").read_text(encoding="utf-8")
    assert "preserved line" in contents
    assert "OLD" not in contents
    assert "Test CPU" in contents


def test_specs_print_does_not_touch_file(tmp_path: Path, patch_detect_all) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_paths(repo, tmp_path / "data")

    result = runner.invoke(app, ["specs", "--print"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code == 0
    assert "Test CPU" in result.stdout
    assert not (repo / "specs.md").exists()


def test_specs_check_clean_exits_zero(tmp_path: Path, patch_detect_all) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_paths(repo, tmp_path / "data")

    runner.invoke(app, ["specs"], env={"LLM_REPO_ROOT": str(repo)})  # establish baseline
    result = runner.invoke(app, ["specs", "--check"], env={"LLM_REPO_ROOT": str(repo)})

    # Detection is identical, so the auto block matches; exit 0.
    assert result.exit_code == 0


def test_specs_check_drift_exits_nonzero(tmp_path: Path, monkeypatch, patch_detect_all) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_paths(repo, tmp_path / "data")
    runner.invoke(app, ["specs"], env={"LLM_REPO_ROOT": str(repo)})

    drifted = SystemSpecs(
        cpu=CpuInfo(model="DIFFERENT CPU", logical_cores=8),
        ram_gb=32,
    )
    monkeypatch.setattr("llm_cli.commands.specs.detect_all", lambda *a, **kw: drifted)

    result = runner.invoke(app, ["specs", "--check"], env={"LLM_REPO_ROOT": str(repo)})
    assert result.exit_code != 0
