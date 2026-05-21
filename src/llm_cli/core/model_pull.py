"""HF URL model pull (CLI and dashboard API)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from subprocess import run as _subprocess_run
from typing import Optional

from llm_cli.core.hf_client import HFApiError, fetch_repo_revision
from llm_cli.core.hf_url import HFUrlError, parse_hf_url
from llm_cli.core.model_registry import (
    Artifact,
    HFSource,
    Metadata,
    RegistryEntry,
    get_entry,
    upsert_entry,
)
from llm_cli.core.model_resolve import (
    FormatInferenceError,
    build_artifact,
    derive_model_id,
    infer_format,
)
from llm_cli.core.settings import load_settings, resolve
from llm_cli.core.time import utc_now_iso


class PullModelError(Exception):
    """Non-zero exit path for HF URL pulls."""


class DuplicateModelRegistrationError(PullModelError):
    """HF URL resolves to a model id that is already in the registry."""

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        super().__init__(
            f"{model_id!r} already registered; use --force or "
            f"`loco model uninstall {model_id}` first"
        )


def hf_download(
    repo: str,
    revision: str,
    include: list[str],
    exclude: list[str],
    target_dir: Path,
) -> int:
    """Invoke ``hf download`` as a subprocess. Patched in tests."""
    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["hf", "download", repo, "--revision", revision, "--local-dir", str(target_dir)]
    for pat in include:
        cmd += ["--include", pat]
    for pat in exclude:
        cmd += ["--exclude", pat]
    result = _subprocess_run(cmd, check=False)
    return result.returncode



def _verify_sha256(target_dir: Path, expected: dict[str, str]) -> list[str]:
    errs: list[str] = []
    for rel, want in expected.items():
        p = target_dir / rel
        if not p.is_file():
            errs.append(f"{rel}: file missing on disk")
            continue
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024), b""):
                h.update(chunk)
        got = h.hexdigest()
        if got != want:
            errs.append(f"{rel}: sha256 mismatch (got {got[:8]}…, want {want[:8]}…)")
    return errs


def pull_hf_url_model_id(
    url: str,
    *,
    fmt: Optional[str] = None,
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
    id_override: Optional[str] = None,
    force: bool = False,
) -> str:
    """Register a model from a Hugging Face URL; returns the model id."""
    models_dir = resolve(load_settings()).models_dir
    try:
        parsed = parse_hf_url(url)
    except HFUrlError as exc:
        raise PullModelError(str(exc)) from exc

    try:
        info = fetch_repo_revision(parsed.repo, revision=parsed.revision)
    except HFApiError as exc:
        raise PullModelError(str(exc)) from exc

    include = list(include or [])
    exclude = list(exclude or [])

    inferred = None
    if not (fmt and include):
        try:
            inferred = infer_format(parsed, [s.rfilename for s in info.siblings])
        except FormatInferenceError as exc:
            raise PullModelError(str(exc)) from exc

    chosen_format = fmt or (inferred.format if inferred else "")
    chosen_include = list(include or (inferred.include if inferred else ()))
    chosen_exclude = list(exclude)

    if not chosen_format:
        raise PullModelError("could not determine format; pass --format")

    mid = id_override or derive_model_id(parsed)
    target_dir = models_dir / mid
    if get_entry(models_dir, mid) is not None and not force:
        raise DuplicateModelRegistrationError(mid)

    rc = hf_download(
        parsed.repo, parsed.revision, chosen_include, chosen_exclude, target_dir
    )
    if rc != 0:
        raise PullModelError(f"hf download failed (exit {rc})")

    artifact = build_artifact(target_dir, chosen_format)
    sha_map = {
        s.rfilename: s.lfs_sha256
        for s in info.siblings
        if s.lfs_sha256 and s.rfilename in artifact.files
    }
    bad = _verify_sha256(target_dir, sha_map)
    if bad:
        raise PullModelError("; ".join(bad))

    artifact_with_hashes = Artifact(
        primary=artifact.primary,
        files=artifact.files,
        total_size_bytes=artifact.total_size_bytes,
        sha256=sha_map,
    )

    entry = RegistryEntry(
        id=mid,
        format=chosen_format,
        source=HFSource(
            repo=parsed.repo,
            revision=parsed.revision,
            include=tuple(chosen_include),
            exclude=tuple(chosen_exclude),
        ),
        artifact=artifact_with_hashes,
        metadata=Metadata(
            display_name=info.repo,
            license=info.license,
            ctx_length=None,
        ),
        installed_at=utc_now_iso(),
    )
    upsert_entry(models_dir, entry)
    return mid
