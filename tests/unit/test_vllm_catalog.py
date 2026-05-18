from __future__ import annotations

from pathlib import Path

import yaml


def test_vllm_params_envs_are_wired_in_serve_scripts() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    params_path = repo_root / "runtimes" / "vllm" / "params.yaml"
    serve_path = repo_root / "runtimes" / "vllm" / "serve.sh"
    helper_path = repo_root / "runtimes" / "vllm" / "_serve_flags.sh"

    schema = yaml.safe_load(params_path.read_text(encoding="utf-8")) or {}
    scripts_text = (
        serve_path.read_text(encoding="utf-8")
        + "\n"
        + helper_path.read_text(encoding="utf-8")
    )

    for key, spec in schema.items():
        if key == "extra_args":
            continue
        env_name = spec.get("env") or f"LLM_VLLM_{key.upper()}"
        assert env_name in scripts_text, (
            f"param {key!r} with env {env_name!r} is not referenced "
            "in serve.sh/_serve_flags.sh"
        )
