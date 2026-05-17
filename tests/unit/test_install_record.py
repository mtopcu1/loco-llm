from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core.install_record import (
    InstallRecord,
    is_installed,
    read_record,
    record_path,
    write_record,
)


def test_record_path(tmp_path: Path):
    assert record_path(tmp_path / "runtimes", "llamacpp") == (
        tmp_path / "runtimes" / "llamacpp" / ".installed"
    )


def test_write_and_read_round_trip(tmp_path: Path):
    rec = InstallRecord(
        runtime_id="llamacpp",
        installed_at="2026-05-17T17:45:00Z",
        build_params={"flavor": "cuda", "jobs": 0},
        build_sh_sha256="abc123",
        verify_passed=True,
        schema_hash="def456",
    )
    write_record(tmp_path / "runtimes", rec)
    got = read_record(tmp_path / "runtimes", "llamacpp")
    assert got == rec


def test_read_record_missing_returns_none(tmp_path: Path):
    assert read_record(tmp_path / "runtimes", "llamacpp") is None


def test_is_installed(tmp_path: Path):
    assert is_installed(tmp_path / "runtimes", "llamacpp") is False
    write_record(
        tmp_path / "runtimes",
        InstallRecord(
            runtime_id="llamacpp",
            installed_at="2026-05-17T17:45:00Z",
            build_params={},
            build_sh_sha256="x",
            verify_passed=None,
            schema_hash="y",
        ),
    )
    assert is_installed(tmp_path / "runtimes", "llamacpp") is True


def test_read_record_corrupt_raises(tmp_path: Path):
    p = tmp_path / "runtimes" / "llamacpp" / ".installed"
    p.parent.mkdir(parents=True)
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        read_record(tmp_path / "runtimes", "llamacpp")
