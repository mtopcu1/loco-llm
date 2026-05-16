import sys

import pytest

from llm_cli.core.shell import CommandResult, run_command


def test_run_command_captures_stdout() -> None:
    result = run_command([sys.executable, "-c", "print('hello')"])
    assert isinstance(result, CommandResult)
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.stderr == ""
    assert result.found is True


def test_run_command_captures_nonzero_exit() -> None:
    result = run_command([sys.executable, "-c", "import sys; sys.exit(2)"])
    assert result.exit_code == 2
    assert result.found is True


def test_run_command_missing_executable_returns_not_found() -> None:
    result = run_command(["__definitely_not_a_command_42__"])
    assert result.found is False
    assert result.exit_code == -1


def test_run_command_timeout_returns_timeout_flag() -> None:
    result = run_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout_sec=0.5,
    )
    assert result.timed_out is True
    assert result.found is True


def test_run_command_passes_env(monkeypatch: pytest.MonkeyPatch) -> None:
    result = run_command(
        [sys.executable, "-c", "import os; print(os.environ.get('FOO', 'unset'))"],
        env={"FOO": "bar"},
    )
    assert "bar" in result.stdout
