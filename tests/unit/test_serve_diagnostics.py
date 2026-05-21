from __future__ import annotations

import pytest
import yaml

from llm_cli.core.serve_diagnostics import diagnose_serve_failure


def test_diagnose_unknown_config(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("LOCO_HOME", str(data_root))
    from llm_cli.core.settings import save_settings

    save_settings({"data_root": str(data_root), "repo_root": str(tmp_path / "repo")})
    msg = diagnose_serve_failure("missing-config-id", exit_code=1)
    assert "exit code 1" in msg or "exited with code 1" in msg
    assert "missing-config-id" in msg
    assert "llm serve missing-config-id" in msg


def test_diagnose_runtime_not_installed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    data_root = tmp_path / "data"
    (data_root / "configs").mkdir(parents=True)
    runtime_id = "diag-rt"
    config_id = "diag-cfg"

    runtime_dir = repo_root / "runtimes" / runtime_id
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "id": runtime_id,
                "display_name": runtime_id,
                "kind": "official",
                "accepts_formats": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (data_root / "configs" / f"{config_id}.yaml").write_text(
        yaml.safe_dump(
            {
                "id": config_id,
                "runtime": runtime_id,
                "serve": {"host": "127.0.0.1", "port": 18080, "params": {}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LOCO_HOME", str(data_root))
    monkeypatch.setenv("LOCO_INSTALL", str(repo_root))

    from llm_cli.core.settings import save_settings

    save_settings({"data_root": str(data_root), "repo_root": str(repo_root)})

    msg = diagnose_serve_failure(config_id, exit_code=1)
    assert "not installed" in msg
    assert runtime_id in msg
