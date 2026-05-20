from __future__ import annotations

import pytest


@pytest.mark.webapi
def test_get_disk_reports_models_and_cache(test_client, webapi_repo):
    data_root = webapi_repo["data_root"]
    (data_root / "models" / "m1").mkdir(parents=True, exist_ok=True)
    (data_root / "models" / "m1" / "weights.bin").write_bytes(b"x" * 100)
    (data_root / "cache" / "hf").mkdir(parents=True, exist_ok=True)
    (data_root / "cache" / "hf" / "blob").write_bytes(b"y" * 25)

    r = test_client.get("/api/disk", headers={"Host": "testserver"})
    assert r.status_code == 200
    body = r.json()
    assert "models" in body
    assert any(model["id"] == "m1" for model in body["models"])
    assert body["cache_bytes"] >= 25
