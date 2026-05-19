"""Pexpect wrapper for driving `llm` in a PTY."""
from __future__ import annotations

import os
import re
import shlex
import sys
from pathlib import Path

import pexpect

from tests.tui.seed import RepoFixture

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


class TuiSession:
    """Thin helper around a spawned `llm` CLI process."""

    def __init__(self, child: pexpect.spawn, fixture: RepoFixture) -> None:
        self.child = child
        self.fixture = fixture

    @classmethod
    def spawn(
        cls,
        fixture: RepoFixture,
        args: list[str],
        *,
        timeout: int | None = None,
    ) -> TuiSession:
        if timeout is None:
            timeout = 120 if os.environ.get("CI") else 60
        cmd = [sys.executable, "-m", "llm_cli", *args]
        cmd_str = " ".join(shlex.quote(part) for part in cmd)
        repo = shlex.quote(str(fixture.repo_root))
        # Disable ixon so Ctrl+S reaches prompt_toolkit (Save) instead of freezing output.
        shell_cmd = f"stty -ixon 2>/dev/null; cd {repo} && exec {cmd_str}"
        child = pexpect.spawn(
            "bash",
            ["-lc", shell_cmd],
            env=fixture.spawn_env(src_root=_SRC_ROOT),
            encoding="utf-8",
            timeout=timeout,
        )
        child.setwinsize(30, 100)
        return cls(child, fixture)

    def expect(self, *patterns: str, timeout: int | None = None) -> int:
        if timeout is None:
            timeout = 30 if os.environ.get("CI") else 15
        try:
            return self.child.expect(list(patterns), timeout=timeout)
        except pexpect.TIMEOUT as exc:
            buf = strip_ansi(self.child.before or "")
            raise AssertionError(
                f"Timed out waiting for {patterns!r}; buffer tail:\n{buf[-4000:]}"
            ) from exc

    def send(self, text: str) -> None:
        self.child.send(text)

    def sendline(self, text: str = "") -> None:
        self.child.sendline(text)

    def wait_exit(self, *, timeout: int = 60) -> int:
        if not self.child.flag_eof:
            self.child.expect(pexpect.EOF, timeout=timeout)
        self.child.close()
        status = self.child.exitstatus
        if status is None:
            return 0 if self.child.signalstatus in (None, 0) else 128
        return int(status)

    def close(self) -> None:
        if self.child.isalive():
            self.child.close(force=True)

    @property
    def buffer(self) -> str:
        after = self.child.after
        after_text = "" if not isinstance(after, str) else after
        return strip_ansi((self.child.before or "") + after_text)
