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

    def test_uses_release_please_action(self):
        doc = _load("release-please.yml")
        jobs = doc["jobs"]
        steps = next(iter(jobs.values()))["steps"]
        uses = [s.get("uses", "") for s in steps]
        assert any(u.startswith("googleapis/release-please-action@") for u in uses)

    def test_release_please_can_be_rerun_manually(self):
        doc = _load("release-please.yml")
        on = _get_on(doc)
        assert "workflow_dispatch" in on

    def test_release_please_grants_pr_write(self):
        doc = _load("release-please.yml")
        perms = doc.get("permissions", {})
        assert perms.get("pull-requests") == "write"
        assert perms.get("contents") == "write"
        assert perms.get("id-token") == "write"

    def test_release_please_validates_release_branch(self):
        doc = _load("release-please.yml")
        job = doc["jobs"].get("release-pr-check")
        assert job is not None, "expected a release-pr-check job"
        run_steps = [s.get("run", "") for s in job["steps"] if "run" in s]
        assert any("version sync ok" in cmd or "release-please-manifest" in cmd for cmd in run_steps)
        assert any("python -m build" in cmd for cmd in run_steps)

    def test_release_please_publishes_when_release_created(self):
        doc = _load("release-please.yml")
        job = doc["jobs"].get("publish")
        assert job is not None, "expected a publish job chained to release-please"
        assert "releases_created" in job.get("if", "")
        all_steps = job.get("steps", [])
        uses = [s.get("uses", "") for s in all_steps]
        assert any(u.startswith("pypa/gh-action-pypi-publish@") for u in uses)


class TestCIWorkflow:
    def test_triggers_on_pull_request_only(self):
        doc = _load("ci.yml")
        on = _get_on(doc)
        assert "pull_request" in on
        assert "push" not in on, "CI should not run on push to main"

    def test_skips_release_please_branches(self):
        doc = _load("ci.yml")
        job_if = doc["jobs"]["test"].get("if", "")
        assert "release-please--" in job_if

    def test_uses_uv_and_runs_pytest(self):
        doc = _load("ci.yml")
        steps = doc["jobs"]["test"]["steps"]
        uses = [s.get("uses", "") for s in steps]
        runs = [s.get("run", "") for s in steps]
        assert any(u.startswith("astral-sh/setup-uv@") for u in uses)
        assert any("pytest" in cmd for cmd in runs)
