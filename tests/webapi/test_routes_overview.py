from __future__ import annotations

import pytest
import yaml

from llm_cli.core import lifecycle
from llm_cli.core.model_registry import Artifact, HFSource, Metadata, RegistryEntry, upsert_entry
from llm_cli.core.settings import resolve_settings


@pytest.mark.webapi
def test_get_overview_returns_aggregate_payload(test_client, webapi_repo):
    settings = resolve_settings()
    repo_root = webapi_repo["repo_root"]

    runtime_dir = repo_root / "runtimes" / "rt-overview"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {"id": "rt-overview", "display_name": "rt-overview", "kind": "official", "accepts_formats": []},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    for script_name in ("build.sh", "serve.sh", "healthcheck.sh"):
        (runtime_dir / script_name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    (webapi_repo["configs_dir"] / "cfg-overview.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "cfg-overview",
                "runtime": "rt-overview",
                "serve": {"host": "127.0.0.1", "port": 8000, "params": {}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    upsert_entry(
        settings.models_dir,
        RegistryEntry(
            id="md-overview",
            format="gguf",
            source=HFSource(repo="owner/repo"),
            artifact=Artifact(primary="model.gguf", files=("model.gguf",), total_size_bytes=10),
            metadata=Metadata(display_name="md-overview"),
            installed_at="2026-05-20T00:00:00Z",
        ),
    )

    lifecycle.append_history(
        lifecycle.state_root(settings),
        {"action": "config-create", "id": "cfg-overview", "ts": "2026-05-20T00:00:00Z"},
    )

    r = test_client.get("/api/overview", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    for key in (
        "version",
        "instance",
        "runtimes_count",
        "runtimes_installed_count",
        "models_count",
        "configs_count",
        "doctor_summary",
        "recent_history",
        "disk_summary",
    ):
        assert key in body
