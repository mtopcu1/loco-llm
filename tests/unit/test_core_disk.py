from pathlib import Path

import pytest

from llm_cli.core import disk


def _seed_data_root(tmp_path: Path) -> Path:
    root = tmp_path / "data_root"
    (root / "models" / "m1").mkdir(parents=True)
    (root / "models" / "m1" / "weights.bin").write_bytes(b"x" * 1000)
    (root / "models" / "m2").mkdir(parents=True)
    (root / "models" / "m2" / "weights.bin").write_bytes(b"y" * 500)
    (root / "cache" / "hf").mkdir(parents=True)
    (root / "cache" / "hf" / "blob").write_bytes(b"z" * 250)
    return root


def test_scan_reports_models(tmp_path, monkeypatch):
    root = _seed_data_root(tmp_path)
    monkeypatch.setattr(disk, "_models_dir", lambda: root / "models")
    monkeypatch.setattr(disk, "_cache_dir", lambda: root / "cache")
    monkeypatch.setattr(disk, "_data_root", lambda: root)
    report = disk.scan()
    by_id = {m.id: m for m in report.models}
    assert by_id["m1"].bytes == 1000
    assert by_id["m2"].bytes == 500
    assert report.cache_bytes == 250
    assert report.data_root_bytes_used >= 1750


def test_scan_handles_empty_models(tmp_path, monkeypatch):
    root = tmp_path / "data_root"
    (root / "models").mkdir(parents=True)
    (root / "cache").mkdir(parents=True)
    monkeypatch.setattr(disk, "_models_dir", lambda: root / "models")
    monkeypatch.setattr(disk, "_cache_dir", lambda: root / "cache")
    monkeypatch.setattr(disk, "_data_root", lambda: root)
    report = disk.scan()
    assert report.models == []
    assert report.cache_bytes == 0
