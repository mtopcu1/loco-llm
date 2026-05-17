"""Pure helpers for model id derivation and format inference."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from llm_cli.core.hf_url import ParsedHFUrl
from llm_cli.core.model_registry import Artifact


_SLUG_NON_WORD = re.compile(r"[^a-z0-9.]+")
_SHARD_SUFFIX = re.compile(r"-\d{5}-of-\d{5}$", re.IGNORECASE)
_GGUF_SUFFIX = re.compile(r"\.gguf$", re.IGNORECASE)
_GGUF_REPO_SUFFIX = re.compile(r"-gguf$", re.IGNORECASE)


def _slug(token: str) -> str:
    return _SLUG_NON_WORD.sub("-", token.lower()).strip("-")


def _repo_slug(repo: str) -> str:
    owner, _, repo_name = repo.partition("/")
    repo_name = _GGUF_REPO_SUFFIX.sub("", repo_name)
    return f"{_slug(owner)}-{_slug(repo_name)}"


def _repo_base_name(repo: str) -> str:
    """`unsloth/Qwen3.6-235B-A22B-GGUF` -> `Qwen3.6-235B-A22B` (strips trailing -GGUF)."""
    _, _, name = repo.partition("/")
    return _GGUF_REPO_SUFFIX.sub("", name)


def _quant_suffix(filename: str, repo: str) -> str:
    """Pull the quant tag out of a GGUF filename using the repo's base name as prefix."""
    name = filename.rsplit("/", 1)[-1]
    name = _GGUF_SUFFIX.sub("", name)
    name = _SHARD_SUFFIX.sub("", name)
    base = _repo_base_name(repo)
    if base and name.startswith(base):
        name = name[len(base) :].lstrip("-_.")
    return _slug(name)


def derive_model_id(parsed: ParsedHFUrl) -> str:
    """Derive a stable id from a parsed HF URL."""
    base = _repo_slug(parsed.repo)
    if parsed.file is None:
        return base
    suffix = _quant_suffix(parsed.file, parsed.repo)
    return f"{base}__{suffix}" if suffix else base


@dataclass(frozen=True)
class InferResult:
    format: str
    include: tuple[str, ...]


class FormatInferenceError(ValueError):
    """Raised when the format cannot be inferred from a URL + repo listing."""


def _strip_shard(name: str) -> str:
    return _SHARD_SUFFIX.sub("", _GGUF_SUFFIX.sub("", name))


def _gguf_families(files: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name in files:
        if not _GGUF_SUFFIX.search(name):
            continue
        family = _strip_shard(name)
        out.setdefault(family, []).append(name)
    return {k: sorted(v) for k, v in out.items()}


def infer_format(parsed: ParsedHFUrl, repo_files: list[str]) -> InferResult:
    if parsed.file is not None:
        if _GGUF_SUFFIX.search(parsed.file):
            family_base = _strip_shard(parsed.file)
            matches = [
                f
                for f in repo_files
                if _strip_shard(f) == family_base and _GGUF_SUFFIX.search(f)
            ]
            include = tuple(sorted(matches)) if matches else (parsed.file,)
            return InferResult(format="gguf", include=include)
        raise FormatInferenceError(
            f"file {parsed.file!r} has unsupported extension; "
            "re-run with --format and/or --include to disambiguate"
        )

    families = _gguf_families(repo_files)
    has_safetensors = any(f.endswith(".safetensors") for f in repo_files)
    has_config = any(f == "config.json" for f in repo_files)
    if families and has_safetensors:
        raise FormatInferenceError(
            "repo mixes GGUF and safetensors files; "
            "re-run with --format and/or --include"
        )
    if not families and has_safetensors and has_config:
        return InferResult(format="safetensors-dir", include=())
    if families and not has_safetensors:
        if len(families) == 1:
            (only,) = families.values()
            return InferResult(format="gguf", include=tuple(only))
        raise FormatInferenceError(
            "repo contains multiple GGUF quants; "
            f"re-run with --include for one of: {sorted(families)}"
        )
    raise FormatInferenceError(
        "could not infer format from repo contents; "
        "re-run with --format and/or --include"
    )


def _walk_relative(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out.append(p.relative_to(root))
    return out


def build_artifact(download_dir: Path, format_: str) -> Artifact:
    files = _walk_relative(download_dir)
    if not files:
        raise ValueError(f"no files under {download_dir}")
    rel_strs = [p.as_posix() for p in files]
    total = sum((download_dir / p).stat().st_size for p in files)
    if format_ == "gguf":
        gguf = sorted(p for p in rel_strs if _GGUF_SUFFIX.search(p))
        if not gguf:
            raise ValueError(f"no .gguf files under {download_dir}")
        primary = gguf[0]
        return Artifact(
            primary=primary,
            files=tuple(gguf),
            total_size_bytes=total,
            sha256={},
        )
    if format_ == "safetensors-dir":
        if "config.json" not in rel_strs:
            raise ValueError(f"safetensors-dir missing config.json under {download_dir}")
        return Artifact(
            primary=".",
            files=tuple(sorted(rel_strs)),
            total_size_bytes=total,
            sha256={},
        )
    raise ValueError(f"unsupported format {format_!r}")
