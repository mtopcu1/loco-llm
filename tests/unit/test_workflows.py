"""Validate the GitHub Actions workflows for structural correctness.

This does NOT execute the workflows — it just parses the YAML and
asserts the required triggers, permissions, and steps are present.
Catches misconfigurations (e.g. missing OIDC permission) in unit-test
time rather than on the next release.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _load(name: str) -> dict[str, Any]:
    path = WORKFLOWS_DIR / name
    assert path.is_file(), f"missing workflow {name}"
    # PyYAML treats the unquoted `on:` key as boolean True; load and accept
    # either key form.
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return doc


def _get_on(doc: dict[str, Any]) -> dict[str, Any]:
    # GitHub YAML uses `on:` which PyYAML may parse as the Python bool True.
    if True in doc:
        return doc[True]
    return doc["on"]


class TestReleasePleaseWorkflow:
    def test_triggers_on_push_to_main(self):
        doc = _load("release-please.yml")
        on = _get_on(doc)
        assert "push" in on
        assert "main" in on["push"]["branches"]

    def test_supports_manual_dispatch(self):
        doc = _load("release-please.yml")
        on = _get_on(doc)
        assert "workflow_dispatch" in on

    def test_uses_release_please_action(self):
        doc = _load("release-please.yml")
        steps = doc["jobs"]["release-please"]["steps"]
        uses = [s.get("uses", "") for s in steps]
        assert any(u.startswith("googleapis/release-please-action@") for u in uses)

    def test_grants_only_minimum_permissions(self):
        doc = _load("release-please.yml")
        perms = doc.get("permissions", {})
        assert perms.get("contents") == "write"
        assert perms.get("pull-requests") == "write"
        assert "id-token" not in perms, "no OIDC needed without PyPI publish"

    def test_has_no_publish_or_check_jobs(self):
        doc = _load("release-please.yml")
        assert set(doc["jobs"].keys()) == {"release-please"}, (
            "release-please.yml should have exactly one job"
        )


class TestCIWorkflow:
    def test_triggers_on_pull_request_only(self):
        doc = _load("ci.yml")
        on = _get_on(doc)
        assert "pull_request" in on
        assert "push" not in on, "CI should not run on push to main"

    def test_skips_release_please_branches(self):
        doc = _load("ci.yml")
        for job_name in ("pytest-core", "pytest-webapi", "pytest"):
            job_if = doc["jobs"][job_name].get("if", "")
            assert "release-please--" in job_if

    def test_sharded_pytest_jobs_use_uv(self):
        doc = _load("ci.yml")
        for job_name in ("pytest-core", "pytest-webapi"):
            steps = doc["jobs"][job_name]["steps"]
            uses = [s.get("uses", "") for s in steps]
            runs = [s.get("run", "") for s in steps]
            assert any(u.startswith("astral-sh/setup-uv@") for u in uses)
            assert any("pytest" in cmd for cmd in runs)

    def test_pytest_gate_job_waits_for_shards(self):
        doc = _load("ci.yml")
        assert doc["jobs"]["pytest"]["needs"] == ["pytest-core", "pytest-webapi"]


class TestDashboardTestsWorkflow:
    def test_job_is_dashboard(self):
        doc = _load("dashboard-tests.yml")
        assert "dashboard" in doc["jobs"]
