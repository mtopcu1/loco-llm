import os
from pathlib import Path

from llm_cli.core import dashboard as dash


def _write_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "main.css").write_text("body{}", encoding="utf-8")
    (assets / "main.js").write_text("console.log(0)", encoding="utf-8")
    return dist


def test_compute_dist_hash_stable(tmp_path):
    d = _write_dist(tmp_path)
    h1 = dash.compute_dist_hash(d)
    h2 = dash.compute_dist_hash(d)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_compute_dist_hash_changes_on_edit(tmp_path):
    d = _write_dist(tmp_path)
    h1 = dash.compute_dist_hash(d)
    (d / "assets" / "main.js").write_text("console.log(1)", encoding="utf-8")
    h2 = dash.compute_dist_hash(d)
    assert h1 != h2


def test_installed_record_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "dashboard_root", lambda: tmp_path)
    rec = dash.InstalledRecord(
        installed_at="2026-05-20T07:30:00Z",
        cli_version="1.1.0",
        node_version="20.11.1",
        npm_version="10.2.4",
        dist_hash="sha256:abc",
    )
    dash.write_installed_record(rec)
    loaded = dash.load_installed_record()
    assert loaded == rec


def test_verify_installed_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "dashboard_root", lambda: tmp_path)
    verdict, reason = dash.verify_installed("1.1.0")
    assert verdict == "missing"


def test_verify_installed_version_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "dashboard_root", lambda: tmp_path)
    d = _write_dist(tmp_path)
    rec = dash.InstalledRecord(
        installed_at="2026-05-20T07:30:00Z",
        cli_version="1.0.0",
        node_version="20.11.1",
        npm_version="10.2.4",
        dist_hash=dash.compute_dist_hash(d),
    )
    dash.write_installed_record(rec)
    verdict, _ = dash.verify_installed("1.1.0")
    assert verdict == "version_mismatch"


def test_verify_installed_hash_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "dashboard_root", lambda: tmp_path)
    d = _write_dist(tmp_path)
    rec = dash.InstalledRecord(
        installed_at="2026-05-20T07:30:00Z",
        cli_version="1.1.0",
        node_version="20.11.1",
        npm_version="10.2.4",
        dist_hash="sha256:WRONG",
    )
    dash.write_installed_record(rec)
    verdict, _ = dash.verify_installed("1.1.0")
    assert verdict == "hash_mismatch"


def test_verify_installed_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(dash, "dashboard_root", lambda: tmp_path)
    d = _write_dist(tmp_path)
    rec = dash.InstalledRecord(
        installed_at="2026-05-20T07:30:00Z",
        cli_version="1.1.0",
        node_version="20.11.1",
        npm_version="10.2.4",
        dist_hash=dash.compute_dist_hash(d),
    )
    dash.write_installed_record(rec)
    verdict, _ = dash.verify_installed("1.1.0")
    assert verdict == "ok"


def test_is_server_alive_self_pid():
    assert dash.is_server_alive(os.getpid()) is True


def test_is_server_alive_nonexistent():
    assert dash.is_server_alive(999999) is False
