from __future__ import annotations

from datetime import datetime, timezone

import pytest
import yaml

from llm_cli.core.install_record import InstallRecord, write_record
from llm_cli.core.settings import resolve_settings


@pytest.fixture
def seed_runtime(webapi_repo):
    repo_root = webapi_repo["repo_root"]

    def _seed(runtime_id: str, *, kind: str = "official", installed: bool = False) -> None:
        runtime_dir = repo_root / "runtimes" / runtime_id
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "manifest.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": runtime_id,
                    "display_name": runtime_id,
                    "kind": kind,
                    "accepts_formats": [],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        for script_name in ("build.sh", "serve.sh", "healthcheck.sh"):
            (runtime_dir / script_name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")

        if installed:
            installed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            settings = resolve_settings()
            write_record(
                settings.runtimes_dir,
                InstallRecord(runtime_id=runtime_id, installed_at=installed_at, kind=kind),
            )

    return _seed


@pytest.mark.webapi
def test_list_runtimes_includes_seeded(test_client, seed_runtime):
    seed_runtime("dummy", kind="custom")
    r = test_client.get("/api/runtimes", headers={"Host": "testserver"})
    assert r.status_code == 200
    ids = [rt["id"] for rt in r.json()]
    assert "dummy" in ids


@pytest.mark.webapi
def test_get_runtime_detail_404_when_missing(test_client):
    r = test_client.get("/api/runtimes/does-not-exist", headers={"Host": "testserver"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "RUNTIME_NOT_FOUND"


@pytest.mark.webapi
def test_list_runtimes_has_metrics_from_manifest(test_client, webapi_repo, seed_runtime):
    del webapi_repo
    seed_runtime("with-metrics", kind="official")
    seed_runtime("without-metrics", kind="official")

    from llm_cli.core.settings import resolve_settings

    settings = resolve_settings()
    repo = settings.repo_root
    assert repo is not None
    (repo / "runtimes" / "with-metrics" / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "with-metrics",
                "display_name": "with-metrics",
                "kind": "official",
                "accepts_formats": [],
                "metrics": {"endpoint": "/metrics", "fields": {}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (repo / "runtimes" / "without-metrics" / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "without-metrics",
                "display_name": "without-metrics",
                "kind": "official",
                "accepts_formats": [],
                "metrics": None,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    r = test_client.get("/api/runtimes", headers={"Host": "testserver"})
    assert r.status_code == 200
    by_id = {rt["id"]: rt["has_metrics"] for rt in r.json()}
    assert by_id["with-metrics"] is True
    assert by_id["without-metrics"] is False
