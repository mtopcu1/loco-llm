"""Tests for `llm serve` env construction."""
from __future__ import annotations

from pathlib import Path

from llm_cli.commands.serve import _serve_env_from_params
from llm_cli.core.params import parse_schema
from llm_cli.core.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path / "data",
        repo_root=tmp_path / "repo",
        runtimes_dir=tmp_path / "data" / "runtimes",
        models_dir=tmp_path / "data" / "models",
        cache_dir=tmp_path / "data" / "cache",
    )


def test_serve_env_from_params_basic(tmp_path: Path) -> None:
    s = _settings(tmp_path)
    schema = parse_schema(
        {
            "gguf_path": {"type": "path", "required": True, "env": "LLM_LLAMACPP_GGUF"},
            "ctx": {"type": "int", "env": "LLM_LLAMACPP_CTX"},
        }
    )
    cfg_data = {
        "id": "c1",
        "runtime": "llamacpp",
        "serve": {
            "host": "127.0.0.1",
            "port": 8080,
            "params": {
                "gguf_path": "${models_dir}/x.gguf",
                "ctx": 4096,
            },
        },
    }
    env = _serve_env_from_params(s, cfg_data, schema)
    assert env["LLM_SERVE_HOST"] == "127.0.0.1"
    assert env["LLM_SERVE_PORT"] == "8080"
    assert env["LLM_CONFIG_ID"] == "c1"
    assert env["LLM_LLAMACPP_CTX"] == "4096"
    assert env["LLM_LLAMACPP_GGUF"].endswith("/x.gguf")
    assert "${" not in env["LLM_LLAMACPP_GGUF"]
