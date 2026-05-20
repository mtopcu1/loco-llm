from llm_cli.core.doctor import _check_insecure_in_recent_log


def test_insecure_recent_log_warns(tmp_path, monkeypatch):
    log = tmp_path / "server.log"
    log.write_text(
        "[SECURITY] Started with --insecure=True on 0.0.0.0:7878; allowed_hosts=['192.168.1.50:7878']\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("llm_cli.core.dashboard.server_log_path", lambda: log)
    result = _check_insecure_in_recent_log()
    assert result.status == "warning"
    assert "--insecure" in result.message


def test_no_insecure_in_log_ok(tmp_path, monkeypatch):
    log = tmp_path / "server.log"
    log.write_text(
        "[SECURITY] Started with --insecure=False on 127.0.0.1:7878; allowed_hosts=[]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("llm_cli.core.dashboard.server_log_path", lambda: log)
    result = _check_insecure_in_recent_log()
    assert result.status == "ok"


def test_missing_log_ok(tmp_path, monkeypatch):
    log = tmp_path / "missing.log"
    monkeypatch.setattr("llm_cli.core.dashboard.server_log_path", lambda: log)
    result = _check_insecure_in_recent_log()
    assert result.status == "ok"
