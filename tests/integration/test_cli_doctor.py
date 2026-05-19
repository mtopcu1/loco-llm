from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_cli.core.doctor import CheckStatus, Requirement, RequirementResult
from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def _configure(tmp_path: Path, repo: Path) -> None:
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})


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


def _write_runtime(repo: Path, runtime_id: str, requires_yaml: str, build_yaml: str = "") -> None:
    rt = repo / "runtimes" / runtime_id
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        f"id: {runtime_id}\n"
        "official: true\n"
        f"{build_yaml}"
        "requires:\n"
        f"{requires_yaml}",
        encoding="utf-8",
    )
    for script in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / script).write_text("#!/usr/bin/env bash\n", encoding="utf-8")


def test_doctor_render_requirements_writes_md(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_requirements(repo)
    _write_runtime(
        repo,
        "rt-a",
        "  - id: cmake\n"
        "    verify: { cmd: cmake --version, version_regex: '([0-9.]+)' }\n"
        "    install_hint: install cmake\n",
    )
    _configure(tmp_path, repo)

    result = runner.invoke(app, ["doctor", "render-requirements"])

    assert result.exit_code == 0, result.stdout
    md = (repo / "requirements.md").read_text(encoding="utf-8")
    assert "| python |" in md
    assert "| git |" in md
    assert "## Runtime: rt-a" in md
    assert "| cmake |" in md
    assert "auto-generated" in md.lower()


def test_doctor_runs_all_checks_and_succeeds(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_requirements(repo)
    _configure(tmp_path, repo)

    def fake_check_all(requirements, **kw):
        return [
            RequirementResult(requirement=r, status=CheckStatus.OK, detected_version="x.y")
            for r in requirements
        ]

    monkeypatch.setattr("llm_cli.commands.doctor.check_all", fake_check_all)
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "python" in result.stdout
    assert "git" in result.stdout


def test_doctor_exits_nonzero_when_any_check_fails(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_requirements(repo)
    _configure(tmp_path, repo)

    def fake_check_all(requirements, **kw):
        results = []
        for i, r in enumerate(requirements):
            status = CheckStatus.OK if i == 0 else CheckStatus.MISSING
            results.append(RequirementResult(requirement=r, status=status))
        return results

    monkeypatch.setattr("llm_cli.commands.doctor.check_all", fake_check_all)
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code != 0


def test_doctor_missing_requirements_yaml_errors(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _configure(tmp_path, repo)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code != 0
    assert "requirements.yaml" in (result.stdout or "") + (result.stderr or "")


def test_doctor_default_scopes_to_installed_runtime_deps(tmp_path: Path) -> None:
    from llm_cli.core.install_record import InstallRecord, write_record

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.yaml").write_text("[]\n", encoding="utf-8")
    _write_runtime(
        repo,
        "rt-a",
        "  - id: definitely-not-on-path-zzz\n"
        "    verify: { cmd: definitely-not-on-path-zzz, version_regex: '([0-9.]+)' }\n"
        "    install_hint: nope\n",
    )
    runtimes_dir = tmp_path / "data" / "runtimes"
    write_record(
        runtimes_dir,
        InstallRecord(
            runtime_id="rt-a",
            installed_at="2026-05-17T00:00:00Z",
            build_params={},
            build_sh_sha256="x",
            verify_passed=True,
            schema_hash="y",
        ),
    )
    _configure(tmp_path, repo)

    result = runner.invoke(app, ["doctor"], catch_exceptions=False)

    assert "definitely-not-on-path-zzz" in result.stdout
    assert result.exit_code == 1


def test_doctor_runtime_flag_scopes_to_one_runtime(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.yaml").write_text("[]\n", encoding="utf-8")
    _write_runtime(
        repo,
        "rt-a",
        "  - id: cmake\n"
        "    verify: { cmd: cmake --version, version_regex: '([0-9.]+)' }\n"
        "    install_hint: install cmake\n",
    )
    _write_runtime(
        repo,
        "rt-b",
        "  - id: git\n"
        "    verify: { cmd: git --version, version_regex: '([0-9.]+)' }\n"
        "    install_hint: install git\n",
    )
    _configure(tmp_path, repo)
    seen_ids: list[str] = []

    def fake_check_all(requirements, **kw):
        seen_ids.extend(r.id for r in requirements)
        return [
            RequirementResult(requirement=r, status=CheckStatus.OK, detected_version="x.y")
            for r in requirements
        ]

    monkeypatch.setattr("llm_cli.commands.doctor.check_all", fake_check_all)

    result = runner.invoke(app, ["doctor", "--runtime", "rt-b"])

    assert result.exit_code == 0, result.stdout
    assert seen_ids == ["git"]


def test_doctor_runtime_flag_rejects_unknown_runtime(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.yaml").write_text("[]\n", encoding="utf-8")
    _configure(tmp_path, repo)

    def fake_check_all(requirements, **kw):  # pragma: no cover - should not be reached
        raise AssertionError("doctor should reject unknown runtime before checks")

    monkeypatch.setattr("llm_cli.commands.doctor.check_all", fake_check_all)

    result = runner.invoke(app, ["doctor", "--runtime", "ollamacpp"])

    assert result.exit_code == 1
    assert "unknown runtime 'ollamacpp'" in result.stdout


def test_doctor_runtime_flag_skips_conditional_reqs_when_uninstalled(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.yaml").write_text("[]\n", encoding="utf-8")
    _write_runtime(
        repo,
        "rt-a",
        "  - id: cmake\n"
        "    verify: { cmd: cmake --version, version_regex: '([0-9.]+)' }\n"
        "    install_hint: install cmake\n"
        "  - id: nvcc\n"
        "    when: { build.flavor: cuda }\n"
        "    verify: { cmd: nvcc --version, version_regex: '([0-9.]+)' }\n"
        "    install_hint: install cuda\n",
        build_yaml=(
            "build:\n"
            "  flavor:\n"
            "    type: enum\n"
            "    values: [cuda, cpu]\n"
        ),
    )
    _configure(tmp_path, repo)
    seen_ids: list[str] = []

    def fake_check_all(requirements, **kw):
        seen_ids.extend(r.id for r in requirements)
        return [
            RequirementResult(requirement=r, status=CheckStatus.OK, detected_version="x.y")
            for r in requirements
        ]

    monkeypatch.setattr("llm_cli.commands.doctor.check_all", fake_check_all)

    result = runner.invoke(app, ["doctor", "--runtime", "rt-a"])

    assert result.exit_code == 0, result.stdout
    assert sorted(seen_ids) == ["cmake"]


def test_doctor_all_flag_includes_uninstalled_runtime_baseline_reqs(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.yaml").write_text("[]\n", encoding="utf-8")
    _write_runtime(
        repo,
        "rt-a",
        "  - id: cmake\n"
        "    verify: { cmd: cmake --version, version_regex: '([0-9.]+)' }\n"
        "    install_hint: install cmake\n"
        "  - id: nvcc\n"
        "    when: { build.flavor: cuda }\n"
        "    verify: { cmd: nvcc --version, version_regex: '([0-9.]+)' }\n"
        "    install_hint: install cuda\n",
        build_yaml=(
            "build:\n"
            "  flavor:\n"
            "    type: enum\n"
            "    values: [cuda, cpu]\n"
        ),
    )
    _configure(tmp_path, repo)
    seen_ids: list[str] = []

    def fake_check_all(requirements, **kw):
        seen_ids.extend(r.id for r in requirements)
        return [
            RequirementResult(requirement=r, status=CheckStatus.OK, detected_version="x.y")
            for r in requirements
        ]

    monkeypatch.setattr("llm_cli.commands.doctor.check_all", fake_check_all)

    result = runner.invoke(app, ["doctor", "--all"])

    assert result.exit_code == 0, result.stdout
    assert sorted(seen_ids) == ["cmake"]
