# Models Registry Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-model `manifest.yaml` + `pull.sh` abstraction with a single `$LLM_MODELS/registry.json` populated by `llm model pull <hf-url>` / `llm model add <id> <path>`; add runtime `accepts_formats` gating and a `${model_path}` template in `serve.params`.

**Architecture:** Four new pure modules (`hf_url.py`, `hf_client.py`, `model_registry.py`, `model_resolve.py`) feed a rewritten `commands/model_cmd.py`. `core/registry.py` loses its model-discovery code, gains `accepts_formats` on `RuntimeManifest`, and tightens `validate_config_v2`. `core/config_resolve.py` learns `${model_path}`. The shipped `llamacpp` and `stub-runtime` manifests get `accepts_formats`; the tracked `stub-runtime__stub-model__default.yaml` config and `models/stub-model/` are deleted.

**Tech Stack:** Python 3.11+, Typer, Rich, PyYAML, pytest, stdlib `urllib` for HF API, subprocess via existing WSL runner for `hf download`.

**Spec:** [`docs/superpowers/specs/2026-05-17-models-registry-redesign.md`](../specs/2026-05-17-models-registry-redesign.md)

---

## Phase A — HF URL parser (`core/hf_url.py`)

### Task A1: ParsedHFUrl dataclass + bare repo URL

**Files:**
- Create: `src/llm_cli/core/hf_url.py`
- Test: `tests/unit/test_hf_url.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_hf_url.py
from __future__ import annotations

import pytest

from llm_cli.core.hf_url import ParsedHFUrl, parse_hf_url, HFUrlError


def test_parse_bare_repo_url():
    p = parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct")
    assert p == ParsedHFUrl(repo="Qwen/Qwen2.5-7B-Instruct", revision="main", file=None)


def test_parse_bare_repo_trailing_slash():
    p = parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/")
    assert p == ParsedHFUrl(repo="Qwen/Qwen2.5-7B-Instruct", revision="main", file=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_hf_url.py -v`
Expected: FAIL (module not importable).

- [ ] **Step 3: Write the implementation**

```python
# src/llm_cli/core/hf_url.py
"""Parse Hugging Face URLs into (repo, revision, file?)."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse


class HFUrlError(ValueError):
    """Raised when a URL is not a recognizable Hugging Face URL."""


@dataclass(frozen=True)
class ParsedHFUrl:
    """Pieces extracted from an HF URL. `file` is None for repo-level URLs."""

    repo: str
    revision: str
    file: str | None


_VALID_HOSTS = {"huggingface.co", "hf.co"}


def parse_hf_url(url: str) -> ParsedHFUrl:
    """Parse one of the supported HF URL shapes; raise HFUrlError otherwise."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HFUrlError(f"unsupported scheme {parsed.scheme!r} in {url!r}")
    host = (parsed.netloc or "").lower()
    if host not in _VALID_HOSTS:
        raise HFUrlError(f"not a Hugging Face host ({host!r}) in {url!r}")
    raw = unquote(parsed.path or "").strip("/")
    parts = raw.split("/") if raw else []
    if len(parts) < 2:
        raise HFUrlError(f"URL {url!r} does not contain <owner>/<repo>")
    owner, repo = parts[0], parts[1]
    repo_id = f"{owner}/{repo}"
    rest = parts[2:]
    if not rest:
        return ParsedHFUrl(repo=repo_id, revision="main", file=None)
    raise HFUrlError(f"unsupported HF URL shape: {url!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_hf_url.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/hf_url.py tests/unit/test_hf_url.py
git commit -m "feat(hf-url): parse bare HF repo URLs"
```

---

### Task A2: `tree/<rev>` URL shape

**Files:**
- Modify: `src/llm_cli/core/hf_url.py`
- Modify: `tests/unit/test_hf_url.py`

- [ ] **Step 1: Append failing tests**

```python
def test_parse_tree_url_with_revision():
    p = parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/tree/main")
    assert p == ParsedHFUrl(repo="Qwen/Qwen2.5-7B-Instruct", revision="main", file=None)


def test_parse_tree_url_with_branch_revision():
    p = parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/tree/feature-branch")
    assert p == ParsedHFUrl(
        repo="Qwen/Qwen2.5-7B-Instruct", revision="feature-branch", file=None
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_hf_url.py -v`
Expected: FAIL (tree shape unsupported).

- [ ] **Step 3: Extend the implementation**

Replace the `if not rest` block with:

```python
    if not rest:
        return ParsedHFUrl(repo=repo_id, revision="main", file=None)
    kind = rest[0]
    if kind == "tree":
        if len(rest) < 2:
            raise HFUrlError(f"`tree/` URL missing revision: {url!r}")
        revision = rest[1]
        if len(rest) > 2:
            raise HFUrlError(
                f"`tree/` URL must not include a file path: {url!r}"
            )
        return ParsedHFUrl(repo=repo_id, revision=revision, file=None)
    raise HFUrlError(f"unsupported HF URL shape: {url!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_hf_url.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/hf_url.py tests/unit/test_hf_url.py
git commit -m "feat(hf-url): parse tree/<rev> URLs"
```

---

### Task A3: `blob/<rev>/<file>` and `resolve/<rev>/<file>` URL shapes

**Files:**
- Modify: `src/llm_cli/core/hf_url.py`
- Modify: `tests/unit/test_hf_url.py`

- [ ] **Step 1: Append failing tests**

```python
def test_parse_blob_url():
    p = parse_hf_url(
        "https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF/blob/main/Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00010.gguf"
    )
    assert p == ParsedHFUrl(
        repo="unsloth/Qwen3.6-235B-A22B-GGUF",
        revision="main",
        file="Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00010.gguf",
    )


def test_parse_resolve_url():
    p = parse_hf_url(
        "https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF/resolve/main/weights.gguf"
    )
    assert p.file == "weights.gguf"


def test_parse_blob_nested_file():
    p = parse_hf_url(
        "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/blob/main/snapshots/abc/file.bin"
    )
    assert p.file == "snapshots/abc/file.bin"


def test_parse_blob_url_missing_file():
    with pytest.raises(HFUrlError, match="missing file path"):
        parse_hf_url("https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/blob/main/")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_hf_url.py -v`
Expected: FAIL (blob/resolve shapes unsupported).

- [ ] **Step 3: Extend the implementation**

Replace the `if kind == "tree"` block with:

```python
    if kind in ("tree", "blob", "resolve"):
        if len(rest) < 2:
            raise HFUrlError(f"`{kind}/` URL missing revision: {url!r}")
        revision = rest[1]
        file_parts = rest[2:]
        if kind == "tree":
            if file_parts:
                raise HFUrlError(
                    f"`tree/` URL must not include a file path: {url!r}"
                )
            return ParsedHFUrl(repo=repo_id, revision=revision, file=None)
        if not file_parts:
            raise HFUrlError(
                f"`{kind}/` URL missing file path: {url!r}"
            )
        file_str = "/".join(file_parts)
        return ParsedHFUrl(repo=repo_id, revision=revision, file=file_str)
    raise HFUrlError(f"unsupported HF URL shape: {url!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_hf_url.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/hf_url.py tests/unit/test_hf_url.py
git commit -m "feat(hf-url): parse blob/ and resolve/ file URLs"
```

---

### Task A4: `hf.co` short host + bad-URL coverage

**Files:**
- Modify: `tests/unit/test_hf_url.py`

- [ ] **Step 1: Append failing tests**

```python
def test_parse_hf_co_short_host():
    p = parse_hf_url("https://hf.co/Qwen/Qwen2.5-7B-Instruct/blob/main/weights.gguf")
    assert p.repo == "Qwen/Qwen2.5-7B-Instruct"
    assert p.file == "weights.gguf"


def test_parse_uppercase_host():
    p = parse_hf_url("https://HuggingFace.CO/Qwen/Qwen2.5-7B-Instruct")
    assert p.repo == "Qwen/Qwen2.5-7B-Instruct"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
        "https://example.com/Qwen/Qwen2.5-7B-Instruct",
        "https://huggingface.co/Qwen",
        "https://huggingface.co/",
        "https://huggingface.co/Qwen/repo/bogus/x",
    ],
)
def test_parse_bad_urls_raise(url):
    with pytest.raises(HFUrlError):
        parse_hf_url(url)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_hf_url.py -v`
Expected: PASS (the existing implementation already handles short host case-insensitively and rejects unknown shapes; if any fail, fix `_VALID_HOSTS` comparison or shape handling).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_hf_url.py
git commit -m "test(hf-url): cover short host and rejection paths"
```

---

## Phase B — HF metadata client (`core/hf_client.py`)

### Task B1: `fetch_repo_revision` returns parsed dict

**Files:**
- Create: `src/llm_cli/core/hf_client.py`
- Test: `tests/unit/test_hf_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_hf_client.py
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from llm_cli.core.hf_client import (
    HFApiError,
    HFRepoInfo,
    HFSibling,
    fetch_repo_revision,
)


_FAKE_PAYLOAD = {
    "id": "Qwen/Qwen2.5-7B-Instruct",
    "sha": "deadbeef",
    "cardData": {"license": "apache-2.0"},
    "siblings": [
        {
            "rfilename": "config.json",
            "size": 612,
            "lfs": None,
        },
        {
            "rfilename": "model-00001-of-00004.safetensors",
            "size": 4900000000,
            "lfs": {"sha256": "abc123", "size": 4900000000},
        },
    ],
}


def _fake_response(payload):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    resp.status = 200
    return resp


def test_fetch_repo_revision_parses_payload():
    with patch("llm_cli.core.hf_client.urlopen", return_value=_fake_response(_FAKE_PAYLOAD)):
        info = fetch_repo_revision("Qwen/Qwen2.5-7B-Instruct", revision="main")
    assert isinstance(info, HFRepoInfo)
    assert info.repo == "Qwen/Qwen2.5-7B-Instruct"
    assert info.revision == "main"
    assert info.sha == "deadbeef"
    assert info.license == "apache-2.0"
    by_name = {s.rfilename: s for s in info.siblings}
    assert by_name["config.json"].lfs_sha256 is None
    assert by_name["config.json"].size == 612
    assert by_name["model-00001-of-00004.safetensors"].lfs_sha256 == "abc123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_hf_client.py -v`
Expected: FAIL (module not importable).

- [ ] **Step 3: Write the implementation**

```python
# src/llm_cli/core/hf_client.py
"""Minimal Hugging Face Hub metadata client (read-only, public API)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_BASE = "https://huggingface.co/api/models"


class HFApiError(RuntimeError):
    """Wraps HTTP / network failures from the public HF API."""


@dataclass(frozen=True)
class HFSibling:
    rfilename: str
    size: int | None
    lfs_sha256: str | None


@dataclass(frozen=True)
class HFRepoInfo:
    repo: str
    revision: str
    sha: str
    license: str | None
    siblings: list[HFSibling]


def _request(url: str, *, token: str | None) -> bytes:
    headers = {"Accept": "application/json", "User-Agent": "localllm-cli/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read()
    except HTTPError as exc:
        raise HFApiError(f"HF API HTTP {exc.code} for {url}: {exc.reason}") from exc
    except URLError as exc:
        raise HFApiError(f"HF API network error for {url}: {exc.reason}") from exc


def fetch_repo_revision(repo: str, revision: str = "main") -> HFRepoInfo:
    """Fetch repo metadata for `<repo>@<revision>`; HFApiError on failure."""
    url = f"{_BASE}/{repo}/revision/{revision}"
    token = os.environ.get("HF_TOKEN")
    raw = _request(url, token=token)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HFApiError(f"HF API returned non-JSON for {url}: {exc}") from exc

    card = payload.get("cardData") or {}
    license_ = card.get("license") if isinstance(card, dict) else None
    siblings_raw = payload.get("siblings") or []
    siblings: list[HFSibling] = []
    for s in siblings_raw:
        if not isinstance(s, dict):
            continue
        lfs = s.get("lfs") if isinstance(s.get("lfs"), dict) else None
        siblings.append(
            HFSibling(
                rfilename=str(s.get("rfilename", "")),
                size=int(s["size"]) if isinstance(s.get("size"), int) else None,
                lfs_sha256=str(lfs["sha256"]) if lfs and "sha256" in lfs else None,
            )
        )
    return HFRepoInfo(
        repo=str(payload.get("id", repo)),
        revision=revision,
        sha=str(payload.get("sha", "")),
        license=str(license_) if isinstance(license_, str) else None,
        siblings=siblings,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_hf_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/hf_client.py tests/unit/test_hf_client.py
git commit -m "feat(hf-client): fetch repo revision metadata"
```

---

### Task B2: HF_TOKEN auth + HTTPError surfacing

**Files:**
- Modify: `tests/unit/test_hf_client.py`

- [ ] **Step 1: Append failing tests**

```python
def test_fetch_includes_authorization_when_hf_token_env(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.headers)
        return _fake_response(_FAKE_PAYLOAD)

    monkeypatch.setenv("HF_TOKEN", "secret123")
    with patch("llm_cli.core.hf_client.urlopen", side_effect=fake_urlopen):
        fetch_repo_revision("Qwen/Qwen2.5-7B-Instruct", revision="main")
    assert captured["headers"]["Authorization"] == "Bearer secret123"


def test_fetch_404_raises_hf_api_error(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)

    def boom(req, timeout):
        from urllib.error import HTTPError
        raise HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=None)

    with patch("llm_cli.core.hf_client.urlopen", side_effect=boom):
        with pytest.raises(HFApiError, match="HTTP 404"):
            fetch_repo_revision("nope/nope")


def test_fetch_network_error_raises_hf_api_error(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    from urllib.error import URLError

    with patch("llm_cli.core.hf_client.urlopen", side_effect=URLError("offline")):
        with pytest.raises(HFApiError, match="network error"):
            fetch_repo_revision("Qwen/Qwen2.5-7B-Instruct")
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_hf_client.py -v`
Expected: PASS (implementation from B1 already covers these; if `urllib.request.Request.headers` capitalizes keys, adjust the assertion to use `req.get_header("Authorization")` instead).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_hf_client.py
git commit -m "test(hf-client): auth header + HTTP/network failure paths"
```

---

## Phase C — Model registry I/O (`core/model_registry.py`)

### Task C1: Dataclasses + JSON encode/decode round-trip

**Files:**
- Create: `src/llm_cli/core/model_registry.py`
- Test: `tests/unit/test_model_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_model_registry.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_cli.core.model_registry import (
    Artifact,
    HFSource,
    LocalSource,
    Metadata,
    RegistryEntry,
    encode_entry,
    decode_entry,
)


def _hf_entry() -> RegistryEntry:
    return RegistryEntry(
        id="unsloth-qwen3.6-235b-a22b__ud-q4-k-xl",
        format="gguf",
        source=HFSource(
            repo="unsloth/Qwen3.6-235B-A22B-GGUF",
            revision="main",
            include=("*UD-Q4_K_XL*",),
            exclude=(),
        ),
        artifact=Artifact(
            primary="model-00001-of-00010.gguf",
            files=("model-00001-of-00010.gguf", "model-00002-of-00010.gguf"),
            total_size_bytes=210432000000,
            sha256={"model-00001-of-00010.gguf": "abc"},
        ),
        metadata=Metadata(
            display_name="Qwen3.6 GGUF",
            license="apache-2.0",
            ctx_length=32768,
        ),
        installed_at="2026-05-17T20:00:00Z",
    )


def test_encode_decode_hf_entry_roundtrip():
    entry = _hf_entry()
    raw = encode_entry(entry)
    assert raw["format"] == "gguf"
    assert raw["source"]["kind"] == "hf"
    assert raw["source"]["include"] == ["*UD-Q4_K_XL*"]
    decoded = decode_entry(entry.id, raw)
    assert decoded == entry


def test_decode_local_entry():
    raw = {
        "format": "safetensors-dir",
        "source": {"kind": "local", "original_path": "/home/u/my"},
        "artifact": {
            "primary": ".",
            "files": ["config.json"],
            "total_size_bytes": 1024,
            "sha256": {},
        },
        "metadata": {"display_name": "My finetune"},
        "installed_at": "2026-05-17T21:00:00Z",
    }
    entry = decode_entry("my-finetune", raw)
    assert isinstance(entry.source, LocalSource)
    assert entry.source.original_path == "/home/u/my"
    assert entry.metadata.ctx_length is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_model_registry.py -v`
Expected: FAIL (module not importable).

- [ ] **Step 3: Write the implementation**

```python
# src/llm_cli/core/model_registry.py
"""Local model registry persisted as $LLM_MODELS/registry.json."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Union

REGISTRY_FILENAME = "registry.json"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class HFSource:
    kind: str = "hf"
    repo: str = ""
    revision: str = "main"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class LocalSource:
    kind: str = "local"
    original_path: str = ""


Source = Union[HFSource, LocalSource]


@dataclass(frozen=True)
class Artifact:
    primary: str
    files: tuple[str, ...]
    total_size_bytes: int
    sha256: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Metadata:
    display_name: str = ""
    license: str | None = None
    ctx_length: int | None = None


@dataclass(frozen=True)
class RegistryEntry:
    id: str
    format: str
    source: Source
    artifact: Artifact
    metadata: Metadata
    installed_at: str


def _encode_source(src: Source) -> dict[str, Any]:
    if isinstance(src, HFSource):
        return {
            "kind": "hf",
            "repo": src.repo,
            "revision": src.revision,
            "include": list(src.include),
            "exclude": list(src.exclude),
        }
    if isinstance(src, LocalSource):
        return {"kind": "local", "original_path": src.original_path}
    raise TypeError(f"unknown source type: {type(src).__name__}")


def encode_entry(entry: RegistryEntry) -> dict[str, Any]:
    return {
        "format": entry.format,
        "source": _encode_source(entry.source),
        "artifact": {
            "primary": entry.artifact.primary,
            "files": list(entry.artifact.files),
            "total_size_bytes": entry.artifact.total_size_bytes,
            "sha256": dict(entry.artifact.sha256),
        },
        "metadata": {
            "display_name": entry.metadata.display_name,
            "license": entry.metadata.license,
            "ctx_length": entry.metadata.ctx_length,
        },
        "installed_at": entry.installed_at,
    }


def _decode_source(raw: dict[str, Any]) -> Source:
    kind = str(raw.get("kind", ""))
    if kind == "hf":
        return HFSource(
            repo=str(raw.get("repo", "")),
            revision=str(raw.get("revision", "main")),
            include=tuple(str(p) for p in (raw.get("include") or [])),
            exclude=tuple(str(p) for p in (raw.get("exclude") or [])),
        )
    if kind == "local":
        return LocalSource(original_path=str(raw.get("original_path", "")))
    raise ValueError(f"unknown source kind {kind!r}")


def decode_entry(entry_id: str, raw: dict[str, Any]) -> RegistryEntry:
    art = raw.get("artifact") or {}
    md = raw.get("metadata") or {}
    return RegistryEntry(
        id=entry_id,
        format=str(raw["format"]),
        source=_decode_source(raw.get("source") or {}),
        artifact=Artifact(
            primary=str(art.get("primary", "")),
            files=tuple(str(p) for p in (art.get("files") or [])),
            total_size_bytes=int(art.get("total_size_bytes") or 0),
            sha256={str(k): str(v) for k, v in (art.get("sha256") or {}).items()},
        ),
        metadata=Metadata(
            display_name=str(md.get("display_name", "")),
            license=str(md["license"]) if md.get("license") is not None else None,
            ctx_length=int(md["ctx_length"]) if md.get("ctx_length") is not None else None,
        ),
        installed_at=str(raw.get("installed_at", "")),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_model_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/model_registry.py tests/unit/test_model_registry.py
git commit -m "feat(model-registry): dataclasses + entry encode/decode"
```

---

### Task C2: Atomic load/write + missing-file tolerance

**Files:**
- Modify: `src/llm_cli/core/model_registry.py`
- Modify: `tests/unit/test_model_registry.py`

- [ ] **Step 1: Append failing tests**

```python
from llm_cli.core.model_registry import (
    load_registry,
    write_registry,
    registry_path,
)


def test_load_missing_returns_empty(tmp_path: Path):
    reg = load_registry(tmp_path)
    assert reg == {}


def test_write_then_load_roundtrip(tmp_path: Path):
    entry = _hf_entry()
    write_registry(tmp_path, {entry.id: entry})
    reg = load_registry(tmp_path)
    assert list(reg.keys()) == [entry.id]
    assert reg[entry.id] == entry
    p = registry_path(tmp_path)
    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert on_disk["version"] == 1
    assert entry.id in on_disk["models"]


def test_load_malformed_raises(tmp_path: Path):
    registry_path(tmp_path).write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="registry.json"):
        load_registry(tmp_path)


def test_load_wrong_version_raises(tmp_path: Path):
    registry_path(tmp_path).write_text(
        json.dumps({"version": 99, "models": {}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unsupported registry version"):
        load_registry(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_model_registry.py -v`
Expected: FAIL (load/write not implemented).

- [ ] **Step 3: Extend the implementation**

Append to `src/llm_cli/core/model_registry.py`:

```python
def registry_path(models_dir: Path) -> Path:
    return models_dir / REGISTRY_FILENAME


def load_registry(models_dir: Path) -> dict[str, RegistryEntry]:
    """Return all entries; an absent file is a clean empty registry."""
    p = registry_path(models_dir)
    if not p.is_file():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{p}: malformed registry.json ({exc})") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{p}: registry.json top-level must be a mapping")
    version = payload.get("version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"{p}: unsupported registry version {version!r}; expected {SCHEMA_VERSION}"
        )
    models = payload.get("models") or {}
    if not isinstance(models, dict):
        raise ValueError(f"{p}: models must be a mapping")
    out: dict[str, RegistryEntry] = {}
    for mid, raw in models.items():
        if not isinstance(raw, dict):
            raise ValueError(f"{p}: entry {mid!r} must be a mapping")
        out[str(mid)] = decode_entry(str(mid), raw)
    return out


def write_registry(models_dir: Path, entries: dict[str, RegistryEntry]) -> Path:
    """Atomically write the registry; creates parent dir if needed."""
    models_dir.mkdir(parents=True, exist_ok=True)
    p = registry_path(models_dir)
    payload = {
        "version": SCHEMA_VERSION,
        "models": {mid: encode_entry(e) for mid, e in sorted(entries.items())},
    }
    fd, tmp_name = tempfile.mkstemp(
        prefix=".registry.", suffix=".tmp", dir=str(models_dir)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        os.replace(tmp_name, p)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
    return p
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_model_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/model_registry.py tests/unit/test_model_registry.py
git commit -m "feat(model-registry): atomic load/write of registry.json"
```

---

### Task C3: `get_entry` / `upsert_entry` / `remove_entry` helpers

**Files:**
- Modify: `src/llm_cli/core/model_registry.py`
- Modify: `tests/unit/test_model_registry.py`

- [ ] **Step 1: Append failing tests**

```python
from llm_cli.core.model_registry import get_entry, upsert_entry, remove_entry


def test_upsert_and_get(tmp_path: Path):
    entry = _hf_entry()
    upsert_entry(tmp_path, entry)
    fetched = get_entry(tmp_path, entry.id)
    assert fetched == entry


def test_get_missing_returns_none(tmp_path: Path):
    assert get_entry(tmp_path, "nope") is None


def test_remove_entry(tmp_path: Path):
    entry = _hf_entry()
    upsert_entry(tmp_path, entry)
    assert remove_entry(tmp_path, entry.id) is True
    assert get_entry(tmp_path, entry.id) is None
    # second remove is a no-op
    assert remove_entry(tmp_path, entry.id) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_model_registry.py -v`
Expected: FAIL (helpers not implemented).

- [ ] **Step 3: Append the helpers**

```python
def get_entry(models_dir: Path, entry_id: str) -> RegistryEntry | None:
    return load_registry(models_dir).get(entry_id)


def upsert_entry(models_dir: Path, entry: RegistryEntry) -> Path:
    entries = load_registry(models_dir)
    entries[entry.id] = entry
    return write_registry(models_dir, entries)


def remove_entry(models_dir: Path, entry_id: str) -> bool:
    entries = load_registry(models_dir)
    if entry_id not in entries:
        return False
    entries.pop(entry_id)
    write_registry(models_dir, entries)
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_model_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/model_registry.py tests/unit/test_model_registry.py
git commit -m "feat(model-registry): get/upsert/remove helpers"
```

---

## Phase D — Format inference + id derivation (`core/model_resolve.py`)

### Task D1: `derive_model_id` from URL pieces

**Files:**
- Create: `src/llm_cli/core/model_resolve.py`
- Test: `tests/unit/test_model_resolve.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_model_resolve.py
from __future__ import annotations

import pytest

from llm_cli.core.hf_url import ParsedHFUrl
from llm_cli.core.model_resolve import derive_model_id


def test_derive_id_safetensors_repo():
    p = ParsedHFUrl(repo="Qwen/Qwen2.5-7B-Instruct", revision="main", file=None)
    assert derive_model_id(p) == "qwen-qwen2.5-7b-instruct"


def test_derive_id_gguf_file():
    p = ParsedHFUrl(
        repo="unsloth/Qwen3.6-235B-A22B-GGUF",
        revision="main",
        file="Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00010.gguf",
    )
    assert derive_model_id(p) == "unsloth-qwen3.6-235b-a22b__ud-q4-k-xl"


def test_derive_id_gguf_single_file_no_shard():
    p = ParsedHFUrl(
        repo="bartowski/Foo-GGUF",
        revision="main",
        file="Foo-Q5_K_M.gguf",
    )
    assert derive_model_id(p) == "bartowski-foo__q5-k-m"


def test_derive_id_gguf_file_when_name_equals_repo_base():
    p = ParsedHFUrl(
        repo="o/Foo-GGUF",
        revision="main",
        file="Foo.gguf",
    )
    # When stripping the repo's base name from the file leaves nothing, drop the suffix.
    assert derive_model_id(p) == "o-foo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_model_resolve.py -v`
Expected: FAIL (module not importable).

- [ ] **Step 3: Write the implementation**

```python
# src/llm_cli/core/model_resolve.py
"""Pure helpers for model id derivation and format inference."""
from __future__ import annotations

import re
from dataclasses import dataclass

from llm_cli.core.hf_url import ParsedHFUrl


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
    """Pull the quant tag out of a GGUF filename using the repo's base name as prefix.

    e.g. file `Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00010.gguf`
         repo `unsloth/Qwen3.6-235B-A22B-GGUF`
    -> strip ext + shard suffix      -> `Qwen3.6-235B-A22B-UD-Q4_K_XL`
    -> strip repo base + leading `-` -> `UD-Q4_K_XL`
    -> slug                          -> `ud-q4-k-xl`
    """
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_model_resolve.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/model_resolve.py tests/unit/test_model_resolve.py
git commit -m "feat(model-resolve): derive_model_id from HF URL pieces"
```

---

### Task D2: `infer_format` from URL + repo file list

**Files:**
- Modify: `src/llm_cli/core/model_resolve.py`
- Modify: `tests/unit/test_model_resolve.py`

- [ ] **Step 1: Append failing tests**

```python
from llm_cli.core.model_resolve import (
    InferResult,
    FormatInferenceError,
    infer_format,
)


def _files(*names: str) -> list[str]:
    return list(names)


def test_infer_format_url_with_gguf_file():
    p = ParsedHFUrl(repo="o/r", revision="main", file="weights.gguf")
    r = infer_format(p, _files("weights.gguf", "config.json"))
    assert r == InferResult(format="gguf", include=("weights.gguf",))


def test_infer_format_url_with_unsupported_file_errors():
    p = ParsedHFUrl(repo="o/r", revision="main", file="model.bin")
    with pytest.raises(FormatInferenceError, match="--format and/or --include"):
        infer_format(p, _files("model.bin"))


def test_infer_format_repo_single_gguf():
    p = ParsedHFUrl(repo="o/r", revision="main", file=None)
    r = infer_format(p, _files("only-Q4.gguf", "README.md"))
    assert r.format == "gguf"
    assert r.include == ("only-Q4.gguf",)


def test_infer_format_repo_safetensors_dir():
    p = ParsedHFUrl(repo="o/r", revision="main", file=None)
    files = _files("config.json", "tokenizer.json", "model-00001-of-00004.safetensors")
    r = infer_format(p, files)
    assert r.format == "safetensors-dir"
    assert r.include == ()


def test_infer_format_repo_multiple_gguf_quants_errors():
    p = ParsedHFUrl(repo="o/r", revision="main", file=None)
    files = _files("model-Q4_K_M.gguf", "model-Q5_K_M.gguf")
    with pytest.raises(FormatInferenceError, match="multiple GGUF"):
        infer_format(p, files)


def test_infer_format_mixed_repo_errors():
    p = ParsedHFUrl(repo="o/r", revision="main", file=None)
    files = _files("model-Q4_K_M.gguf", "config.json", "model.safetensors")
    with pytest.raises(FormatInferenceError, match="mixed"):
        infer_format(p, files)


def test_infer_format_split_gguf_one_family_ok():
    p = ParsedHFUrl(repo="o/r", revision="main", file=None)
    files = _files(
        "model-Q4_K_M-00001-of-00003.gguf",
        "model-Q4_K_M-00002-of-00003.gguf",
        "model-Q4_K_M-00003-of-00003.gguf",
    )
    r = infer_format(p, files)
    assert r.format == "gguf"
    assert sorted(r.include) == sorted(files)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_model_resolve.py -v`
Expected: FAIL.

- [ ] **Step 3: Extend the implementation**

Append to `src/llm_cli/core/model_resolve.py`:

```python
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
                f for f in repo_files if _strip_shard(f) == family_base and _GGUF_SUFFIX.search(f)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_model_resolve.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/model_resolve.py tests/unit/test_model_resolve.py
git commit -m "feat(model-resolve): infer_format with strict ambiguity handling"
```

---

### Task D3: `build_artifact` from a download directory

**Files:**
- Modify: `src/llm_cli/core/model_resolve.py`
- Modify: `tests/unit/test_model_resolve.py`

- [ ] **Step 1: Append failing tests**

```python
from pathlib import Path

from llm_cli.core.model_resolve import build_artifact


def test_build_artifact_single_gguf(tmp_path: Path):
    f = tmp_path / "weights.gguf"
    f.write_bytes(b"x" * 1024)
    art = build_artifact(tmp_path, "gguf")
    assert art.primary == "weights.gguf"
    assert art.files == ("weights.gguf",)
    assert art.total_size_bytes == 1024


def test_build_artifact_split_gguf(tmp_path: Path):
    for i in (1, 2, 3):
        (tmp_path / f"model-Q4-{i:05d}-of-00003.gguf").write_bytes(b"x" * 10)
    art = build_artifact(tmp_path, "gguf")
    assert art.primary == "model-Q4-00001-of-00003.gguf"
    assert art.files[0] == "model-Q4-00001-of-00003.gguf"
    assert len(art.files) == 3


def test_build_artifact_safetensors_dir(tmp_path: Path):
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model-00001-of-00002.safetensors").write_bytes(b"x" * 50)
    (tmp_path / "model-00002-of-00002.safetensors").write_bytes(b"x" * 50)
    art = build_artifact(tmp_path, "safetensors-dir")
    assert art.primary == "."
    assert "config.json" in art.files
    assert art.total_size_bytes == 100


def test_build_artifact_empty_dir_errors(tmp_path: Path):
    with pytest.raises(ValueError, match="no files"):
        build_artifact(tmp_path, "gguf")


def test_build_artifact_safetensors_dir_missing_config_errors(tmp_path: Path):
    (tmp_path / "model.safetensors").write_bytes(b"x")
    with pytest.raises(ValueError, match="config.json"):
        build_artifact(tmp_path, "safetensors-dir")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_model_resolve.py -v`
Expected: FAIL.

- [ ] **Step 3: Append the implementation**

```python
from pathlib import Path  # already imported transitively; ensure present at top

from llm_cli.core.model_registry import Artifact


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
```

(Make sure the `from pathlib import Path` and `from llm_cli.core.model_registry import Artifact` imports are at the top of the file, not inline.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_model_resolve.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/model_resolve.py tests/unit/test_model_resolve.py
git commit -m "feat(model-resolve): build_artifact from download directory"
```

---

## Phase E — Runtime manifest `accepts_formats`

### Task E1: Extend `RuntimeManifest` with `accepts_formats`

**Files:**
- Modify: `src/llm_cli/core/registry.py:27-37`, `140-155`
- Modify: `tests/unit/test_registry.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/unit/test_registry.py (or create if no relevant file exists)
import yaml

from llm_cli.core import registry as _registry


def _write_runtime_manifest(repo, rid, body):
    rt = repo / "runtimes" / rid
    rt.mkdir(parents=True, exist_ok=True)
    (rt / "manifest.yaml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    for n in ("build.sh", "serve.sh", "healthcheck.sh"):
        (rt / n).write_text("#!/usr/bin/env bash\n", encoding="utf-8")


def test_runtime_manifest_accepts_formats_default_empty(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    _write_runtime_manifest(repo, "rt", {"id": "rt", "official": True})
    mf = _registry.get_runtime_manifest(repo, "rt")
    assert mf.accepts_formats == ()


def test_runtime_manifest_accepts_formats_list(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    _write_runtime_manifest(
        repo, "rt", {"id": "rt", "official": True, "accepts_formats": ["gguf"]}
    )
    mf = _registry.get_runtime_manifest(repo, "rt")
    assert mf.accepts_formats == ("gguf",)


def test_runtime_manifest_accepts_formats_invalid_type(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    _write_runtime_manifest(
        repo, "rt", {"id": "rt", "official": True, "accepts_formats": "gguf"}
    )
    with pytest.raises(ValueError, match="accepts_formats must be a list"):
        _registry.get_runtime_manifest(repo, "rt")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_registry.py -v -k accepts_formats`
Expected: FAIL.

- [ ] **Step 3: Extend the dataclass and `_to_manifest`**

In `src/llm_cli/core/registry.py`, add the field to `RuntimeManifest`:

```python
@dataclass(frozen=True)
class RuntimeManifest:
    id: str
    display_name: str
    description: str
    official: bool
    build_schema: list[ParamSpec]
    serve_schema: list[ParamSpec]
    requires: list[dict[str, Any]]
    accepts_formats: tuple[str, ...]
    path: Path
    raw: dict[str, Any]
```

And update `_to_manifest` to parse the field:

```python
def _to_manifest(rec: RuntimeRecord) -> RuntimeManifest:
    data = rec.manifest
    requires = data.get("requires") or []
    if not isinstance(requires, list):
        raise ValueError(f"{rec.id}: requires must be a list")
    raw_formats = data.get("accepts_formats", [])
    if not isinstance(raw_formats, list):
        raise ValueError(f"{rec.id}: accepts_formats must be a list of strings")
    accepts_formats = tuple(str(f) for f in raw_formats)
    return RuntimeManifest(
        id=rec.id,
        display_name=str(data.get("display_name", rec.id)),
        description=str(data.get("description", "")),
        official=bool(data.get("official", False)),
        build_schema=parse_schema(data.get("build") or {}),
        serve_schema=parse_schema(data.get("serve") or {}),
        requires=[r for r in requires if isinstance(r, dict)],
        accepts_formats=accepts_formats,
        path=rec.path,
        raw=data,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_registry.py -v -k accepts_formats`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/registry.py tests/unit/test_registry.py
git commit -m "feat(registry): RuntimeManifest.accepts_formats"
```

---

## Phase F — `${model_path}` template (`core/config_resolve.py`)

### Task F1: Resolve `${model_path}` for a config with `model:` set

**Files:**
- Modify: `src/llm_cli/core/config_resolve.py`
- Modify: `tests/unit/test_config_resolve.py`

- [ ] **Step 1: Append failing tests**

```python
# tests/unit/test_config_resolve.py — append
from pathlib import Path

from llm_cli.core.config_resolve import resolve_config_for_display
from llm_cli.core.model_registry import (
    Artifact,
    HFSource,
    Metadata,
    RegistryEntry,
    upsert_entry,
)
from llm_cli.core.registry import ConfigRecord
from llm_cli.core.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path / "data",
        repo_root=tmp_path / "repo",
        runtimes_dir=tmp_path / "data" / "runtimes",
        models_dir=tmp_path / "data" / "models",
        cache_dir=tmp_path / "data" / "cache",
    )


def _seed_entry(models_dir: Path) -> RegistryEntry:
    e = RegistryEntry(
        id="my-model",
        format="gguf",
        source=HFSource(repo="o/r"),
        artifact=Artifact(primary="weights.gguf", files=("weights.gguf",), total_size_bytes=1),
        metadata=Metadata(display_name="x"),
        installed_at="2026-05-17T00:00:00Z",
    )
    upsert_entry(models_dir, e)
    return e


def test_resolve_model_path_in_serve_params(tmp_path: Path):
    s = _settings(tmp_path)
    s.models_dir.mkdir(parents=True)
    _seed_entry(s.models_dir)
    cfg = ConfigRecord(
        id="c",
        path=tmp_path / "c.yaml",
        data={
            "id": "c",
            "runtime": "rt",
            "model": "my-model",
            "serve": {"host": "127.0.0.1", "port": 8080, "params": {"gguf_path": "${model_path}"}},
        },
    )
    out = resolve_config_for_display(cfg, s)
    expected = (s.models_dir / "my-model" / "weights.gguf").as_posix()
    assert out["serve"]["params"]["gguf_path"] == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config_resolve.py -v -k model_path`
Expected: FAIL.

- [ ] **Step 3: Extend `resolve_config_for_display`**

Rewrite `src/llm_cli/core/config_resolve.py`:

```python
"""Resolve `${...}` placeholders inside config documents."""
from __future__ import annotations

import copy
import re
from typing import Any

from llm_cli.core.model_registry import RegistryEntry, get_entry
from llm_cli.core.params import ParamValidationError, expand_path
from llm_cli.core.registry import ConfigRecord
from llm_cli.core.settings import Settings


_MODEL_TOKEN_RE = re.compile(r"\$\{model_path\}")


def _resolve_model_path_in(value: str, entry: RegistryEntry, settings: Settings) -> str:
    target = (settings.models_dir / entry.id / entry.artifact.primary).as_posix()
    return _MODEL_TOKEN_RE.sub(target, value)


def resolve_config_for_display(cfg: ConfigRecord, settings: Settings) -> dict[str, Any]:
    data: dict[str, Any] = copy.deepcopy(cfg.data)
    model_id = data.get("model") if isinstance(data.get("model"), str) else None
    model_entry: RegistryEntry | None = None
    if model_id:
        model_entry = get_entry(settings.models_dir, model_id)
    serve = data.get("serve")
    if isinstance(serve, dict):
        env = serve.get("env")
        if isinstance(env, dict):
            for key, val in list(env.items()):
                if isinstance(val, str):
                    env[key] = val.replace(
                        "${data_root}", settings.data_root.as_posix()
                    )
        params = serve.get("params")
        if isinstance(params, dict):
            for key, val in list(params.items()):
                if isinstance(val, str):
                    expanded = val
                    if model_entry is not None and "${model_path}" in expanded:
                        expanded = _resolve_model_path_in(expanded, model_entry, settings)
                    try:
                        params[key] = expand_path(expanded, settings)
                    except ParamValidationError:
                        raise
    return data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config_resolve.py -v -k model_path`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/config_resolve.py tests/unit/test_config_resolve.py
git commit -m "feat(config-resolve): expand ${model_path} from registry"
```

---

### Task F2: Error on `${model_path}` without `model:` (strict mode)

**Files:**
- Modify: `src/llm_cli/core/config_resolve.py`
- Modify: `tests/unit/test_config_resolve.py`

- [ ] **Step 1: Append failing test**

```python
def test_resolve_errors_when_model_path_used_without_model(tmp_path: Path):
    s = _settings(tmp_path)
    s.models_dir.mkdir(parents=True)
    cfg = ConfigRecord(
        id="c",
        path=tmp_path / "c.yaml",
        data={
            "id": "c",
            "runtime": "rt",
            "serve": {"host": "127.0.0.1", "port": 8080, "params": {"gguf_path": "${model_path}"}},
        },
    )
    with pytest.raises(ParamValidationError, match=r"\$\{model_path\}"):
        resolve_config_for_display(cfg, s)


def test_resolve_errors_when_model_path_uses_missing_id(tmp_path: Path):
    s = _settings(tmp_path)
    s.models_dir.mkdir(parents=True)
    cfg = ConfigRecord(
        id="c",
        path=tmp_path / "c.yaml",
        data={
            "id": "c",
            "runtime": "rt",
            "model": "ghost-id",
            "serve": {"host": "127.0.0.1", "port": 8080, "params": {"gguf_path": "${model_path}"}},
        },
    )
    with pytest.raises(ParamValidationError, match="ghost-id"):
        resolve_config_for_display(cfg, s)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_config_resolve.py -v -k model_path`
Expected: FAIL.

- [ ] **Step 3: Tighten the resolver**

Inside the params loop, add explicit error checks before substitution:

```python
        if isinstance(params, dict):
            for key, val in list(params.items()):
                if isinstance(val, str):
                    expanded = val
                    if "${model_path}" in expanded:
                        if not model_id:
                            raise ParamValidationError(
                                f"{cfg.id}: serve.params.{key} uses ${{model_path}} "
                                "but no `model:` is set"
                            )
                        if model_entry is None:
                            raise ParamValidationError(
                                f"{cfg.id}: serve.params.{key} references model "
                                f"{model_id!r} which is not in the registry"
                            )
                        expanded = _resolve_model_path_in(expanded, model_entry, settings)
                    try:
                        params[key] = expand_path(expanded, settings)
                    except ParamValidationError:
                        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_config_resolve.py -v -k model_path`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/config_resolve.py tests/unit/test_config_resolve.py
git commit -m "feat(config-resolve): strict errors when ${model_path} can't resolve"
```

---

## Phase G — `validate_config_v2` new model rules

### Task G1: model required ↔ `accepts_formats` non-empty; absent ↔ empty

**Files:**
- Modify: `src/llm_cli/core/registry.py:196-249`
- Modify: `tests/unit/test_registry.py`

- [ ] **Step 1: Append failing tests**

```python
def _write_config(repo, name, body):
    p = repo / "configs" / f"{name}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def test_validate_requires_model_when_accepts_formats_non_empty(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    _write_runtime_manifest(repo, "rt", {"id": "rt", "official": True, "accepts_formats": ["gguf"]})
    _write_config(repo, "c", {
        "id": "c", "runtime": "rt",
        "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
    })
    cfg = next(c for c in _registry.discover_configs(repo) if c.id == "c")
    errs, _ = _registry.validate_config_v2(repo, cfg)
    assert any("model: is required" in e for e in errs)


def test_validate_rejects_model_when_accepts_formats_empty(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    _write_runtime_manifest(repo, "rt", {"id": "rt", "official": True, "accepts_formats": []})
    _write_config(repo, "c", {
        "id": "c", "runtime": "rt", "model": "x",
        "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
    })
    cfg = next(c for c in _registry.discover_configs(repo) if c.id == "c")
    errs, _ = _registry.validate_config_v2(repo, cfg)
    assert any("must not set `model:`" in e for e in errs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_registry.py -v -k validate`
Expected: FAIL.

- [ ] **Step 3: Replace `validate_config_v2`**

In `src/llm_cli/core/registry.py`, replace the function. Also remove the `md_id` early-return-string-check at the top (the new logic handles missing/extra model uniformly):

```python
def validate_config_v2(repo: Path, cfg: ConfigRecord) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors fail validation; warnings are advisory."""
    errs: list[str] = []
    warnings: list[str] = []

    rt_id = cfg.data.get("runtime")
    if not isinstance(rt_id, str):
        errs.append(f"{cfg.id}: runtime must be a string")
        return errs, warnings

    rt = get_runtime(repo, rt_id)
    rt_manifest = _to_manifest(rt) if rt is not None else None
    if rt is None:
        errs.append(f"{cfg.id}: unknown runtime {rt_id!r}")
    else:
        errs.extend(validate_runtime_layout(rt))

    md_id_raw = cfg.data.get("model")
    md_id: str | None = md_id_raw if isinstance(md_id_raw, str) else None
    if rt_manifest is not None:
        if rt_manifest.accepts_formats and md_id is None:
            errs.append(
                f"{cfg.id}: model: is required when runtime {rt_id!r} declares "
                f"accepts_formats={list(rt_manifest.accepts_formats)}"
            )
        if not rt_manifest.accepts_formats and md_id is not None:
            errs.append(
                f"{cfg.id}: runtime {rt_id!r} has empty accepts_formats; "
                f"config must not set `model:`"
            )

    serve = cfg.data.get("serve")
    if not isinstance(serve, dict):
        errs.append(f"{cfg.id}: serve must be a mapping")
    else:
        for key in ("host", "port"):
            if key not in serve:
                errs.append(f"{cfg.id}: serve.{key} is required")
        if rt_manifest is not None:
            params = serve.get("params", {})
            if not isinstance(params, dict):
                errs.append(f"{cfg.id}: serve.params must be a mapping")
            else:
                _, param_errs = validate_params(rt_manifest.serve_schema, params)
                errs.extend(f"{cfg.id}: {e}" for e in param_errs)

    ready = cfg.data.get("readiness")
    if ready is not None and not isinstance(ready, dict):
        errs.append(f"{cfg.id}: readiness must be a mapping when present")

    yaml_id = cfg.data.get("id")
    if yaml_id is not None and yaml_id != cfg.id:
        errs.append(f"{cfg.id}: file id {yaml_id!r} does not match filename/config id")

    try:
        settings = resolve(load_settings())
    except (MissingSettingError, UnknownSettingError, ValueError) as exc:
        errs.append(f"settings: {exc}")
        return errs, warnings

    if rt_manifest is not None and not is_installed(settings.runtimes_dir, rt_id):
        warnings.append(
            f"{cfg.id}: runtime {rt_id!r} is not installed; "
            f"run `llm runtime install {rt_id}` before `llm serve`."
        )

    return errs, warnings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_registry.py -v -k validate`
Expected: PASS for the two new tests. Pre-existing tests that referenced `validate_model_layout` or assumed `md_id` was always required will fail; we fix them in G2.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/core/registry.py tests/unit/test_registry.py
git commit -m "feat(validate): enforce model presence rule via accepts_formats"
```

---

### Task G2: model-id must resolve in registry; format compat

**Files:**
- Modify: `src/llm_cli/core/registry.py` (extend `validate_config_v2`)
- Modify: `tests/unit/test_registry.py`

- [ ] **Step 1: Append failing tests**

```python
def test_validate_errors_on_unknown_model(tmp_path, monkeypatch):
    repo = tmp_path / "repo"; repo.mkdir()
    _write_runtime_manifest(repo, "rt", {"id": "rt", "official": True, "accepts_formats": ["gguf"]})
    _write_config(repo, "c", {
        "id": "c", "runtime": "rt", "model": "ghost",
        "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
    })
    save = _registry.load_settings
    # ensure load_settings resolves to tmp_path/data
    from llm_cli.core.settings import save_settings as ss
    ss({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    cfg = next(c for c in _registry.discover_configs(repo) if c.id == "c")
    errs, _ = _registry.validate_config_v2(repo, cfg)
    assert any("unknown model 'ghost'" in e for e in errs)


def test_validate_errors_on_format_mismatch(tmp_path):
    from llm_cli.core.model_registry import (
        Artifact, HFSource, Metadata, RegistryEntry, upsert_entry,
    )
    from llm_cli.core.settings import save_settings as ss

    repo = tmp_path / "repo"; repo.mkdir()
    _write_runtime_manifest(
        repo, "rt", {"id": "rt", "official": True, "accepts_formats": ["safetensors-dir"]}
    )
    _write_config(repo, "c", {
        "id": "c", "runtime": "rt", "model": "g",
        "serve": {"host": "127.0.0.1", "port": 8080, "params": {}},
    })
    ss({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    upsert_entry(
        tmp_path / "data" / "models",
        RegistryEntry(
            id="g",
            format="gguf",
            source=HFSource(repo="o/r"),
            artifact=Artifact(primary="x.gguf", files=("x.gguf",), total_size_bytes=1),
            metadata=Metadata(),
            installed_at="2026-05-17T00:00:00Z",
        ),
    )
    cfg = next(c for c in _registry.discover_configs(repo) if c.id == "c")
    errs, _ = _registry.validate_config_v2(repo, cfg)
    assert any("format" in e and "gguf" in e for e in errs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_registry.py -v -k "unknown_model or format_mismatch"`
Expected: FAIL.

- [ ] **Step 3: Extend `validate_config_v2`**

Insert before the early `settings` resolution try block:

```python
    # Model lookup happens after we know we need one and have settings available.
```

Replace the settings block so model checks run after settings are resolved:

```python
    try:
        settings = resolve(load_settings())
    except (MissingSettingError, UnknownSettingError, ValueError) as exc:
        errs.append(f"settings: {exc}")
        return errs, warnings

    if rt_manifest is not None and md_id is not None:
        from llm_cli.core.model_registry import get_entry as _get_model
        model_entry = _get_model(settings.models_dir, md_id)
        if model_entry is None:
            errs.append(f"{cfg.id}: unknown model {md_id!r}")
        else:
            if model_entry.format not in rt_manifest.accepts_formats:
                errs.append(
                    f"{cfg.id}: model {md_id!r} has format "
                    f"{model_entry.format!r}; runtime {rt_id!r} accepts "
                    f"{list(rt_manifest.accepts_formats)}"
                )
            primary_path = settings.models_dir / md_id / model_entry.artifact.primary
            if not primary_path.exists():
                warnings.append(
                    f"{cfg.id}: model {md_id!r} primary path missing on disk "
                    f"({primary_path}); run `llm model pull {md_id}`."
                )

    if rt_manifest is not None and not is_installed(settings.runtimes_dir, rt_id):
        warnings.append(
            f"{cfg.id}: runtime {rt_id!r} is not installed; "
            f"run `llm runtime install {rt_id}` before `llm serve`."
        )

    return errs, warnings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_registry.py -v -k "unknown_model or format_mismatch"`
Expected: PASS.

- [ ] **Step 5: Drop dead model-discovery code in `core/registry.py`**

Delete the following symbols (and their imports if newly orphaned):
- `ModelRecord` dataclass
- `discover_models`
- `get_model`
- `validate_model_layout`

Run: `pytest tests -q`
Expected: PASS. If anything still imports the deleted symbols, fix it (see Phase H).

- [ ] **Step 6: Commit**

```bash
git add src/llm_cli/core/registry.py tests/unit/test_registry.py
git commit -m "feat(validate): registry-backed model lookup + format compat; drop model dir discovery"
```

---

## Phase H — Rewrite `commands/model_cmd.py`

### Task H1: `list` and `info` against the registry

**Files:**
- Modify: `src/llm_cli/commands/model_cmd.py` (full rewrite — see below)
- Modify: `tests/integration/test_cli_model.py` (full rewrite — see below)

- [ ] **Step 1: Replace test file with registry-backed scenarios**

```python
# tests/integration/test_cli_model.py
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from llm_cli.core.model_registry import (
    Artifact, HFSource, Metadata, RegistryEntry, upsert_entry,
)
from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def _seed_entry(models_dir: Path, mid: str = "qwen-qwen2.5-7b-instruct") -> RegistryEntry:
    e = RegistryEntry(
        id=mid,
        format="safetensors-dir",
        source=HFSource(repo="Qwen/Qwen2.5-7B-Instruct"),
        artifact=Artifact(primary=".", files=("config.json",), total_size_bytes=42),
        metadata=Metadata(display_name="Qwen 2.5", license="apache-2.0"),
        installed_at="2026-05-17T00:00:00Z",
    )
    upsert_entry(models_dir, e)
    return e


def _configure(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"; repo.mkdir()
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    return tmp_path / "data" / "models"


def test_model_list_empty(tmp_path: Path):
    _configure(tmp_path)
    result = runner.invoke(app, ["model", "list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "no models registered" in result.stdout.lower() or "Models" in result.stdout


def test_model_list_shows_registered_entry(tmp_path: Path):
    models_dir = _configure(tmp_path)
    _seed_entry(models_dir)
    result = runner.invoke(app, ["model", "list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "qwen-qwen2.5-7b-instruct" in result.stdout
    assert "safetensors-dir" in result.stdout


def test_model_info(tmp_path: Path):
    models_dir = _configure(tmp_path)
    _seed_entry(models_dir)
    result = runner.invoke(app, ["model", "info", "qwen-qwen2.5-7b-instruct"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "Qwen/Qwen2.5-7B-Instruct" in result.stdout
    assert "apache-2.0" in result.stdout


def test_model_info_missing(tmp_path: Path):
    _configure(tmp_path)
    result = runner.invoke(app, ["model", "info", "ghost"], catch_exceptions=False)
    assert result.exit_code == 1
    assert "unknown model" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_cli_model.py -v`
Expected: FAIL (old command surface still in place).

- [ ] **Step 3: Rewrite `model_cmd.py` (list + info only for this task)**

```python
# src/llm_cli/commands/model_cmd.py
"""`llm model` — list/info/pull/add/uninstall against $LLM_MODELS/registry.json."""
from __future__ import annotations

import json as _json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from llm_cli.core.model_registry import (
    get_entry, load_registry,
)
from llm_cli.core.settings import load_settings, resolve

console = Console()
model_app = typer.Typer(help="Manage models (list/info/pull/add/uninstall).")


def _models_dir() -> Path:
    return resolve(load_settings()).models_dir


@model_app.command("list", help="List models registered in $LLM_MODELS/registry.json.")
def model_list(as_json: bool = typer.Option(False, "--json")) -> None:
    models_dir = _models_dir()
    reg = load_registry(models_dir)
    if as_json:
        typer.echo(_json.dumps({k: vars(v) for k, v in reg.items()}, default=str, indent=2))
        return
    if not reg:
        console.print("[dim]no models registered[/dim]")
        return
    table = Table(title="Models")
    table.add_column("ID")
    table.add_column("Format")
    table.add_column("Source")
    table.add_column("Size")
    table.add_column("Present")
    for mid, e in sorted(reg.items()):
        present = (models_dir / mid / e.artifact.primary).exists()
        table.add_row(
            mid,
            e.format,
            e.source.kind,
            f"{e.artifact.total_size_bytes}",
            "yes" if present else "[red]no[/red]",
        )
    console.print(table)


@model_app.command("info", help="Show a registered model's full entry.")
def model_info(model_id: str = typer.Argument(...), as_json: bool = typer.Option(False, "--json")) -> None:
    models_dir = _models_dir()
    e = get_entry(models_dir, model_id)
    if e is None:
        console.print(f"[red]error:[/red] unknown model {model_id!r}")
        raise typer.Exit(code=1)
    if as_json:
        from llm_cli.core.model_registry import encode_entry
        typer.echo(_json.dumps({model_id: encode_entry(e)}, indent=2))
        return
    console.print(f"[bold]{e.id}[/bold] — {e.metadata.display_name or '(no display name)'}")
    console.print(f"  format: {e.format}")
    console.print(f"  source.kind: {e.source.kind}")
    if hasattr(e.source, "repo"):
        console.print(f"  source.repo: {e.source.repo}@{e.source.revision}")
        if e.source.include:
            console.print(f"  source.include: {list(e.source.include)}")
    if hasattr(e.source, "original_path"):
        console.print(f"  source.original_path: {e.source.original_path}")
    console.print(f"  artifact.primary: {e.artifact.primary}")
    console.print(f"  artifact.files: {len(e.artifact.files)} file(s), {e.artifact.total_size_bytes} bytes")
    if e.metadata.license:
        console.print(f"  metadata.license: {e.metadata.license}")
    if e.metadata.ctx_length:
        console.print(f"  metadata.ctx_length: {e.metadata.ctx_length}")
    console.print(f"  installed_at: {e.installed_at}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_cli_model.py -v -k "list or info"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/model_cmd.py tests/integration/test_cli_model.py
git commit -m "feat(model-cmd): registry-backed list and info"
```

---

### Task H2: `pull <url>` happy path (HF client + `hf download` patched)

**Files:**
- Modify: `src/llm_cli/commands/model_cmd.py`
- Modify: `tests/integration/test_cli_model.py`

- [ ] **Step 1: Append failing test**

```python
from unittest.mock import patch

from llm_cli.core.hf_client import HFRepoInfo, HFSibling


def _fake_repo_info() -> HFRepoInfo:
    return HFRepoInfo(
        repo="unsloth/Qwen3.6-235B-A22B-GGUF",
        revision="main",
        sha="abc",
        license="apache-2.0",
        siblings=[
            HFSibling(
                rfilename="Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00002.gguf",
                size=100,
                lfs_sha256="111",
            ),
            HFSibling(
                rfilename="Qwen3.6-235B-A22B-UD-Q4_K_XL-00002-of-00002.gguf",
                size=200,
                lfs_sha256="222",
            ),
            HFSibling(rfilename="README.md", size=10, lfs_sha256=None),
        ],
    )


def _fake_download(repo, revision, include, exclude, target_dir):
    for name in (
        "Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00002.gguf",
        "Qwen3.6-235B-A22B-UD-Q4_K_XL-00002-of-00002.gguf",
    ):
        p = Path(target_dir) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * (100 if "00001" in name else 200))
    return 0


def test_model_pull_url_happy_path(tmp_path: Path):
    models_dir = _configure(tmp_path)
    url = (
        "https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF/blob/main/"
        "Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00002.gguf"
    )
    with patch(
        "llm_cli.commands.model_cmd.fetch_repo_revision", return_value=_fake_repo_info()
    ), patch(
        "llm_cli.commands.model_cmd.hf_download", side_effect=_fake_download
    ):
        result = runner.invoke(app, ["model", "pull", url], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout
    from llm_cli.core.model_registry import get_entry
    e = get_entry(models_dir, "unsloth-qwen3.6-235b-a22b__ud-q4-k-xl")
    assert e is not None
    assert e.format == "gguf"
    assert e.source.kind == "hf"
    assert e.source.repo == "unsloth/Qwen3.6-235B-A22B-GGUF"
    assert e.artifact.primary == "Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00002.gguf"
    assert len(e.artifact.files) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_cli_model.py -v -k pull_url_happy`
Expected: FAIL (no `pull` yet).

- [ ] **Step 3: Add `pull` + `hf_download` adapter**

Append to `src/llm_cli/commands/model_cmd.py`:

```python
from datetime import datetime, timezone
from subprocess import run as _subprocess_run
from typing import Optional

from llm_cli.core.hf_client import HFApiError, HFRepoInfo, fetch_repo_revision
from llm_cli.core.hf_url import HFUrlError, parse_hf_url
from llm_cli.core.model_registry import (
    Artifact, HFSource, Metadata, RegistryEntry, upsert_entry,
)
from llm_cli.core.model_resolve import (
    FormatInferenceError, build_artifact, derive_model_id, infer_format,
)


def hf_download(
    repo: str,
    revision: str,
    include: list[str],
    exclude: list[str],
    target_dir: Path,
) -> int:
    """Invoke `hf download` as a subprocess. Patched in tests."""
    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["hf", "download", repo, "--revision", revision, "--local-dir", str(target_dir)]
    for pat in include:
        cmd += ["--include", pat]
    for pat in exclude:
        cmd += ["--exclude", pat]
    result = _subprocess_run(cmd, check=False)
    return result.returncode


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _verify_sha256(target_dir: Path, expected: dict[str, str]) -> list[str]:
    import hashlib
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


@model_app.command("pull", help="Pull a model from HF (URL) or re-pull an existing id.")
def model_pull(
    target: str = typer.Argument(..., help="HF URL or registered model id."),
    fmt: Optional[str] = typer.Option(
        None, "--format", help="Override format (gguf|safetensors-dir)."
    ),
    include: list[str] = typer.Option([], "--include", help="hf download --include pattern (repeatable)."),
    exclude: list[str] = typer.Option([], "--exclude", help="hf download --exclude pattern (repeatable)."),
    id_override: Optional[str] = typer.Option(None, "--id", help="Override derived model id."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing entry."),
) -> None:
    models_dir = _models_dir()

    try:
        parsed = parse_hf_url(target)
    except HFUrlError:
        parsed = None

    if parsed is not None:
        try:
            info = fetch_repo_revision(parsed.repo, revision=parsed.revision)
        except HFApiError as exc:
            console.print(f"[red]error:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        try:
            inferred = (
                infer_format(parsed, [s.rfilename for s in info.siblings])
                if not fmt or not include
                else None
            )
        except FormatInferenceError as exc:
            console.print(f"[red]error:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        chosen_format = fmt or (inferred.format if inferred else "")
        chosen_include = list(include or (inferred.include if inferred else ()))
        chosen_exclude = list(exclude)

        if not chosen_format:
            console.print("[red]error:[/red] could not determine format; pass --format")
            raise typer.Exit(code=1)

        mid = id_override or derive_model_id(parsed)
        target_dir = models_dir / mid
        if get_entry(models_dir, mid) is not None and not force:
            console.print(
                f"[red]error:[/red] {mid!r} already registered; "
                f"use `--force` to overwrite or `llm model uninstall {mid}` first"
            )
            raise typer.Exit(code=1)

        rc = hf_download(parsed.repo, parsed.revision, chosen_include, chosen_exclude, target_dir)
        if rc != 0:
            console.print(f"[red]error:[/red] hf download failed (exit {rc})")
            raise typer.Exit(code=rc)

        artifact = build_artifact(target_dir, chosen_format)
        sha_map = {
            s.rfilename: s.lfs_sha256
            for s in info.siblings
            if s.lfs_sha256 and s.rfilename in artifact.files
        }
        bad = _verify_sha256(target_dir, sha_map)
        if bad:
            for line in bad:
                console.print(f"[red]sha256:[/red] {line}")
            raise typer.Exit(code=1)
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
            installed_at=_utc_now_iso(),
        )
        upsert_entry(models_dir, entry)
        console.print(f"[green]registered[/green] {mid}")
        console.print(f"  next: edit your config to use `model: {mid}` and `gguf_path: ${{model_path}}`")
        return

    # Treat target as an existing id.
    existing = get_entry(models_dir, target)
    if existing is None:
        console.print(
            f"[red]error:[/red] {target!r} is neither a valid HF URL nor a registered model id"
        )
        raise typer.Exit(code=1)
    if not isinstance(existing.source, HFSource):
        console.print(
            f"[red]error:[/red] {target!r} is a local-source model; re-pull only applies to HF entries"
        )
        raise typer.Exit(code=1)
    target_dir = models_dir / existing.id
    rc = hf_download(
        existing.source.repo,
        existing.source.revision,
        list(existing.source.include),
        list(existing.source.exclude),
        target_dir,
    )
    if rc != 0:
        console.print(f"[red]error:[/red] hf download failed (exit {rc})")
        raise typer.Exit(code=rc)
    artifact = build_artifact(target_dir, existing.format)
    refreshed = RegistryEntry(
        id=existing.id,
        format=existing.format,
        source=existing.source,
        artifact=Artifact(
            primary=artifact.primary,
            files=artifact.files,
            total_size_bytes=artifact.total_size_bytes,
            sha256=existing.artifact.sha256,
        ),
        metadata=existing.metadata,
        installed_at=_utc_now_iso(),
    )
    upsert_entry(models_dir, refreshed)
    console.print(f"[green]refreshed[/green] {existing.id}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_cli_model.py -v -k pull_url_happy`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/model_cmd.py tests/integration/test_cli_model.py
git commit -m "feat(model-cmd): pull <hf-url> resolves, downloads, verifies, registers"
```

---

### Task H3: `pull <existing-id>` refresh

**Files:**
- Modify: `tests/integration/test_cli_model.py`

- [ ] **Step 1: Append failing test**

```python
def test_model_pull_existing_id_refreshes(tmp_path: Path):
    models_dir = _configure(tmp_path)
    # Seed an HF entry with one shard already on disk.
    (models_dir / "qwen-q__q4").mkdir(parents=True)
    (models_dir / "qwen-q__q4" / "x.gguf").write_bytes(b"x" * 50)
    from llm_cli.core.model_registry import (
        Artifact, HFSource, Metadata, RegistryEntry, upsert_entry,
    )
    upsert_entry(
        models_dir,
        RegistryEntry(
            id="qwen-q__q4",
            format="gguf",
            source=HFSource(repo="qwen/Q", revision="main", include=("*Q4*",)),
            artifact=Artifact(primary="x.gguf", files=("x.gguf",), total_size_bytes=50),
            metadata=Metadata(display_name="qwen/Q"),
            installed_at="2026-01-01T00:00:00Z",
        ),
    )

    def fake_dl(repo, revision, include, exclude, target_dir):
        # simulate a second-run no-op (file already there)
        return 0

    with patch("llm_cli.commands.model_cmd.hf_download", side_effect=fake_dl):
        result = runner.invoke(app, ["model", "pull", "qwen-q__q4"], catch_exceptions=False)
    assert result.exit_code == 0
    from llm_cli.core.model_registry import get_entry
    e = get_entry(models_dir, "qwen-q__q4")
    assert e.installed_at != "2026-01-01T00:00:00Z"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/integration/test_cli_model.py -v -k pull_existing_id`
Expected: PASS (implementation already in H2).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_cli_model.py
git commit -m "test(model-cmd): pull <id> refreshes installed_at"
```

---

### Task H4: `pull <url>` ambiguous → exit 1, registry unchanged

**Files:**
- Modify: `tests/integration/test_cli_model.py`

- [ ] **Step 1: Append failing test**

```python
def test_model_pull_ambiguous_url_errors(tmp_path: Path):
    models_dir = _configure(tmp_path)
    url = "https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF"
    multi_quant = HFRepoInfo(
        repo="unsloth/Qwen3.6-235B-A22B-GGUF",
        revision="main",
        sha="x",
        license=None,
        siblings=[
            HFSibling(rfilename="model-Q4_K_M.gguf", size=10, lfs_sha256=None),
            HFSibling(rfilename="model-Q5_K_M.gguf", size=10, lfs_sha256=None),
        ],
    )
    with patch(
        "llm_cli.commands.model_cmd.fetch_repo_revision", return_value=multi_quant
    ), patch(
        "llm_cli.commands.model_cmd.hf_download"
    ) as mock_dl:
        result = runner.invoke(app, ["model", "pull", url], catch_exceptions=False)
    assert result.exit_code == 1
    assert "--include" in result.stdout
    assert not mock_dl.called
    from llm_cli.core.model_registry import load_registry
    assert load_registry(models_dir) == {}
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/integration/test_cli_model.py -v -k ambiguous_url`
Expected: PASS (implementation already raises before download).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_cli_model.py
git commit -m "test(model-cmd): ambiguous URL exits 1 and leaves registry untouched"
```

---

### Task H5: `add <id> <path>` for local weights

**Files:**
- Modify: `src/llm_cli/commands/model_cmd.py`
- Modify: `tests/integration/test_cli_model.py`

- [ ] **Step 1: Append failing tests**

```python
def test_model_add_safetensors_dir(tmp_path: Path):
    models_dir = _configure(tmp_path)
    src = tmp_path / "src"; src.mkdir()
    (src / "config.json").write_text("{}", encoding="utf-8")
    (src / "tokenizer.json").write_text("{}", encoding="utf-8")
    (src / "model.safetensors").write_bytes(b"x" * 32)
    result = runner.invoke(
        app, ["model", "add", "my-ft", str(src), "--format", "safetensors-dir"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout
    target = models_dir / "my-ft"
    assert (target / "config.json").exists()
    from llm_cli.core.model_registry import get_entry
    e = get_entry(models_dir, "my-ft")
    assert e.format == "safetensors-dir"
    assert e.source.kind == "local"
    assert e.artifact.primary == "."


def test_model_add_gguf_single_file(tmp_path: Path):
    models_dir = _configure(tmp_path)
    f = tmp_path / "weights.gguf"; f.write_bytes(b"x" * 16)
    result = runner.invoke(
        app, ["model", "add", "single-q", str(f), "--format", "gguf"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout
    target = models_dir / "single-q"
    assert (target / "weights.gguf").exists()
    from llm_cli.core.model_registry import get_entry
    e = get_entry(models_dir, "single-q")
    assert e.artifact.primary == "weights.gguf"


def test_model_add_rejects_safetensors_dir_without_config(tmp_path: Path):
    _configure(tmp_path)
    src = tmp_path / "src"; src.mkdir()
    (src / "model.safetensors").write_bytes(b"x")
    result = runner.invoke(
        app, ["model", "add", "bad", str(src), "--format", "safetensors-dir"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "config.json" in result.stdout


def test_model_add_rejects_missing_path(tmp_path: Path):
    _configure(tmp_path)
    result = runner.invoke(
        app, ["model", "add", "x", str(tmp_path / "nope"), "--format", "gguf"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "does not exist" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_cli_model.py -v -k model_add`
Expected: FAIL.

- [ ] **Step 3: Add `model_add` to `model_cmd.py`**

Append to `model_cmd.py`:

```python
import os
import shutil

from llm_cli.core.model_registry import LocalSource


def _symlink_or_copy(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    try:
        os.symlink(src, dst)
    except (OSError, NotImplementedError):
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        console.print(f"[yellow][info][/yellow] symlink unavailable; copied {src} → {dst}")


@model_app.command("add", help="Register pre-existing local weights under a model id.")
def model_add(
    model_id: str = typer.Argument(...),
    path: Path = typer.Argument(...),
    fmt: str = typer.Option(..., "--format", help="gguf | safetensors-dir"),
) -> None:
    if not path.exists():
        console.print(f"[red]error:[/red] path does not exist: {path}")
        raise typer.Exit(code=1)
    models_dir = _models_dir()
    target = models_dir / model_id
    target.mkdir(parents=True, exist_ok=True)

    if fmt == "gguf":
        if path.is_file():
            _symlink_or_copy(path, target / path.name)
        elif path.is_dir():
            for entry in sorted(path.iterdir()):
                if entry.suffix.lower() == ".gguf":
                    _symlink_or_copy(entry, target / entry.name)
        else:
            console.print(f"[red]error:[/red] unsupported gguf path: {path}")
            raise typer.Exit(code=1)
    elif fmt == "safetensors-dir":
        if not path.is_dir():
            console.print(f"[red]error:[/red] safetensors-dir requires a directory: {path}")
            raise typer.Exit(code=1)
        if not (path / "config.json").is_file():
            console.print(f"[red]error:[/red] safetensors-dir missing config.json: {path}")
            raise typer.Exit(code=1)
        for entry in sorted(path.iterdir()):
            _symlink_or_copy(entry, target / entry.name)
    else:
        console.print(f"[red]error:[/red] unknown --format {fmt!r}")
        raise typer.Exit(code=1)

    try:
        artifact = build_artifact(target, fmt)
    except ValueError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    entry = RegistryEntry(
        id=model_id,
        format=fmt,
        source=LocalSource(original_path=str(path.resolve())),
        artifact=artifact,
        metadata=Metadata(display_name=model_id),
        installed_at=_utc_now_iso(),
    )
    upsert_entry(models_dir, entry)
    console.print(f"[green]registered[/green] {model_id}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_cli_model.py -v -k model_add`
Expected: PASS. (On Windows where symlinks may be disallowed for non-admins, the copy fallback engages and the test still passes — `(target / 'config.json').exists()` is true either way.)

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/model_cmd.py tests/integration/test_cli_model.py
git commit -m "feat(model-cmd): `add <id> <path>` for local weights with symlink default"
```

---

### Task H6: `uninstall <id>` with optional `--purge`

**Files:**
- Modify: `src/llm_cli/commands/model_cmd.py`
- Modify: `tests/integration/test_cli_model.py`

- [ ] **Step 1: Append failing tests**

```python
def test_model_uninstall_removes_registry_row(tmp_path: Path):
    models_dir = _configure(tmp_path)
    _seed_entry(models_dir, "x")
    (models_dir / "x").mkdir(exist_ok=True)
    (models_dir / "x" / "weights.gguf").write_bytes(b"x")
    result = runner.invoke(app, ["model", "uninstall", "x", "--yes"], catch_exceptions=False)
    assert result.exit_code == 0
    from llm_cli.core.model_registry import get_entry
    assert get_entry(models_dir, "x") is None
    # files NOT removed without --purge
    assert (models_dir / "x" / "weights.gguf").exists()


def test_model_uninstall_with_purge_removes_files(tmp_path: Path):
    models_dir = _configure(tmp_path)
    _seed_entry(models_dir, "x")
    (models_dir / "x").mkdir(exist_ok=True)
    (models_dir / "x" / "weights.gguf").write_bytes(b"x")
    result = runner.invoke(
        app, ["model", "uninstall", "x", "--purge", "--yes"], catch_exceptions=False
    )
    assert result.exit_code == 0
    assert not (models_dir / "x").exists()


def test_model_uninstall_unknown_id_errors(tmp_path: Path):
    _configure(tmp_path)
    result = runner.invoke(
        app, ["model", "uninstall", "ghost", "--yes"], catch_exceptions=False
    )
    assert result.exit_code == 1
    assert "unknown model" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_cli_model.py -v -k uninstall`
Expected: FAIL.

- [ ] **Step 3: Add `model_uninstall`**

Append to `model_cmd.py`:

```python
from llm_cli.core.model_registry import remove_entry


@model_app.command("uninstall", help="Remove a registered model.")
def model_uninstall(
    model_id: str = typer.Argument(...),
    purge: bool = typer.Option(False, "--purge", help="Also delete $LLM_MODELS/<id>/."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
) -> None:
    models_dir = _models_dir()
    if get_entry(models_dir, model_id) is None:
        console.print(f"[red]error:[/red] unknown model {model_id!r}")
        raise typer.Exit(code=1)
    if not yes:
        msg = (
            f"Purge {models_dir / model_id}? (removes weights/symlinks)"
            if purge else f"Remove registry entry {model_id!r}?"
        )
        if not typer.confirm(msg, default=False):
            console.print("aborted")
            raise typer.Exit(code=1)
    remove_entry(models_dir, model_id)
    if purge:
        target = models_dir / model_id
        if target.exists():
            import shutil
            shutil.rmtree(target)
    console.print(f"[green]uninstalled[/green] {model_id}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_cli_model.py -v -k uninstall`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/llm_cli/commands/model_cmd.py tests/integration/test_cli_model.py
git commit -m "feat(model-cmd): uninstall with optional --purge"
```

---

## Phase I — Runtime manifests get `accepts_formats`

### Task I1: `llamacpp` and `stub-runtime` manifests

**Files:**
- Modify: `runtimes/llamacpp/manifest.yaml`
- Modify: `runtimes/stub-runtime/manifest.yaml`

- [ ] **Step 1: Edit `runtimes/llamacpp/manifest.yaml`**

Add at the top level (anywhere after `id:`, before `requires:`):

```yaml
accepts_formats: [gguf]
```

- [ ] **Step 2: Edit `runtimes/stub-runtime/manifest.yaml`**

Add at the top level:

```yaml
accepts_formats: []
```

- [ ] **Step 3: Verify**

Run: `pytest tests -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add runtimes/llamacpp/manifest.yaml runtimes/stub-runtime/manifest.yaml
git commit -m "feat(runtimes): declare accepts_formats on llamacpp and stub-runtime"
```

---

## Phase J — Delete legacy `models/` + migrate stub config

### Task J1: Delete tracked `models/stub-model/`

**Files:**
- Delete: `models/stub-model/manifest.yaml`
- Delete: `models/stub-model/pull.sh`
- Delete: `models/stub-model/README.md`

- [ ] **Step 1: Remove the directory**

```bash
git rm -r models/stub-model
```

- [ ] **Step 2: Confirm pytest**

Run: `pytest tests -q`
Expected: PASS (tests that depended on the dir were rewritten in Phase H; if any remain, fix them now).

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove tracked models/stub-model (replaced by registry)"
```

---

### Task J2: Rename stub config; drop `model:`

**Files:**
- Delete: `configs/stub-runtime__stub-model__default.yaml`
- Create: `configs/stub-runtime__default.yaml`

- [ ] **Step 1: Write the new config**

```yaml
# configs/stub-runtime__default.yaml
id: stub-runtime__default
runtime: stub-runtime
serve:
  host: 127.0.0.1
  port: 18080
  params: {}
readiness:
  timeout_seconds: 120
```

- [ ] **Step 2: Remove the old one**

```bash
git rm configs/stub-runtime__stub-model__default.yaml
```

- [ ] **Step 3: Update any test fixtures or asserts that referenced the old config id**

Run: `pytest tests -q` and fix any remaining references that fail (likely in `test_cli_lifecycle.py` / `test_cli_systemd.py` / `test_cli_serve.py`). The new id is `stub-runtime__default`.

- [ ] **Step 4: Commit**

```bash
git add configs/stub-runtime__default.yaml
git commit -m "refactor(configs): stub-runtime config no longer needs a model"
```

---

## Phase K — Docs sweep

### Task K1: Rewrite `docs/add-a-model.md`

**Files:**
- Modify: `docs/add-a-model.md`

- [ ] **Step 1: Replace the file**

```markdown
# HOWTO: add a model

Models live in a per-machine registry at `$LLM_MODELS/registry.json` (not in git). You don't write any YAML or scripts by hand; the CLI manages everything.

## Pull from Hugging Face (one shot)

For a single GGUF quant (URL points at the file):

```bash
llm model pull \
  https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF/blob/main/Qwen3.6-235B-A22B-UD-Q4_K_XL-00001-of-00010.gguf
```

For a whole safetensors-style repo:

```bash
llm model pull https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
```

If the repo is ambiguous (mixed formats, multiple GGUF quants) `pull` will refuse and tell you to add `--format` and/or `--include`:

```bash
llm model pull https://huggingface.co/unsloth/Qwen3.6-235B-A22B-GGUF \
  --include "*UD-Q4_K_XL*"
```

## Register local weights

```bash
llm model add my-finetune /home/me/llm/staging/my-finetune --format safetensors-dir
llm model add q4-local   /home/me/llm/staging/q4.gguf      --format gguf
```

Files are symlinked into `$LLM_MODELS/<id>/` (copied as a fallback if the FS rejects symlinks). The originals are untouched.

## Reference models in configs

Configs reference a model by id and use the `${model_path}` template inside `serve.params`:

```yaml
runtime: llamacpp
model: unsloth-qwen3.6-235b-a22b__ud-q4-k-xl
serve:
  host: 127.0.0.1
  port: 8080
  params:
    gguf_path: "${model_path}"
    n_gpu_layers: -1
    ctx: 8192
```

`llm config validate` enforces:
- `model:` is required when the runtime declares `accepts_formats: [...]` (non-empty).
- `model:` must be absent when the runtime declares `accepts_formats: []`.
- The model's `format` must be in the runtime's `accepts_formats`.

## Verify and uninstall

```bash
llm model list
llm model info <id>
llm model uninstall <id> [--purge]
```

`--purge` removes the symlinked / downloaded files under `$LLM_MODELS/<id>/` in addition to the registry row.

## See also

- [`runtime-lifecycle.md`](runtime-lifecycle.md)
- [Models registry redesign spec](superpowers/specs/2026-05-17-models-registry-redesign.md)
```

- [ ] **Step 2: Commit**

```bash
git add docs/add-a-model.md
git commit -m "docs(add-a-model): rewrite for registry + pull/add commands"
```

---

### Task K2: Update `docs/repo-conventions.md`

**Files:**
- Modify: `docs/repo-conventions.md`

- [ ] **Step 1: Edit the directory layout section**

Remove the `models/{id}/` row from the layout table. Add a row noting that the per-machine registry lives at `$LLM_MODELS/registry.json` (data root, not in git).

- [ ] **Step 2: Commit**

```bash
git add docs/repo-conventions.md
git commit -m "docs(conventions): models now live in registry.json under data root"
```

---

### Task K3: Update `README.md` CLI table

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the model verbs row in the CLI table**

Replace the existing `llm model list/info/pull` rows with:

```markdown
| `llm model list` | List models in `$LLM_MODELS/registry.json` |
| `llm model info <id>` | Show full registry entry |
| `llm model pull <url-or-id>` | Pull from HF (URL) or refresh an existing id; `--format`, `--include`, `--exclude`, `--id`, `--force` |
| `llm model add <id> <path> --format <fmt>` | Register local weights via symlink |
| `llm model uninstall <id> [--purge]` | Remove a model (and optionally its files) |
```

Update the Getting Started snippet so the model step reads:

```bash
llm model pull https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): update model CLI section for registry + pull from URL"
```

---

## Phase Z — Final sweep

### Task Z1: Full test suite + manual smoke

**Files:** all

- [ ] **Step 1: Run the whole suite**

Run: `pytest tests -q`
Expected: PASS (skips for Windows-only / systemd-only are fine).

- [ ] **Step 2: Sanity-test the CLI manually in WSL**

```bash
llm model list                                # empty
llm model pull https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
llm model info qwen-qwen2.5-7b-instruct
llm config validate                           # warnings only
llm model uninstall qwen-qwen2.5-7b-instruct --yes
```

- [ ] **Step 3: Commit anything that surfaced**

If documentation tweaks or fixture cleanups appeared during the smoke, commit them now with a focused message.

```bash
git status
# (apply any small follow-ups)
git commit -m "chore: post-implementation cleanups from models redesign"
```

---

## Done criteria

- `llm model pull <hf-url>` populates `$LLM_MODELS/registry.json` and downloads the artifact; ambiguous URLs exit 1 with a hint.
- `llm model add <id> <path> --format <fmt>` symlinks local weights and registers an entry.
- `llm config validate` enforces the model-presence rule, format compatibility, and registry membership.
- `${model_path}` expands at serve/display time; missing models error loudly.
- The repo no longer carries `models/<id>/` content; `stub-runtime` config no longer references a model.
- Docs (`add-a-model.md`, `repo-conventions.md`, `README.md`) describe the new flow.
- `pytest tests -q` is green.
