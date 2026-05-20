"""Tests for editable pip install detection."""
from __future__ import annotations

import json
import sysconfig
from pathlib import Path

from llm_cli.core import editable_install as ei


def test_editable_project_path_reads_direct_url(tmp_path: Path, monkeypatch) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    site = tmp_path / "site-packages"
    site.mkdir()
    meta = site / "loco_llm_cli-1.3.0.dist-info"
    meta.mkdir()
    (meta / "direct_url.json").write_text(
        json.dumps(
            {
                "dir_info": {"editable": True},
                "url": checkout.as_uri(),
            }
        ),
        encoding="utf-8",
    )
    empty = tmp_path / "empty-platlib"
    empty.mkdir()

    def _path(kind: str) -> str:
        if kind == "purelib":
            return str(site)
        return str(empty)

    monkeypatch.setattr(sysconfig, "get_path", _path)
    assert ei.editable_project_path() == checkout.resolve()


def test_check_editable_install_errors_when_target_missing(tmp_path: Path, monkeypatch) -> None:
    missing = tmp_path / "gone"
    site = tmp_path / "site-packages"
    site.mkdir()
    meta = site / "loco_llm_cli-1.3.0.dist-info"
    meta.mkdir()
    (meta / "direct_url.json").write_text(
        json.dumps(
            {
                "dir_info": {"editable": True},
                "url": missing.as_uri(),
            }
        ),
        encoding="utf-8",
    )
    empty = tmp_path / "empty-platlib"
    empty.mkdir()

    def _path(kind: str) -> str:
        if kind == "purelib":
            return str(site)
        return str(empty)

    monkeypatch.setattr(sysconfig, "get_path", _path)
    cid, status, msg = ei.check_editable_install()
    assert cid == "cli-editable"
    assert status == "error"
    assert "missing" in msg.lower()
