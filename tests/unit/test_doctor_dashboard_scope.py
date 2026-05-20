from llm_cli.core import doctor as docmod


def test_dashboard_scope_reports_node_missing(monkeypatch):
    monkeypatch.setattr(
        "shutil.which", lambda cmd: None if cmd in ("node", "npm") else "/usr/bin/x"
    )
    monkeypatch.setattr("llm_cli.core.dashboard.load_installed_record", lambda: None)
    results = docmod.run_scope("dashboard")
    by_name = {r.name: r for r in results}
    assert by_name["node"].status in {"error", "warning", "info"}
    assert by_name["npm"].status in {"error", "warning", "info"}


def test_dashboard_scope_reports_not_installed(monkeypatch):
    monkeypatch.setattr("llm_cli.core.dashboard.load_installed_record", lambda: None)
    results = docmod.run_scope("dashboard")
    by_name = {r.name: r for r in results}
    assert by_name["dashboard installed"].status == "info"
