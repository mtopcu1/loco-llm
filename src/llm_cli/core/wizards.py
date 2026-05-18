"""Hybrid prompts: questionary on TTY, plain Rich prompts otherwise."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from rich.console import Console
from rich.prompt import Prompt

Choice = str

_FORCE_PLAIN = False
_console = Console()


def force_plain(flag: bool) -> None:
    """Disable arrow-key UI (used by tests / `--quiet` callers when wired)."""
    global _FORCE_PLAIN
    _FORCE_PLAIN = flag


def use_plain_prompts() -> bool:
    if _FORCE_PLAIN:
        return True
    if not sys.stdout.isatty():
        return True
    term = os.environ.get("TERM", "").strip().lower()
    return term in ("", "dumb")


def text(
    prompt: str,
    *,
    default: str | None = None,
    validate: Callable[[str], str | None] | None = None,
) -> str:
    """Single-line text entry."""
    while True:
        answer = Prompt.ask(prompt, default=default)
        if validate is None:
            return answer
        err = validate(answer)
        if err is None:
            return answer
        _console.print(f"[red]error:[/red] {err}")


def confirm(prompt: str, *, default: bool = True) -> bool:
    if use_plain_prompts():
        suffix = "[Y/n]" if default else "[y/N]"
        raw = Prompt.ask(f"{prompt} {suffix}", default="")
        token = str(raw).strip().lower()
        if token == "":
            return default
        if token in ("y", "yes"):
            return True
        if token in ("n", "no"):
            return False
        return default
    import questionary

    result = questionary.confirm(prompt, default=default).ask()
    return bool(result)


def select(
    prompt: str,
    choices: Iterable[Choice],
    *,
    default: Choice | None = None,
) -> Choice:
    choice_list = list(choices)
    if not choice_list:
        raise ValueError("select() requires at least one choice")

    if use_plain_prompts():
        _console.print(f"\n{prompt}")
        for i, c in enumerate(choice_list, start=1):
            marker = " <default>" if c == default else ""
            _console.print(f"  [{i}] {c}{marker}")
        default_str = (
            str(choice_list.index(default) + 1) if default in choice_list else None
        )
        while True:
            raw = Prompt.ask("Enter number", default=default_str)
            try:
                idx = int(str(raw).strip())
            except ValueError:
                continue
            if 1 <= idx <= len(choice_list):
                return choice_list[idx - 1]

    import questionary

    picked = questionary.select(prompt, choices=choice_list, default=default).ask()
    if picked is None:
        return choice_list[0]
    return picked


def checkbox(
    prompt: str,
    choices: Iterable[Choice],
    *,
    defaults: tuple[Choice, ...] = (),
) -> tuple[Choice, ...]:
    choice_list = list(choices)
    if use_plain_prompts():
        _console.print(f"\n{prompt}")
        _console.print("Comma-separated indices (empty = none):")
        for i, c in enumerate(choice_list, start=1):
            marker = " [default]" if c in defaults else ""
            _console.print(f"  [{i}] {c}{marker}")
        default_str = ",".join(
            str(choice_list.index(d) + 1) for d in defaults if d in choice_list
        )
        raw = Prompt.ask(">", default=default_str)
        if not str(raw).strip():
            return ()
        picked: list[Choice] = []
        for token in str(raw).split(","):
            t = token.strip()
            if not t:
                continue
            try:
                idx = int(t)
            except ValueError:
                continue
            if 1 <= idx <= len(choice_list):
                picked.append(choice_list[idx - 1])
        return tuple(picked)

    import questionary

    sel = questionary.checkbox(prompt, choices=choice_list).ask()
    return tuple(sel or ())


SAVE_SENTINEL = "save"
ABORT_SENTINEL = "abort"

RowsInput = list[tuple[str, str]] | Callable[[], list[tuple[str, str]]]


def review(
    rows: RowsInput,
    *,
    on_edit: Callable[[str], None],
) -> str:
    """Loop pick rows until save or abort. Returns SAVE_SENTINEL or ABORT_SENTINEL."""
    save = "[Save and write file]"
    abort = "[Abort without saving]"
    while True:
        row_list = rows() if callable(rows) else rows
        choices: list[str] = [save]
        for label, value in row_list:
            choices.append(f"{label}    {value}")
        choices.append(abort)
        pick = select("Review — edit a row, save, or abort", choices)
        if pick == save:
            return SAVE_SENTINEL
        if pick == abort:
            return ABORT_SENTINEL
        label = pick.split("    ", 1)[0].strip()
        on_edit(label)


@dataclass
class WalkTierResult:
    values: dict[str, str] = field(default_factory=dict)
    advanced_revealed: bool = False


def walk_tier(specs: list[Any]) -> WalkTierResult:
    """Prompt for common-tier ParamSpecs, optionally advanced."""
    common = [s for s in specs if getattr(s, "tier", "common") == "common"]
    advanced = [s for s in specs if getattr(s, "tier", "common") == "advanced"]
    values: dict[str, str] = {}
    for spec in common:
        default_s = None if spec.default is None else str(spec.default)
        if spec.description:
            _console.print(f"[bold cyan]{spec.key}[/bold cyan] — {spec.description}")
        values[spec.key] = text(spec.key, default=default_s)
    revealed = False
    if advanced:
        revealed = confirm(f"Reveal {len(advanced)} advanced parameter(s)?", default=False)
        if revealed:
            for spec in advanced:
                default_s = None if spec.default is None else str(spec.default)
                if spec.description:
                    _console.print(
                        f"[bold cyan]{spec.key}[/bold cyan] — {spec.description}"
                    )
                values[spec.key] = text(spec.key, default=default_s)
    return WalkTierResult(values=values, advanced_revealed=revealed)
