from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def test_serve_insecure_alone_refuses(monkeypatch):
    result = runner.invoke(app, ["dashboard", "serve", "--insecure"])
    assert result.exit_code == 78
    assert "REFUSING TO START" in (result.stdout + (result.stderr or ""))
    assert "--i-understand" in (result.stdout + (result.stderr or ""))


def test_serve_insecure_without_allowed_host_refuses(monkeypatch):
    result = runner.invoke(app, ["dashboard", "serve", "--insecure", "--i-understand"])
    assert result.exit_code == 78
    assert "--allowed-host" in (result.stdout + (result.stderr or ""))


def test_serve_insecure_full_args_proceeds(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "llm_cli.core.dashboard.verify_installed",
        lambda v: ("ok", ""),
    )
    captured = {}

    def fake_start(host, port, allowed_hosts=None, insecure=False):
        captured["host"] = host
        captured["port"] = port
        captured["allowed_hosts"] = allowed_hosts
        captured["insecure"] = insecure
        return 1234

    monkeypatch.setattr("llm_cli.core.dashboard.start_server_background", fake_start)
    monkeypatch.setattr("llm_cli.core.dashboard.open_browser", lambda *a, **k: None)

    result = runner.invoke(
        app,
        [
            "dashboard",
            "serve",
            "--insecure",
            "--i-understand",
            "--host",
            "0.0.0.0",
            "--allowed-host",
            "192.168.1.50:7878",
            "--no-open",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert "192.168.1.50:7878" in captured["allowed_hosts"]
    assert captured["insecure"] is True
