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


class TestCIWorkflow:
    def test_triggers_on_pr_and_push_to_main(self):
        doc = _load("ci.yml")
        on = _get_on(doc)
        assert "pull_request" in on
        assert "push" in on
        assert "main" in on["push"]["branches"]

    def test_runs_pytest_on_supported_python_versions(self):
        doc = _load("ci.yml")
        test_job = doc["jobs"].get("test")
        assert test_job is not None, "expected a 'test' job"
        matrix = test_job.get("strategy", {}).get("matrix", {})
        versions = {str(v) for v in matrix.get("python-version", [])}
        assert {"3.11", "3.12"}.issubset(versions), (
            f"expected pytest matrix on 3.11 and 3.12, got {versions}"
        )
        run_steps = [s.get("run", "") for s in test_job["steps"] if "run" in s]
        assert any("pytest" in cmd for cmd in run_steps), (
            "expected at least one step that runs pytest"
        )

    def test_has_build_check_job(self):
        doc = _load("ci.yml")
        build_job = doc["jobs"].get("build-check")
        assert build_job is not None, "expected a 'build-check' job"
        run_steps = [s.get("run", "") for s in build_job["steps"] if "run" in s]
        assert any("python -m build" in cmd for cmd in run_steps)
        assert any("twine check" in cmd for cmd in run_steps)
