"""Tests for scaffold tarball download and atomic directory swap."""
from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import pytest

from llm_cli.core.scaffold_update import (
    find_scaffold_assets,
    install_scaffold_release,
    remove_scaffold_backup,
    rollback_scaffold,
    verify_sha256_file,
)


def _make_scaffold_tarball(path: Path, inner_name: str = "scaffold-root") -> None:
    staging = path.parent / "staging"
    root = staging / inner_name
    root.mkdir(parents=True)
    (root / "requirements.yaml").write_text("- id: python\n", encoding="utf-8")
    with tarfile.open(path, "w:gz") as tf:
        tf.add(root, arcname=inner_name)
    import shutil

    shutil.rmtree(staging)


def test_find_scaffold_assets() -> None:
    assets = [
        {"name": "scaffold-v0.4.1.tar.gz", "browser_download_url": "https://ex/tar"},
        {"name": "scaffold-v0.4.1.tar.gz.sha256", "browser_download_url": "https://ex/sha"},
    ]
    tar, sha = find_scaffold_assets(assets, "v0.4.1")
    assert tar == "https://ex/tar"
    assert sha == "https://ex/sha"


def test_verify_sha256_file(tmp_path: Path) -> None:
    blob = b"hello scaffold"
    tar = tmp_path / "scaffold-v0.4.1.tar.gz"
    tar.write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()
    sidecar = tmp_path / "scaffold-v0.4.1.tar.gz.sha256"
    sidecar.write_text(f"{digest}  scaffold-v0.4.1.tar.gz\n", encoding="utf-8")
    verify_sha256_file(tar, sidecar)
    sidecar.write_text("deadbeef\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        verify_sha256_file(tar, sidecar)


def test_install_scaffold_release_swap(tmp_path: Path, monkeypatch) -> None:
    live = tmp_path / "scaffold"
    live.mkdir()
    (live / ".scaffold-version").write_text("v0.3.0\n", encoding="utf-8")
    (live / "old-marker.txt").write_text("old\n", encoding="utf-8")

    tag = "v0.4.1"
    tar_path = tmp_path / "scaffold-v0.4.1.tar.gz"
    _make_scaffold_tarball(tar_path)
    digest = hashlib.sha256(tar_path.read_bytes()).hexdigest()
    sha_path = tmp_path / "scaffold-v0.4.1.tar.gz.sha256"
    sha_path.write_text(f"{digest}\n", encoding="utf-8")

    assets = [
        {"name": f"scaffold-{tag}.tar.gz", "browser_download_url": tar_path.as_uri()},
        {
            "name": f"scaffold-{tag}.tar.gz.sha256",
            "browser_download_url": sha_path.as_uri(),
        },
    ]

    sources = {
        tar_path.as_uri(): tar_path,
        sha_path.as_uri(): sha_path,
    }

    def fake_download(url: str, dest: Path) -> None:
        src = sources[url]
        dest.write_bytes(src.read_bytes())

    monkeypatch.setattr(
        "llm_cli.core.scaffold_update._download_file",
        fake_download,
    )

    install_scaffold_release(tag, assets, scaffold_base=live)

    assert (live / ".scaffold-version").read_text(encoding="utf-8").strip() == tag
    assert (live / "requirements.yaml").is_file()
    assert not (live / "old-marker.txt").exists()
    old = live.parent / "scaffold.old"
    assert old.is_dir()
    remove_scaffold_backup(scaffold_base=live)
    assert not old.exists()


def test_rollback_scaffold(tmp_path: Path) -> None:
    live = tmp_path / "scaffold"
    old = tmp_path / "scaffold.old"
    live.mkdir()
    old.mkdir()
    (live / ".scaffold-version").write_text("v0.4.1\n", encoding="utf-8")
    (old / ".scaffold-version").write_text("v0.3.0\n", encoding="utf-8")
    rollback_scaffold(scaffold_base=live)
    assert (live / ".scaffold-version").read_text(encoding="utf-8").strip() == "v0.3.0"
