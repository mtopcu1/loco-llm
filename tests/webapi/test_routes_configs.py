from __future__ import annotations

import pytest
import yaml


@pytest.fixture
def seed_runtime_and_config(webapi_repo):
    repo_root = webapi_repo["repo_root"]

    def _seed(config_id: str, *, valid: bool = True) -> None:
        runtime_id = "rt-config"
        runtime_dir = repo_root / "runtimes" / runtime_id
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "manifest.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": runtime_id,
                    "display_name": "Runtime Config",
                    "kind": "official",
                    "accepts_formats": [],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (runtime_dir / "params.yaml").write_text(
            yaml.safe_dump({"ctx": {"type": "int", "description": "Context length"}}),
            encoding="utf-8",
        )
        for script_name in ("build.sh", "serve.sh", "healthcheck.sh"):
            (runtime_dir / script_name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")

        config_doc = {
            "id": config_id,
            "runtime": runtime_id,
            "serve": {
                "host": "127.0.0.1",
                "port": 9001 if valid else None,
                "params": {"ctx": 1024},
                "env": {"CACHE_DIR": "${data_root}/cache"},
            },
        }
        if not valid:
            del config_doc["serve"]["port"]

        config_path = repo_root / "configs" / f"{config_id}.yaml"
        config_path.write_text(yaml.safe_dump(config_doc, sort_keys=False), encoding="utf-8")

    return _seed


@pytest.mark.webapi
def test_list_configs_includes_seeded(test_client, seed_runtime_and_config):
    seed_runtime_and_config("demo-config")
    r = test_client.get("/api/configs", headers={"Host": "testserver"})
    assert r.status_code == 200
    ids = [cfg["id"] for cfg in r.json()]
    assert "demo-config" in ids


@pytest.mark.webapi
def test_get_config_detail_expands_data_root(test_client, seed_runtime_and_config, webapi_repo):
    seed_runtime_and_config("expanded-config")
    r = test_client.get("/api/configs/expanded-config", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    expected_prefix = webapi_repo["data_root"].as_posix()
    assert body["resolved"]["serve"]["env"]["CACHE_DIR"].startswith(expected_prefix)


@pytest.mark.webapi
def test_get_config_params_returns_param_cells(test_client, seed_runtime_and_config):
    seed_runtime_and_config("params-config")
    r = test_client.get("/api/configs/params-config/params", headers={"Host": "testserver"})
    assert r.status_code == 200
    cells = r.json()
    assert any(cell["key"] == "ctx" for cell in cells)


@pytest.mark.webapi
def test_get_config_validate_reports_errors(test_client, seed_runtime_and_config):
    seed_runtime_and_config("invalid-config", valid=False)
    r = test_client.get("/api/configs/invalid-config/validate", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert any("serve.port" in err for err in body["errors"])
