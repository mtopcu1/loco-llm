"""Tests for systemd_unit: template, write-if-different, and systemctl wrappers."""
from __future__ import annotations

from llm_cli.core.systemd_unit import desired_unit_text


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
