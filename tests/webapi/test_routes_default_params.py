from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

_WORKSPACE = Path(__file__).resolve().parents[2]


@pytest.fixture
def seed_stub_runtime(webapi_repo):
    repo_root = webapi_repo["repo_root"]

    def _seed() -> None:
        runtime_dir = repo_root / "runtimes" / "stub-runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "manifest.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "stub-runtime",
                    "display_name": "Stub",
                    "kind": "official",
                    "accepts_formats": [],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (runtime_dir / "params.yaml").write_text(
            yaml.safe_dump(
                {
                    "host": {
                        "type": "string",
                        "required": True,
                        "description": "Bind host",
                    }
                }
            ),
            encoding="utf-8",
        )
        for script_name in ("build.sh", "serve.sh", "healthcheck.sh"):
            (runtime_dir / script_name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    return _seed


@pytest.fixture
def seed_llamacpp_runtime(webapi_repo):
    repo_root = webapi_repo["repo_root"]

    def _seed() -> None:
        src = _WORKSPACE / "runtimes" / "llamacpp"
        dst = repo_root / "runtimes" / "llamacpp"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    return _seed


@pytest.mark.webapi
def test_default_params_for_stub_runtime(test_client, seed_stub_runtime):
    seed_stub_runtime()
    r = test_client.get("/api/runtimes/stub-runtime/default-params", headers={"Host": "testserver"})
    assert r.status_code == 200
    cells = r.json()
    assert isinstance(cells, list)
    keys = {c["key"] for c in cells}
    assert "host" in keys


@pytest.mark.webapi
def test_default_params_with_model_populates_model_path(
    test_client, seed_llamacpp_runtime, seed_model
):
    seed_llamacpp_runtime()
    seed_model("qwen2-7b", model_format="gguf")
    r = test_client.get(
        "/api/runtimes/llamacpp/default-params?model_id=qwen2-7b",
        headers={"Host": "testserver"},
    )
    assert r.status_code == 200
    cells = r.json()
    gguf = next((c for c in cells if c["key"] == "gguf_path"), None)
    assert gguf is not None
    assert "qwen2-7b" in str(gguf["value"])
