"""Validate the release-please configuration files.

These are not Python files but JSON / structured data we own; if they
break, releases break. Catch typos in CI rather than on the next release.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> dict:
    path = REPO_ROOT / name
    assert path.is_file(), f"missing {name} at repo root"
    return json.loads(path.read_text(encoding="utf-8"))


def test_release_please_config_is_python_release_type():
    cfg = _load("release-please-config.json")
    assert cfg["release-type"] == "python"


def test_release_please_config_declares_root_package():
    cfg = _load("release-please-config.json")
    assert "." in cfg["packages"], "expected the root package keyed by '.'"
    root = cfg["packages"]["."]
    assert root["package-name"] == "loco-llm-cli"


def test_release_please_config_updates_init_py():
    cfg = _load("release-please-config.json")
    extras = cfg["packages"]["."].get("extra-files", [])
    paths = {entry["path"] for entry in extras if isinstance(entry, dict)}
    assert "src/llm_cli/__init__.py" in paths, (
        "release-please must be configured to update __version__ in "
        "src/llm_cli/__init__.py"
    )


def test_release_please_changelog_sections_cover_feat_and_fix():
    cfg = _load("release-please-config.json")
    sections = cfg.get("changelog-sections", [])
    types = {s["type"] for s in sections}
    assert "feat" in types
    assert "fix" in types


def test_release_please_manifest_starts_at_known_version():
    manifest = _load(".release-please-manifest.json")
    assert manifest["."] in {"0.2.0", "0.2.1"}, (
        "the manifest's recorded version for '.' should match the last "
        "released version; if you're bumping pre-release, update this test"
    )
