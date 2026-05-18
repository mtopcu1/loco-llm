from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core.install_record import (
    InstallRecord,
    file_sha256,
    is_installed,
    read_record,
    record_path,
    schema_hash,
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


def test_file_sha256(tmp_path: Path):
    p = tmp_path / "a.sh"
    p.write_bytes(b"hello\n")
    # sha256("hello\n")
    assert file_sha256(p) == (
        "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"
    )


def test_file_sha256_missing_returns_empty(tmp_path: Path):
    assert file_sha256(tmp_path / "nope") == ""


def test_schema_hash_stable_across_key_order():
    a = {"flavor": {"type": "enum", "values": ["cuda", "cpu"], "default": "cuda"}}
    b = {"flavor": {"default": "cuda", "type": "enum", "values": ["cuda", "cpu"]}}
    assert schema_hash(a) == schema_hash(b)


def test_schema_hash_changes_on_value_change():
    a = {"jobs": {"type": "int", "default": 0}}
    b = {"jobs": {"type": "int", "default": 1}}
    assert schema_hash(a) != schema_hash(b)


def test_install_record_custom_kind_round_trip(tmp_path: Path) -> None:
    rec = InstallRecord(
        runtime_id="vllm-custom",
        installed_at="2026-05-18T10:00:00Z",
        build_params={},
        build_sh_sha256="",
        verify_passed=None,
        schema_hash="abc123",
        kind="custom",
    )
    write_record(tmp_path / "runtimes", rec)
    got = read_record(tmp_path / "runtimes", "vllm-custom")
    assert got == rec
    assert got.kind == "custom"
    assert got.verify_passed is None


def test_install_record_kind_defaults_to_official_when_absent(tmp_path: Path) -> None:
    import json

    p = record_path(tmp_path / "runtimes", "legacy")
    p.parent.mkdir(parents=True)
    p.write_text(
        json.dumps({
            "runtime_id": "legacy",
            "installed_at": "2026-05-15T00:00:00Z",
            "build_params": {"flavor": "cuda"},
            "build_sh_sha256": "deadbeef",
            "verify_passed": True,
            "schema_hash": "cafe",
        }),
        encoding="utf-8",
    )
    rec = read_record(tmp_path / "runtimes", "legacy")
    assert rec is not None
    assert rec.kind == "official"
