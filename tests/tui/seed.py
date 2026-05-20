"""Filesystem fixtures for subprocess TUI tests (no monkeypatch in child)."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from llm_cli.core.model_registry import (
    Artifact,
    HFSource,
    Metadata,
    RegistryEntry,
    upsert_entry,
)
from llm_cli.core.scaffold import user_configs_dir, user_runtimes_dir
from llm_cli.core.settings import ensure_data_dirs, load_settings, resolve, save_settings


@dataclass(frozen=True)
class RepoFixture:
    home: Path
    repo_root: Path
    data_root: Path
    models_dir: Path
    runtimes_dir: Path
    configs_dir: Path
    user_runtimes_dir: Path

    def spawn_env(self, *, src_root: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["PYTHONPATH"] = str(src_root)
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = "100"
        env["LINES"] = "30"
        # GitHub Actions sets CI=true, which forces plain numbered menus; TUI tests
        # drive questionary arrow-key UX.
        env.pop("CI", None)
        env.pop("GITHUB_ACTIONS", None)
        env.pop("CURSOR_AGENT", None)
        return env


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def seed_repo(
    tmp_path: Path,
    monkeypatch,
    *,
    with_qwen: bool = False,
) -> RepoFixture:
    """Copy runtimes into an isolated repo and write user settings."""
    home = tmp_path / "home"
    home.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: home)

    shutil.copytree(_workspace_root() / "runtimes", repo_root / "runtimes")
    data_root = tmp_path / "data"
    monkeypatch.setenv("LOCO_HOME", str(data_root))
    monkeypatch.setenv("LOCO_INSTALL", str(repo_root))
    save_settings(
        {
            "data_root": str(data_root),
            "repo_root": str(repo_root),
        }
    )
    settings = resolve(load_settings())
    ensure_data_dirs(settings)

    models_dir = settings.models_dir
    configs_dir = user_configs_dir(settings)
    user_rt_dir = user_runtimes_dir(settings)
    if with_qwen:
        upsert_entry(
            models_dir,
            RegistryEntry(
                id="qwen-7b",
                format="gguf",
                source=HFSource(repo="r"),
                artifact=Artifact(
                    primary="m.gguf",
                    files=("m.gguf",),
                    total_size_bytes=8 * 1024**3,
                ),
                metadata=Metadata(),
                installed_at="2026-05-18T00:00:00Z",
            ),
        )

    return RepoFixture(
        home=home,
        repo_root=repo_root,
        data_root=data_root,
        models_dir=models_dir,
        runtimes_dir=settings.runtimes_dir,
        configs_dir=configs_dir,
        user_runtimes_dir=user_rt_dir,
    )


def add_tiered_build_runtime(repo_root: Path) -> None:
    """Add a tiny official runtime with common + advanced build params."""
    rt = repo_root / "runtimes" / "tier-rt"
    rt.mkdir(parents=True, exist_ok=False)
    (rt / "manifest.yaml").write_text(
        "id: tier-rt\n"
        "display_name: Tiered Runtime\n"
        "kind: official\n"
        "accepts_formats: []\n"
        "build:\n"
        "  flavor:\n"
        "    type: enum\n"
        "    values: [cuda, cpu]\n"
        "    tier: common\n"
        "    description: Build flavor\n"
        "  extra_jobs:\n"
        "    type: int\n"
        "    tier: advanced\n"
        "    description: Extra parallelism\n",
        encoding="utf-8",
    )
    (rt / "build.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        ": \"${LLM_DATA_ROOT:?LLM_DATA_ROOT must be set}\"\n"
        "mkdir -p \"${LLM_DATA_ROOT}/runtimes/tier-rt\"\n"
        "echo \"flavor=${LLM_BUILD_FLAVOR:-}\" > \"${LLM_DATA_ROOT}/runtimes/tier-rt/build-env.txt\"\n"
        "echo \"extra_jobs=${LLM_BUILD_EXTRA_JOBS:-}\" >> \"${LLM_DATA_ROOT}/runtimes/tier-rt/build-env.txt\"\n",
        encoding="utf-8",
    )
    (rt / "verify.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
        encoding="utf-8",
    )
    (rt / "serve.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nsleep 1\n",
        encoding="utf-8",
    )
    (rt / "healthcheck.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
        encoding="utf-8",
    )
