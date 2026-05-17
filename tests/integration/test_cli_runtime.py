from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from llm_cli.core.install_record import InstallRecord, read_record, write_record
from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def _scaffold(repo_root_dir: Path, runtimes_dir: Path) -> None:
    repo_root_dir.mkdir(parents=True, exist_ok=True)
    rt = repo_root_dir / "runtimes" / "rt-a"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: rt-a\ndisplay_name: Alpha\nofficial: true\n",
        encoding="utf-8",
    )
    for script in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / script).write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    rt2 = repo_root_dir / "runtimes" / "rt-b"
    rt2.mkdir(parents=True)
    (rt2 / "manifest.yaml").write_text(
        "id: rt-b\ndisplay_name: Beta\n",
        encoding="utf-8",
    )
    for script in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt2 / script).write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    runtimes_dir.mkdir(parents=True, exist_ok=True)
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


def _scaffold_llamacpp(repo: Path) -> None:
    rt = repo / "runtimes" / "llamacpp"
    rt.mkdir(parents=True)
    (rt / "manifest.yaml").write_text(
        "id: llamacpp\n"
        "official: true\n"
        "build:\n"
        "  flavor:\n"
        "    type: enum\n"
        "    values: [cuda, cpu]\n"
        "    default: cpu\n"
        "  jobs:\n"
        "    type: int\n"
        "    default: 0\n"
        "serve:\n"
        "  ctx:\n"
        "    type: int\n"
        "    default: 8192\n",
        encoding="utf-8",
    )
    for script in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / script).write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")


def test_runtime_list_shows_official_and_installed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    runtimes_dir = tmp_path / "data" / "runtimes"
    _scaffold(repo, runtimes_dir)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})

    result = runner.invoke(app, ["runtime", "list"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "rt-a" in result.stdout
    assert "rt-b" in result.stdout
    assert "official" in result.stdout.lower() or "yes" in result.stdout.lower()


def test_runtime_info_shows_install_and_schema(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    runtimes_dir = tmp_path / "data" / "runtimes"
    _scaffold(repo, runtimes_dir)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})

    result = runner.invoke(app, ["runtime", "info", "rt-a"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "rt-a" in result.stdout
    assert "installed" in result.stdout.lower()


def test_runtime_info_unknown_id(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    runtimes_dir = tmp_path / "data" / "runtimes"
    _scaffold(repo, runtimes_dir)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})

    result = runner.invoke(app, ["runtime", "info", "no-such"], catch_exceptions=False)

    assert result.exit_code == 1


@patch("llm_cli.commands.runtime_cmd._run_build_script", return_value=0)
@patch("llm_cli.commands.runtime_cmd._run_verify_script", return_value=0)
def test_runtime_install_writes_record_with_defaults(
    mock_verify, mock_build, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    (tmp_path / "data" / "runtimes" / "llamacpp").mkdir(parents=True)

    result = runner.invoke(
        app, ["runtime", "install", "llamacpp", "--yes"], catch_exceptions=False
    )

    assert result.exit_code == 0
    rec = read_record(tmp_path / "data" / "runtimes", "llamacpp")
    assert rec is not None
    assert rec.build_params == {"flavor": "cpu", "jobs": 0}
    assert rec.verify_passed is True
    mock_build.assert_called_once()
    env = mock_build.call_args.kwargs["env"]
    assert env["LLM_BUILD_FLAVOR"] == "cpu"
    assert env["LLM_BUILD_JOBS"] == "0"


@patch("llm_cli.commands.runtime_cmd._run_build_script", return_value=0)
@patch("llm_cli.commands.runtime_cmd._run_verify_script", return_value=0)
def test_runtime_install_param_override(
    mock_verify, mock_build, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})

    result = runner.invoke(
        app,
        [
            "runtime",
            "install",
            "llamacpp",
            "--yes",
            "--param",
            "flavor=cuda",
            "--param",
            "jobs=4",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    rec = read_record(tmp_path / "data" / "runtimes", "llamacpp")
    assert rec is not None
    assert rec.build_params == {"flavor": "cuda", "jobs": 4}
    mock_verify.assert_called_once()
    mock_build.assert_called_once()


@patch("llm_cli.commands.runtime_cmd._run_build_script", return_value=1)
def test_runtime_install_build_failure_no_record(mock_build, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})

    result = runner.invoke(
        app, ["runtime", "install", "llamacpp", "--yes"], catch_exceptions=False
    )

    assert result.exit_code != 0
    assert read_record(tmp_path / "data" / "runtimes", "llamacpp") is None
    mock_build.assert_called_once()


def test_runtime_uninstall_removes_marker_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    runtimes_dir = tmp_path / "data" / "runtimes"
    _scaffold(repo, runtimes_dir)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    (runtimes_dir / "rt-a" / "leftover").write_text("keep me", encoding="utf-8")

    result = runner.invoke(
        app, ["runtime", "uninstall", "rt-a", "--yes"], catch_exceptions=False
    )

    assert result.exit_code == 0
    assert not (runtimes_dir / "rt-a" / ".installed").exists()
    assert (runtimes_dir / "rt-a" / "leftover").exists()


def test_runtime_uninstall_purge_removes_tree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    runtimes_dir = tmp_path / "data" / "runtimes"
    _scaffold(repo, runtimes_dir)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    (runtimes_dir / "rt-a" / "leftover").write_text("bye", encoding="utf-8")

    result = runner.invoke(
        app,
        ["runtime", "uninstall", "rt-a", "--purge", "--yes"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert not (runtimes_dir / "rt-a").exists()


def test_runtime_uninstall_not_installed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})

    result = runner.invoke(
        app, ["runtime", "uninstall", "llamacpp", "--yes"], catch_exceptions=False
    )

    assert result.exit_code == 0
    assert (
        "nothing to uninstall" in result.stdout.lower()
        or "not installed" in result.stdout.lower()
    )


@patch("llm_cli.commands.runtime_cmd._run_build_script", return_value=0)
@patch("llm_cli.commands.runtime_cmd._run_verify_script", return_value=0)
def test_runtime_rebuild_reuses_params(
    mock_verify, mock_build, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    (tmp_path / "data" / "runtimes" / "llamacpp").mkdir(parents=True)

    runner.invoke(
        app,
        [
            "runtime",
            "install",
            "llamacpp",
            "--yes",
            "--param",
            "flavor=cuda",
            "--param",
            "jobs=2",
        ],
        catch_exceptions=False,
    )
    mock_build.reset_mock()

    result = runner.invoke(
        app, ["runtime", "rebuild", "llamacpp"], catch_exceptions=False
    )

    assert result.exit_code == 0
    env = mock_build.call_args.kwargs["env"]
    assert env["LLM_BUILD_FLAVOR"] == "cuda"
    assert env["LLM_BUILD_JOBS"] == "2"
    mock_verify.assert_called()


@patch("llm_cli.commands.runtime_cmd._run_build_script", return_value=0)
@patch("llm_cli.commands.runtime_cmd._run_verify_script", return_value=0)
def test_runtime_rebuild_reset_reprompts_via_yes_defaults(
    mock_verify, mock_build, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold_llamacpp(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    (tmp_path / "data" / "runtimes" / "llamacpp").mkdir(parents=True)

    runner.invoke(
        app,
        ["runtime", "install", "llamacpp", "--yes", "--param", "flavor=cuda"],
        catch_exceptions=False,
    )

    result = runner.invoke(
        app,
        ["runtime", "rebuild", "llamacpp", "--reset", "--yes"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    rec = read_record(tmp_path / "data" / "runtimes", "llamacpp")
    assert rec is not None
    assert rec.build_params["flavor"] == "cpu"
    mock_verify.assert_called()
    mock_build.assert_called()
