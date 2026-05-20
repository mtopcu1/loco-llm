import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_cli.core.settings import save_settings
from llm_cli.webapi.errors import ApiError, ErrorCode, install_exception_handlers
from llm_cli.webapi.app import create_app


@pytest.fixture
def error_app() -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/raise/{code_name}")
    def _raise(code_name: str):
        raise ApiError(
            code=ErrorCode[code_name],
            message=f"raised {code_name}",
            details={"code_name": code_name},
            status_code=400,
        )

    @app.get("/boom")
    def _boom():
        raise RuntimeError("synthetic")

    return app


@pytest.fixture
def client(error_app) -> TestClient:
    return TestClient(error_app, raise_server_exceptions=False)


@pytest.fixture
def webapi_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    for dirname in ("runtimes", "benchmarks"):
        (repo_root / dirname).mkdir(parents=True, exist_ok=True)
    (repo_root / "requirements.yaml").write_text("[]\n", encoding="utf-8")

    data_root = tmp_path / "data"
    for dirname in ("configs", "state", "models", "runtimes", "cache", "user"):
        (data_root / dirname).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOCO_HOME", str(data_root))
    monkeypatch.setenv("LOCO_INSTALL", str(repo_root))
    save_settings({"data_root": str(data_root), "repo_root": str(repo_root)})
    return {
        "repo_root": repo_root,
        "data_root": data_root,
        "configs_dir": data_root / "configs",
    }


@pytest.fixture
def seed_model(webapi_repo):
    del webapi_repo

    from llm_cli.core.model_registry import (
        Artifact,
        HFSource,
        Metadata,
        RegistryEntry,
        upsert_entry,
    )
    from llm_cli.core.settings import resolve_settings

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


@pytest.fixture
def test_client(webapi_repo, tmp_path, monkeypatch) -> TestClient:
    del webapi_repo
    monkeypatch.setattr("llm_cli.webapi.app._dist_dir", lambda: tmp_path / "empty-dist")
    app = create_app(allowed_hosts={"testserver"})
    return TestClient(app)
