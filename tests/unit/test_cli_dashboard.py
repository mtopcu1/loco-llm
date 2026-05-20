from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def test_llm_dashboard_help_lists_subcommands():
    result = runner.invoke(app, ["dashboard", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    for sub in ("install", "serve", "status", "stop", "uninstall"):
        assert sub in out


def test_llm_dashboard_status_when_not_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(app, ["dashboard", "status"])
    assert "dashboard" in result.stdout.lower() or "dashboard" in (result.stderr or "").lower()


def test_install_writes_installed_record_when_skips_used(tmp_path, monkeypatch):
    """With --skip-python --skip-frontend, install just writes the marker."""
    repo = tmp_path / "repo"
    dist = repo / "dashboard" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")

    monkeypatch.setattr(
        "llm_cli.core.settings.resolve_settings",
        lambda: type(
            "S",
            (),
            {
                "data_root": tmp_path,
                "repo_root": repo,
                "runtimes_dir": tmp_path,
                "models_dir": tmp_path,
                "cache_dir": tmp_path,
            },
        )(),
    )
    monkeypatch.setattr("llm_cli.core.dashboard.dashboard_root", lambda: repo / "dashboard")
    monkeypatch.setattr("llm_cli.core.dashboard._probe_node_version", lambda: "20.11.1")
    monkeypatch.setattr("llm_cli.core.dashboard._probe_npm_version", lambda: "10.2.4")
    monkeypatch.setattr("llm_cli.commands.dashboard_cmd.current_cli_version", lambda: "1.1.0")

    result = runner.invoke(
        app, ["dashboard", "install", "--skip-python", "--skip-frontend"]
    )
    assert result.exit_code == 0, result.stdout

    record = (repo / "dashboard" / ".installed").read_text(encoding="utf-8")
    assert "node_version: 20.11.1" in record
    assert "npm_version: 10.2.4" in record
