from __future__ import annotations

import shutil
from pathlib import Path

import pytest

_WORKSPACE = Path(__file__).resolve().parents[2]


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
def test_recommendations_for_runtime_model(test_client, seed_llamacpp_runtime, seed_model):
    seed_llamacpp_runtime()
    seed_model("qwen2-7b", model_format="gguf")
    r = test_client.get(
        "/api/recommendations?runtime_id=llamacpp&model_id=qwen2-7b",
        headers={"Host": "testserver"},
    )
    assert r.status_code == 200
    recs = r.json()
    assert isinstance(recs, list)
    for rec in recs:
        assert {"param_key", "suggested_value", "reason"} <= set(rec)
