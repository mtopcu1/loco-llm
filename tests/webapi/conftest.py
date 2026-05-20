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
def webapi_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    for dirname in ("runtimes", "configs", "benchmarks", "state"):
        (repo_root / dirname).mkdir(parents=True, exist_ok=True)

    data_root = tmp_path / "data"
    save_settings({"data_root": str(data_root), "repo_root": str(repo_root)})
    return {"repo_root": repo_root, "data_root": data_root}


@pytest.fixture
def test_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr("llm_cli.webapi.app._dist_dir", lambda: tmp_path / "empty-dist")
    app = create_app(allowed_hosts={"testserver"})
    return TestClient(app)
