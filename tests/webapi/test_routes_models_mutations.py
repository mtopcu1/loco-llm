from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core.model_registry import (
    Artifact,
    HFSource,
    Metadata,
    RegistryEntry,
    get_entry,
    upsert_entry,
)
from llm_cli.core.settings import resolve_settings


@pytest.fixture
def seed_model(webapi_repo):
    del webapi_repo

    def _seed(model_id: str) -> None:
        settings = resolve_settings()
        upsert_entry(
            settings.models_dir,
            RegistryEntry(
                id=model_id,
                format="gguf",
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
def test_pull_model_returns_job_id(test_client, monkeypatch):
    fake_id = "pull-job-1"

    monkeypatch.setattr(
        "llm_cli.webapi.routes.models.jobs_module.registry",
        lambda: type(
            "R",
            (),
            {"start_subprocess": lambda self, **kw: fake_id},
        )(),
    )
    r = test_client.post(
        "/api/models/pull",
        headers={"Host": "testserver"},
        json={"url": "https://huggingface.co/org/model"},
    )
    assert r.status_code == 200
    assert r.json() == {"job_id": fake_id}


@pytest.mark.webapi
def test_add_local_model(test_client, tmp_path):
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"fake")

    r = test_client.post(
        "/api/models/add",
        headers={"Host": "testserver"},
        json={"id": "local-gguf", "path": str(gguf), "format": "gguf"},
    )
    assert r.status_code == 200
    assert r.json()["id"] == "local-gguf"
    assert r.json()["format"] == "gguf"


@pytest.mark.webapi
def test_add_local_model_conflict(test_client, tmp_path, seed_model):
    seed_model("taken-id")
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"fake")

    r = test_client.post(
        "/api/models/add",
        headers={"Host": "testserver"},
        json={"id": "taken-id", "path": str(gguf), "format": "gguf"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "MODEL_ALREADY_REGISTERED"


@pytest.mark.webapi
def test_uninstall_model(test_client, seed_model):
    seed_model("drop-me")
    r = test_client.delete("/api/models/drop-me", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    settings = resolve_settings()
    assert get_entry(settings.models_dir, "drop-me") is None


@pytest.mark.webapi
def test_uninstall_model_404(test_client):
    r = test_client.delete("/api/models/nope", headers={"Host": "testserver"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "MODEL_NOT_FOUND"
