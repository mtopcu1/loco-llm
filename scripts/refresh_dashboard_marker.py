"""Update dashboard .installed hash after copying dist (no npm)."""
from __future__ import annotations

from datetime import UTC, datetime

import importlib.metadata

from llm_cli.core.dashboard import InstalledRecord, compute_dist_hash, dist_dir, write_installed_record


def main() -> None:
    d = dist_dir()
    if not (d / "index.html").is_file():
        raise SystemExit(f"missing {d / 'index.html'}")
    write_installed_record(
        InstalledRecord(
            installed_at=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            cli_version=importlib.metadata.version("loco-llm-cli"),
            node_version="skipped",
            npm_version="skipped",
            dist_hash=compute_dist_hash(d),
        )
    )
    print(f"updated {d}")


if __name__ == "__main__":
    main()
