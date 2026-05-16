from pathlib import Path

from llm_cli.core.doctor import (
    CheckStatus,
    Requirement,
    RequirementResult,
    check_requirement,
    load_requirements,
)
from llm_cli.core.shell import CommandResult


def _ok_run(stdout: str):
    return lambda cmd, **kw: CommandResult(
        exit_code=0, stdout=stdout, stderr="", found=True, timed_out=False
    )


def _missing_run():
    return lambda cmd, **kw: CommandResult(
        exit_code=-1, stdout="", stderr="", found=False, timed_out=False
    )


def _example_req() -> Requirement:
    return Requirement(
        id="python",
        name="Python",
        why="for tests",
        verify_cmd="python3 --version",
        version_regex=r"Python\s+([\d.]+)",
        min_version="3.11",
        install_hint="apt install python3.11",
    )


def test_check_requirement_ok() -> None:
    result = check_requirement(_example_req(), run_command=_ok_run("Python 3.11.9\n"))
    assert isinstance(result, RequirementResult)
    assert result.status == CheckStatus.OK
    assert result.detected_version == "3.11.9"


def test_check_requirement_too_old() -> None:
    result = check_requirement(_example_req(), run_command=_ok_run("Python 3.10.6\n"))
    assert result.status == CheckStatus.OUTDATED
    assert result.detected_version == "3.10.6"


def test_check_requirement_missing_executable() -> None:
    result = check_requirement(_example_req(), run_command=_missing_run())
    assert result.status == CheckStatus.MISSING
    assert result.detected_version is None


def test_check_requirement_unparseable_output_marks_unknown() -> None:
    result = check_requirement(_example_req(), run_command=_ok_run("garbage\n"))
    assert result.status == CheckStatus.UNKNOWN


def test_check_requirement_no_min_marks_ok_when_present() -> None:
    req = Requirement(
        id="x",
        name="x",
        why="x",
        verify_cmd="echo hi",
        version_regex=r"hi",
        min_version=None,
        install_hint="",
    )
    result = check_requirement(req, run_command=_ok_run("hi\n"))
    assert result.status == CheckStatus.OK


def test_load_requirements_parses_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "requirements.yaml"
    yaml_file.write_text(
        "- id: python\n"
        "  name: Python\n"
        "  why: base interpreter\n"
        "  verify:\n"
        "    cmd: python3 --version\n"
        "    version_regex: 'Python\\s+([\\d.]+)'\n"
        "    min: '3.11'\n"
        "  install_hint: 'apt install python3.11'\n",
        encoding="utf-8",
    )

    reqs = load_requirements(yaml_file)
    assert len(reqs) == 1
    assert reqs[0].id == "python"
    assert reqs[0].min_version == "3.11"
    assert reqs[0].verify_cmd == "python3 --version"
