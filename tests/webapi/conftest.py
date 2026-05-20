import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_cli.webapi.errors import ApiError, ErrorCode, install_exception_handlers


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
