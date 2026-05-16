from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_cli.core.doctor import CheckStatus, Requirement, RequirementResult
from llm_cli.main import app

runner = CliRunner()


def _write_requirements(repo: Path) -> None:
    (repo / "requirements.yaml").write_text(
        "- id: python\n"
        "  name: Python\n"
        "  why: base\n"
        "  verify: { cmd: 'python3 --version', version_regex: 'Python\\s+([\\d.]+)', min: '3.11' }\n"
        "  install_hint: 'apt install python3.11'\n"
        "- id: git\n"
        "  name: Git\n"
        "  why: cloning\n"
        "  verify: { cmd: 'git --version', version_regex: 'git version\\s+([\\d.]+)' }\n"
        "  install_hint: 'apt install git'\n",
        encoding="utf-8",
    )


def test_doctor_render_requirements_writes_md(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_requirements(repo)

    result = runner.invoke(
        app, ["doctor", "render-requirements"], env={"LLM_REPO_ROOT": str(repo)}
    )

    assert result.exit_code == 0, result.stdout
    md = (repo / "requirements.md").read_text(encoding="utf-8")
    assert "| python |" in md
    assert "| git |" in md
    assert "auto-generated" in md.lower()


def test_doctor_runs_all_checks_and_succeeds(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_requirements(repo)

    def fake_check_all(requirements, **kw):
        return [
            RequirementResult(requirement=r, status=CheckStatus.OK, detected_version="x.y")
            for r in requirements
        ]

    monkeypatch.setattr("llm_cli.commands.doctor.check_all", fake_check_all)
    result = runner.invoke(app, ["doctor"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code == 0
    assert "python" in result.stdout
    assert "git" in result.stdout


def test_doctor_exits_nonzero_when_any_check_fails(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_requirements(repo)

    def fake_check_all(requirements, **kw):
        results = []
        for i, r in enumerate(requirements):
            status = CheckStatus.OK if i == 0 else CheckStatus.MISSING
            results.append(RequirementResult(requirement=r, status=status))
        return results

    monkeypatch.setattr("llm_cli.commands.doctor.check_all", fake_check_all)
    result = runner.invoke(app, ["doctor"], env={"LLM_REPO_ROOT": str(repo)})

    assert result.exit_code != 0


def test_doctor_missing_requirements_yaml_errors(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    result = runner.invoke(app, ["doctor"], env={"LLM_REPO_ROOT": str(repo)})
    assert result.exit_code != 0
    assert "requirements.yaml" in (result.stdout or "") + (result.stderr or "")
