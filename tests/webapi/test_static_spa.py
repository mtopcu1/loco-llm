from __future__ import annotations

import pytest
from fastapi import FastAPI

from llm_cli.webapi.static import mount_spa


@pytest.mark.webapi
def test_spa_fallback_serves_index_for_client_route(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    app = FastAPI()
    mount_spa(app, dist)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    r = client.get("/models")
    assert r.status_code == 200
    assert "spa" in r.text
