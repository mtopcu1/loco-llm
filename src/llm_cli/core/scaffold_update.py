"""Download and atomically swap the managed scaffold directory."""
from __future__ import annotations

import hashlib
import shutil
import tarfile
from pathlib import Path

import httpx

GITHUB_REPO = "mtopcu1/local-llm-scaffold"


def _scaffold_asset_names(tag: str) -> tuple[str, str]:
    """Return (tarball_name, sha256_sidecar_name) for a release tag."""
    return f"scaffold-{tag}.tar.gz", f"scaffold-{tag}.tar.gz.sha256"


def find_scaffold_assets(assets: list[dict], tag: str) -> tuple[str, str]:
    """Resolve download URLs for tarball and sha256 sidecar from release assets."""
    tar_name, sha_name = _scaffold_asset_names(tag)
    tar_url: str | None = None
    sha_url: str | None = None
    for asset in assets:
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if not name or not url:
            continue
        if name == tar_name:
            tar_url = str(url)
        elif name == sha_name:
            sha_url = str(url)
    if not tar_url or not sha_url:
        raise ValueError(
            f"release {tag!r} missing scaffold assets "
            f"({tar_name!r} and/or {sha_name!r})"
        )
    return tar_url, sha_url


def verify_sha256_file(tarball: Path, sidecar: Path) -> None:
    """Verify tarball digest against ``<name>.sha256`` sidecar contents."""
    expected_line = sidecar.read_text(encoding="utf-8").strip().split()
    if not expected_line:
        raise ValueError(f"empty sha256 sidecar: {sidecar}")
    expected = expected_line[0].lower()
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest().lower()
    if digest != expected:
        raise ValueError(
            f"sha256 mismatch for {tarball.name}: expected {expected}, got {digest}"
        )


def _download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)


def _extract_tarball(tarball: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball, "r:gz") as tf:
        tf.extractall(dest_dir, filter="data")


def _relocate_extracted_root(staging: Path) -> None:
    """If extract created a single top-level directory, hoist its contents up."""
    children = [p for p in staging.iterdir() if p.name != ".scaffold-version"]
    if len(children) == 1 and children[0].is_dir():
        inner = children[0]
        for item in inner.iterdir():
            target = staging / item.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            shutil.move(str(item), str(target))
        inner.rmdir()


def install_scaffold_release(
    tag: str,
    assets: list[dict],
    *,
    yes: bool = False,  # noqa: ARG001 - reserved for future prompts
    scaffold_base: Path | None = None,
) -> Path:
    """Download, verify, extract, and atomically swap the scaffold directory.

    Returns the live scaffold path after a successful swap.
    """
    del yes
    if scaffold_base is None:
        from llm_cli.core.scaffold import scaffold_root

        live = scaffold_root()
    else:
        live = scaffold_base
    parent = live.parent
    new_dir = parent / f"{live.name}.new"
    old_dir = parent / f"{live.name}.old"
    failed_dir = parent / f"{live.name}.failed"
    tarball = parent / f"{live.name}.new.tar.gz"
    sidecar = parent / f"{live.name}.new.tar.gz.sha256"

    tar_url, sha_url = find_scaffold_assets(assets, tag)

    for path in (new_dir, old_dir, failed_dir, tarball, sidecar):
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    try:
        _download_file(tar_url, tarball)
        _download_file(sha_url, sidecar)
        verify_sha256_file(tarball, sidecar)
        _extract_tarball(tarball, new_dir)
        _relocate_extracted_root(new_dir)
        (new_dir / ".scaffold-version").write_text(tag + "\n", encoding="utf-8")

        if live.exists():
            live.rename(old_dir)
        new_dir.rename(live)
    except Exception:
        if new_dir.exists():
            shutil.rmtree(new_dir, ignore_errors=True)
        if live.exists() and not old_dir.exists():
            pass
        elif old_dir.exists() and not live.exists():
            old_dir.rename(live)
        elif live.exists() and old_dir.exists():
            if live.exists():
                live.rename(failed_dir)
            old_dir.rename(live)
        raise
    finally:
        tarball.unlink(missing_ok=True)
        sidecar.unlink(missing_ok=True)

    return live


def remove_scaffold_backup(scaffold_base: Path | None = None) -> None:
    """Delete ``.old`` scaffold backup after successful verify."""
    if scaffold_base is None:
        from llm_cli.core.scaffold import scaffold_root

        live = scaffold_root()
    else:
        live = scaffold_base
    old_dir = live.parent / f"{live.name}.old"
    if old_dir.exists():
        shutil.rmtree(old_dir, ignore_errors=True)


def rollback_scaffold(scaffold_base: Path | None = None) -> None:
    """Restore scaffold from ``.old`` after a failed verify (spec §9.2 step 5.7)."""
    if scaffold_base is None:
        from llm_cli.core.scaffold import scaffold_root

        live = scaffold_root()
    else:
        live = scaffold_base
    parent = live.parent
    old_dir = parent / f"{live.name}.old"
    failed_dir = parent / f"{live.name}.failed"
    if not old_dir.exists():
        return
    if live.exists():
        live.rename(failed_dir)
    old_dir.rename(live)
    if failed_dir.exists():
        shutil.rmtree(failed_dir, ignore_errors=True)
