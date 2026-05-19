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

    def test_skips_full_ci_for_release_please_branches(self):
        doc = _load("ci.yml")
        for name in ("test", "build-check"):
            job_if = doc["jobs"][name].get("if", "")
            assert "release-please--" in job_if, (
                f"expected {name} to skip release-please PRs and merges"
            )


class TestPublishWorkflow:
    def test_triggers_on_release_published(self):
        doc = _load("publish.yml")
        on = _get_on(doc)
        assert "release" in on
        types = on["release"].get("types", [])
        assert "published" in types

    def test_supports_manual_dispatch(self):
        doc = _load("publish.yml")
        on = _get_on(doc)
        assert "workflow_dispatch" in on

    def test_has_id_token_write_permission_for_oidc(self):
        doc = _load("publish.yml")
        # Either job-level or workflow-level permissions are acceptable;
        # we accept the first one that grants id-token: write.
        def _has(d: dict[str, Any]) -> bool:
            perms = d.get("permissions", {})
            return perms.get("id-token") == "write"

        if _has(doc):
            return
        for job in doc["jobs"].values():
            if _has(job):
                return
        pytest.fail(
            "expected id-token: write at workflow or job level for PyPI OIDC"
        )

    def test_uses_pypi_publish_action(self):
        doc = _load("publish.yml")
        all_steps = []
        for job in doc["jobs"].values():
            all_steps.extend(job.get("steps", []))
        uses = [s.get("uses", "") for s in all_steps]
        assert any(
            u.startswith("pypa/gh-action-pypi-publish@") for u in uses
        ), "expected pypa/gh-action-pypi-publish step"

    def test_builds_scaffold_tarball_and_sha256(self):
        doc = _load("publish.yml")
        all_steps = []
        for job in doc["jobs"].values():
            all_steps.extend(job.get("steps", []))
        run_blobs = "\n".join(s.get("run", "") for s in all_steps)
        assert "tar czf" in run_blobs, "expected a tar czf step"
        assert "scaffold-" in run_blobs, (
            "expected scaffold-<tag>.tar.gz naming pattern"
        )
        assert "sha256sum" in run_blobs, (
            "expected sha256sum to produce the .sha256 sidecar"
        )

    def test_attaches_assets_to_github_release(self):
        doc = _load("publish.yml")
        all_steps = []
        for job in doc["jobs"].values():
            all_steps.extend(job.get("steps", []))
        uses = [s.get("uses", "") for s in all_steps]
        run_blobs = "\n".join(s.get("run", "") for s in all_steps)
        attaches_via_action = any(
            u.startswith("softprops/action-gh-release@") for u in uses
        )
        attaches_via_gh_cli = "gh release upload" in run_blobs
        assert attaches_via_action or attaches_via_gh_cli, (
            "expected either softprops/action-gh-release or `gh release upload` "
            "to attach the scaffold tarball to the GitHub Release"
        )
