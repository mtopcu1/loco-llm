"""Tests for systemd_unit: template, write-if-different, and systemctl wrappers."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.systemd_unit import desired_unit_text, unit_path, write_if_different


def test_desired_unit_text_contains_config_and_exec() -> None:
    txt = desired_unit_text("vllm-cuda__qwen2-7b-instruct__default")
    assert "AUTO-GENERATED" in txt
    assert (
        "Description=LocalLLM service (config: vllm-cuda__qwen2-7b-instruct__default)"
        in txt
    )
    assert "ExecStart=" in txt
    assert "vllm-cuda__qwen2-7b-instruct__default --foreground-from-supervisor" in txt
    assert "Restart=on-failure" in txt
    assert "WantedBy=default.target" in txt


def test_desired_unit_text_is_deterministic() -> None:
    assert desired_unit_text("a") == desired_unit_text("a")
    assert desired_unit_text("a") != desired_unit_text("b")


def test_unit_path_uses_xdg_config_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert unit_path() == tmp_path / "systemd" / "user" / "llm.service"


def test_unit_path_falls_back_to_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert unit_path() == tmp_path / ".config" / "systemd" / "user" / "llm.service"


def test_write_if_different_creates_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    changed = write_if_different("hello\n")
    assert changed is True
    assert unit_path().read_text(encoding="utf-8") == "hello\n"


def test_write_if_different_no_op_on_same_bytes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_if_different("v1\n")
    changed = write_if_different("v1\n")
    assert changed is False


def test_write_if_different_replaces_on_change(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_if_different("v1\n")
    changed = write_if_different("v2\n")
    assert changed is True
    assert unit_path().read_text(encoding="utf-8") == "v2\n"
