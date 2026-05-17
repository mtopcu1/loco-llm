from __future__ import annotations

from pathlib import Path

from llm_cli.core import doctor
from llm_cli.core.install_record import InstallRecord, write_record


def _write_runtime(repo: Path, rid: str, requires: list[dict]) -> None:
    root = repo / "runtimes" / rid
    root.mkdir(parents=True)

    import yaml as _y

    body = {
        "id": rid,
        "display_name": rid,
        "official": True,
        "build": {"flavor": {"type": "enum", "values": ["cuda", "cpu"], "default": "cuda"}},
        "requires": requires,
    }
    (root / "manifest.yaml").write_text(_y.safe_dump(body, sort_keys=False), encoding="utf-8")
    for script in ("build.sh", "serve.sh", "healthcheck.sh"):
        (root / script).write_text("#!/usr/bin/env bash\n", encoding="utf-8")


def test_requirements_for_runtime_filters_by_when(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_runtime(
        repo,
        "rt-a",
        [
            {
                "id": "cmake",
                "name": "cmake",
                "verify": {"cmd": "cmake --version", "version_regex": "([\\d.]+)", "min": "3.16"},
                "install_hint": "apt install cmake",
            },
            {
                "id": "nvcc",
                "name": "nvcc",
                "when": {"build.flavor": "cuda"},
                "verify": {"cmd": "nvcc --version", "version_regex": "([\\d.]+)", "min": "12.0"},
                "install_hint": "install cuda",
            },
        ],
    )

    cuda = doctor.requirements_for_runtime(repo, "rt-a", build_params={"flavor": "cuda"})
    cpu = doctor.requirements_for_runtime(repo, "rt-a", build_params={"flavor": "cpu"})

    assert sorted(r.id for r in cuda) == ["cmake", "nvcc"]
    assert sorted(r.id for r in cpu) == ["cmake"]


def test_requirements_for_all_runtimes_uses_install_record_or_defaults(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_runtime(
        repo,
        "rt-a",
        [
            {
                "id": "cmake",
                "verify": {"cmd": "cmake", "version_regex": "([\\d.]+)", "min": "3.16"},
                "install_hint": "",
            },
            {
                "id": "nvcc",
                "when": {"build.flavor": "cuda"},
                "verify": {"cmd": "nvcc", "version_regex": "([\\d.]+)", "min": "12.0"},
                "install_hint": "",
            },
        ],
    )
    _write_runtime(
        repo,
        "rt-b",
        [
            {
                "id": "git",
                "verify": {"cmd": "git --version", "version_regex": "([\\d.]+)", "min": "2.30"},
                "install_hint": "",
            }
        ],
    )

    runtimes_dir = tmp_path / "data" / "runtimes"
    runtimes_dir.mkdir(parents=True)
    write_record(
        runtimes_dir,
        InstallRecord(
            runtime_id="rt-a",
            installed_at="2026-05-17T00:00:00Z",
            build_params={"flavor": "cpu"},
            build_sh_sha256="x",
            verify_passed=True,
            schema_hash="y",
        ),
    )

    installed = doctor.requirements_for_all_runtimes(repo, runtimes_dir, installed_only=True)
    assert sorted(r.id for r in installed) == ["cmake"]

    all_reqs = doctor.requirements_for_all_runtimes(repo, runtimes_dir, installed_only=False)
    assert sorted(r.id for r in all_reqs) == ["cmake", "git"]
