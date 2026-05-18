"""Tests for WSL path helpers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from llm_cli.core import wsl
from llm_cli.core.settings import Settings


def test_to_wsl_path_non_windows_uses_posix(tmp_path: Path) -> None:
    target = tmp_path / "repo" / "x"
    target.mkdir(parents=True)
    with patch.object(wsl, "is_windows", return_value=False):
        assert wsl.to_wsl_path(target) == target.resolve().as_posix()


def test_to_wsl_path_windows_drive() -> None:
    with patch.object(wsl, "is_windows", return_value=True):
        p = Path("C:/Users/me/LocalLLM")
        assert wsl.to_wsl_path(p) == "/mnt/c/Users/me/LocalLLM"


def _fake_settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path / "d",
        repo_root=tmp_path / "r",
        runtimes_dir=tmp_path / "d" / "runtimes",
        models_dir=tmp_path / "d" / "models",
        cache_dir=tmp_path / "d" / "cache",
    )


def test_run_repo_bash_injects_env_from_settings(tmp_path: Path) -> None:
    settings = _fake_settings(tmp_path)
    scaffold = tmp_path / "scaffold"
    scaffold.mkdir()
    captured: dict[str, str] = {}

    def fake_call(cmd, env=None):
        captured.update(env or {})
        return 0

    with patch.object(wsl, "scaffold_root", return_value=scaffold):
        with patch.object(wsl.subprocess, "call", side_effect=fake_call):
            rc = wsl.run_repo_bash(settings, "runtimes/x/build.sh")

    assert rc == 0
    assert captured["LLM_DATA_ROOT"] == (tmp_path / "d").as_posix()
    assert captured["LLM_REPO_ROOT"] == scaffold.resolve().as_posix()
    assert captured["LLM_RUNTIMES"] == (tmp_path / "d" / "runtimes").as_posix()
    assert captured["LLM_MODELS"] == (tmp_path / "d" / "models").as_posix()
    assert captured["LLM_CACHE"] == (tmp_path / "d" / "cache").as_posix()


def test_run_repo_bash_no_longer_sources_llm_env(tmp_path: Path) -> None:
    settings = _fake_settings(tmp_path)
    captured_cmd: list[str] = []

    def fake_call(cmd, env=None):
        captured_cmd.extend(cmd)
        return 0

    with patch.object(wsl.subprocess, "call", side_effect=fake_call):
        wsl.run_repo_bash(settings, "runtimes/x/build.sh")

    joined = " ".join(captured_cmd)
    assert ".llm-env" not in joined
