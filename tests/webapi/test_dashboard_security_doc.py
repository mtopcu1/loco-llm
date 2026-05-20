import pytest


@pytest.mark.webapi
def test_dashboard_security_doc_served(test_client, webapi_repo):
    doc = webapi_repo["repo_root"] / "docs" / "DASHBOARD-SECURITY.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# Security\n", encoding="utf-8")
    r = test_client.get("/docs/dashboard-security", headers={"Host": "testserver"})
    assert r.status_code == 200
    assert "Security" in r.text
