"""Terminal key sequences for pexpect sessions."""
from __future__ import annotations


def _ctrl(ch: str) -> str:
    return chr(ord(ch) ^ 0x40)


CTRL_C = _ctrl("c")
CTRL_S = _ctrl("s")
CTRL_A = _ctrl("a")
CTRL_X = _ctrl("x")
ESC = "\x1b"
ENTER = "\r"
DOWN = "\x1b[B"
UP = "\x1b[A"
RIGHT = "\x1b[C"
LEFT = "\x1b[D"
SPACE = " "
