"""Tests for layered scaffold + user asset discovery."""
from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core import registry
from llm_cli.core.settings import save_settings


def _seed_runtime(root: Path, rid: str) -> None:
    d = root / "runtimes" / rid
    d.mkdir(parents=True)
    (d / "manifest.yaml").write_text(
        f"id: {rid}\ndisplay_name: {rid}\naccepts_formats: []\n",
        encoding="utf-8",
    )
    for name in ("build.sh", "serve.sh", "healthcheck.sh"):
        (d / name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")


def _seed_config(root: Path, cid: str) -> None:
    (root / "configs").mkdir(parents=True, exist_ok=True)
    (root / "configs" / f"{cid}.yaml").write_text(
        f"id: {cid}\nruntime: stub\nserve:\n  host: 127.0.0.1\n  port: 1\n",
        encoding="utf-8",
    )


def test_user_layer_wins_on_runtime_id_collision(tmp_path, monkeypatch) -> None:
    scaffold = tmp_path / "scaffold"
    user = tmp_path / "data" / "user"
    _seed_runtime(scaffold, "rt-a")
    _seed_runtime(user, "rt-a")
    data = tmp_path / "data"
    monkeypatch.setenv("LOCO_HOME", str(data))
    monkeypatch.setenv("LOCO_INSTALL", str(scaffold))
    save_settings({"data_root": data.resolve().as_posix()})

    merged = registry.discover_runtimes_merged()
    by_id = {r.id: r for r in merged}
    assert by_id["rt-a"].source == "user"
    assert by_id["rt-a"].path == user / "runtimes" / "rt-a"


def test_merged_includes_both_runtime_layers(tmp_path, monkeypatch) -> None:
    scaffold = tmp_path / "scaffold"
    user = tmp_path / "data" / "user"
    _seed_runtime(scaffold, "official-rt")
    _seed_runtime(user, "custom-rt")
    data = tmp_path / "data"
    monkeypatch.setenv("LOCO_HOME", str(data))
    monkeypatch.setenv("LOCO_INSTALL", str(scaffold))
    save_settings({"data_root": data.resolve().as_posix()})

    ids = {r.id for r in registry.discover_runtimes_merged()}
    assert ids == {"custom-rt", "official-rt"}


def test_configs_only_from_data_home(tmp_path, monkeypatch) -> None:
    install = tmp_path / "install"
    data = tmp_path / "data"
    monkeypatch.setenv("LOCO_HOME", str(data))
    monkeypatch.setenv("LOCO_INSTALL", str(install))
    _seed_config(install, "from-install")
    _seed_config(data, "from-data")
    save_settings({"data_root": data.resolve().as_posix()})

    merged = registry.discover_configs_merged()
    assert {c.id for c in merged} == {"from-data"}
