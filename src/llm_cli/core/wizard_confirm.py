"""Yes/No prompts with wizard-style buttons (←→, Y/N, Enter)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from rich.console import Console
from rich.prompt import Prompt

from llm_cli.core import wizards
from llm_cli.core.param_grid_theme import DEFAULT_THEME
from llm_cli.core.wizard_shell import BinaryButton, render_binary_buttons, toggle_binary_button

_console = Console()
_HINT = "← → Tab · Y/N · Enter"


@dataclass
class _ConfirmState:
    focused: BinaryButton
    result: bool | None = None


def _can_run_confirm_tui() -> bool:
    if not sys.stdout.isatty():
        return False
    if wizards.use_plain_prompts():
        return False
    try:
        import prompt_toolkit  # noqa: F401

        return True
    except ImportError:
        return False


def _run_binary_confirm_tui(prompt: str, *, default: bool) -> bool:
    from prompt_toolkit.application import Application
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.styles import Style

    state = _ConfirmState(focused="yes" if default else "no")
    theme = DEFAULT_THEME

    def _finish(value: bool) -> None:
        from prompt_toolkit.application import get_app

        state.result = value
        get_app().exit()

    def _render_body() -> StyleAndTextTuples:
        out: StyleAndTextTuples = [("class:text", prompt + "\n\n")]
        out.extend(render_binary_buttons(focused=state.focused))
        out.append(("", "\n\n"))
        out.append(("class:text-dim", _HINT))
        return out

    kb = KeyBindings()

    @kb.add("left")
    def _left(_event) -> None:
        state.focused = "no"

    @kb.add("right")
    def _right(_event) -> None:
        state.focused = "yes"

    @kb.add("tab")
    def _tab(_event) -> None:
        state.focused = toggle_binary_button(state.focused)

    @kb.add("s-tab")
    def _shift_tab(_event) -> None:
        state.focused = toggle_binary_button(state.focused)

    @kb.add("y")
    @kb.add("Y")
    def _yes(_event) -> None:
        _finish(True)

    @kb.add("n")
    @kb.add("N")
    def _no(_event) -> None:
        _finish(False)

    @kb.add("enter")
    def _enter(_event) -> None:
        _finish(state.focused == "yes")

    @kb.add("c-c")
    def _ctrl_c(_event) -> None:
        raise KeyboardInterrupt

    body = Window(FormattedTextControl(_render_body), height=Dimension(min=4))
    app = Application(
        layout=Layout(HSplit([body])),
        key_bindings=kb,
        style=Style.from_dict(theme.to_prompt_toolkit_style()),
        full_screen=False,
        mouse_support=False,
    )
    app.run()
    if state.result is None:
        return default
    return state.result


def _parse_plain_choice(raw: str, *, default: bool) -> bool:
    token = str(raw).strip().lower()
    if token == "":
        return default
    if token in ("y", "yes", "2", "yes."):
        return True
    if token in ("n", "no", "1", "no."):
        return False
    return default


def _confirm_plain_buttons(prompt: str, *, default: bool) -> bool:
    """Numbered No/Yes when TUI is unavailable (no ``[Y/n]`` suffix)."""
    _console.print()
    _console.print(f"[bold]{prompt}[/bold]")
    _console.print("  [1] No   [2] Yes")
    _console.print(f"[dim]{_HINT}[/dim]")
    default_str = "2" if default else "1"
    raw = Prompt.ask("Choice", default=default_str, show_default=False)
    return _parse_plain_choice(raw, default=default)


def _confirm_non_tty(*, default: bool) -> bool:
    return default


def run_binary_confirm(prompt: str, *, default: bool = True) -> bool:
    """Ask a yes/no question with navigable No/Yes buttons."""
    if not sys.stdout.isatty():
        return _confirm_non_tty(default=default)
    if _can_run_confirm_tui():
        try:
            return _run_binary_confirm_tui(prompt, default=default)
        except ImportError:
            pass
    return _confirm_plain_buttons(prompt, default=default)
