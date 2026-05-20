from __future__ import annotations

import pytest

from llm_cli.core.model_registry import (
    Artifact,
    HFSource,
    Metadata,
    RegistryEntry,
    upsert_entry,
)
from llm_cli.core.settings import resolve_settings


@pytest.fixture
def seed_model(webapi_repo):
    del webapi_repo

    def _seed(model_id: str, *, model_format: str = "gguf") -> None:
        settings = resolve_settings()
        upsert_entry(
            settings.models_dir,
            RegistryEntry(
                id=model_id,
                format=model_format,
                source=HFSource(repo="owner/repo"),
                artifact=Artifact(
                    primary="weights.gguf",
                    files=("weights.gguf",),
                    total_size_bytes=123,
                ),
                metadata=Metadata(display_name=model_id),
                installed_at="2026-05-20T00:00:00Z",
            ),
        )

    return _seed


@pytest.mark.webapi
def test_list_models_includes_seeded(test_client, seed_model):
    seed_model("phi-mini")
    r = test_client.get("/api/models", headers={"Host": "testserver"})
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()]
    assert "phi-mini" in ids


@pytest.mark.webapi
def test_get_model_detail_404_when_missing(test_client):
    r = test_client.get("/api/models/does-not-exist", headers={"Host": "testserver"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "MODEL_NOT_FOUND"
