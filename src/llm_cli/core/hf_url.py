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
