"""Real-systemd integration tests. Gated: skip unless `systemctl --user` works."""
from __future__ import annotations

import shutil
import subprocess

import pytest


def _systemd_user_available() -> bool:
    if not shutil.which("systemctl"):
        return False
    try:
        r = subprocess.run(
            ["systemctl", "--user", "list-units", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return r.returncode == 0


pytestmark = pytest.mark.skipif(
    not _systemd_user_available(),
    reason="systemctl --user not available (CI default)",
)


def test_real_systemd_smoke_placeholder() -> None:
    assert _systemd_user_available()
