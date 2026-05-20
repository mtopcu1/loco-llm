"""Tests for git-based llm update."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def _init_repo(root: Path, tags: list[str], on_branch: str | None = None) -> None:
    """Initialize a fake clone with a sequence of tags and optional branch HEAD."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test"], check=True
    )
    (root / "pyproject.toml").write_text('[project]\nname = "loco-llm-cli"\n')
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "initial"], check=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "remote",
            "add",
            "origin",
            "https://github.com/mtopcu1/loco-llm.git",
        ],
        check=True,
    )
    for i, tag in enumerate(tags):
        if i > 0:
            (root / f"release-{tag}.txt").write_text(f"{tag}\n")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-q", "-m", f"release {tag}"],
                check=True,
            )
        subprocess.run(
            ["git", "-C", str(root), "tag", "-a", tag, "-m", tag], check=True
        )
    if on_branch is not None:
        subprocess.run(
            ["git", "-C", str(root), "checkout", "-q", "-b", on_branch], check=True
        )


@pytest.fixture
def fake_clone(tmp_path, monkeypatch):
    root = tmp_path / "loco"
    root.mkdir()
    _init_repo(root, tags=["v0.4.0", "v0.4.1"])
    monkeypatch.setenv("LOCO_LLM_HOME", str(root))
    monkeypatch.setattr(
        "llm_cli.commands.update_cmd._sync_deps", lambda _root: None
    )
    monkeypatch.setattr(
        "llm_cli.commands.update_cmd._fetch_remote", lambda _root, refspec=None: None
    )
    monkeypatch.setattr(
        "llm_cli.commands.update_cmd._ff_pull", lambda _root, _branch: None
    )
    monkeypatch.setattr(
        "llm_cli.commands.update_cmd._service_running", lambda: False
    )
    return root


def test_update_bare_already_on_latest_is_noop(fake_clone):
    subprocess.run(
        ["git", "-C", str(fake_clone), "checkout", "-q", "v0.4.1"], check=True
    )
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "already on latest stable" in result.stdout.lower()


def test_update_bare_advances_to_latest_tag(fake_clone):
    subprocess.run(
        ["git", "-C", str(fake_clone), "checkout", "-q", "v0.4.0"], check=True
    )
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "updated to v0.4.1" in result.stdout.lower()


def test_update_bare_reanchors_from_branch(fake_clone):
    subprocess.run(
        ["git", "-C", str(fake_clone), "checkout", "-q", "-b", "hotfix/x"],
        check=True,
    )
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "switching back to latest stable" in result.stdout.lower()
    assert "v0.4.1" in result.stdout


def test_update_branch_flag_checks_out_branch(fake_clone):
    subprocess.run(
        ["git", "-C", str(fake_clone), "branch", "hotfix/y", "v0.4.0"],
        check=True,
    )
    result = runner.invoke(app, ["update", "--branch", "hotfix/y"])
    assert result.exit_code == 0
    assert "not a stable release" in result.stdout.lower()
    head = subprocess.run(
        ["git", "-C", str(fake_clone), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head == "hotfix/y"


def test_update_tag_flag_pins_to_specific_tag(fake_clone):
    result = runner.invoke(app, ["update", "--tag", "v0.4.0"])
    assert result.exit_code == 0
    assert "v0.4.0" in result.stdout
    head = subprocess.run(
        ["git", "-C", str(fake_clone), "describe", "--tags", "--exact-match"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head == "v0.4.0"


def test_update_check_flag_exits_nonzero_when_behind(fake_clone):
    subprocess.run(
        ["git", "-C", str(fake_clone), "checkout", "-q", "v0.4.0"], check=True
    )
    result = runner.invoke(app, ["update", "--check"])
    assert result.exit_code == 1
    assert "v0.4.0" in result.stdout
    assert "v0.4.1" in result.stdout


def test_update_check_flag_exits_zero_when_up_to_date(fake_clone):
    subprocess.run(
        ["git", "-C", str(fake_clone), "checkout", "-q", "v0.4.1"], check=True
    )
    result = runner.invoke(app, ["update", "--check"])
    assert result.exit_code == 0


def test_sync_deps_targets_managed_venv_python(tmp_path, monkeypatch):
    root = tmp_path / "loco"
    venv_python = root / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")

    captured: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(
        "llm_cli.commands.update_cmd.shutil.which", lambda name: "/usr/bin/uv"
    )
    monkeypatch.setattr("llm_cli.commands.update_cmd.subprocess.run", fake_run)

    from llm_cli.commands.update_cmd import _sync_deps

    _sync_deps(root)

    assert captured == [
        [
            "/usr/bin/uv",
            "pip",
            "install",
            "--python",
            str(venv_python),
            "-e",
            str(root),
        ]
    ]


def test_update_refuses_unmanaged_directory(tmp_path, monkeypatch):
    empty = tmp_path / "not-a-clone"
    empty.mkdir()
    monkeypatch.setenv("LOCO_LLM_HOME", str(empty))
    result = runner.invoke(app, ["update"])
    assert result.exit_code != 0
    assert "not a managed install" in result.stdout.lower()


def test_update_rebuilds_dashboard_if_installed(monkeypatch):
    called = {"install": False}
    monkeypatch.setattr(
        "llm_cli.core.dashboard.load_installed_record",
        lambda: type("R", (), {"cli_version": "0.9.0"})(),
    )
    monkeypatch.setattr("llm_cli.commands.update_cmd.current_cli_version", lambda: "1.1.0")

    def fake_install(**kwargs):
        called["install"] = True
        return type(
            "R",
            (),
            {"cli_version": "1.1.0", "node_version": "20", "npm_version": "10"},
        )()

    monkeypatch.setattr("llm_cli.core.dashboard.run_install", fake_install)
    monkeypatch.setattr("llm_cli.commands.update_cmd.shutil.which", lambda cmd: f"/usr/bin/{cmd}")

    from llm_cli.commands.update_cmd import _post_update_hooks

    _post_update_hooks()
    assert called["install"] is True


def test_update_skips_dashboard_rebuild_if_node_missing(monkeypatch):
    monkeypatch.setattr(
        "llm_cli.core.dashboard.load_installed_record",
        lambda: type("R", (), {"cli_version": "0.9.0"})(),
    )
    monkeypatch.setattr("llm_cli.commands.update_cmd.current_cli_version", lambda: "1.1.0")
    monkeypatch.setattr("llm_cli.commands.update_cmd.shutil.which", lambda _cmd: None)

    from llm_cli.commands.update_cmd import _post_update_hooks

    _post_update_hooks()
