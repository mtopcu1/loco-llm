"""Semantic color tokens for ParamGrid TUI and plain Rich fallback."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParamGridTheme:
    """Reconfigurable palette: prompt_toolkit classes and Rich markup share these tokens."""

    focus_bg: str = "#0066CC"
    focus_fg: str = "#FFFFFF"
    default_fg: str = "#E5A045"
    modified_fg: str = "#6BCB77"
    readonly_fg: str = "#56B6C2"
    advanced_accent: str = "#C678DD"
    hint_fg: str = "#98C379"
    error_fg: str = "#E06C75"
    meta_label: str = "#61AFEF"
    border_common: str = "#ABB2BF"
    border_advanced: str = "#C678DD"
    text_fg: str = "#D4D4D4"
    text_dim: str = "#808080"

    def to_prompt_toolkit_style(self) -> dict[str, str]:
        """Return ``Style.from_dict`` mapping (keys match ``class:*`` fragment names)."""
        fg = lambda c: f"fg:{c}"
        return {
            "cell-default": fg(self.default_fg),
            "cell-modified": fg(self.modified_fg),
            "cell-readonly": fg(self.readonly_fg),
            "cell-focus": f"bold bg:{self.focus_bg} fg:{self.focus_fg}",
            "header-common": f"bold {fg(self.border_common)}",
            "header-advanced": f"bold {fg(self.advanced_accent)}",
            "border-common": fg(self.border_common),
            "border-advanced": fg(self.border_advanced),
            "hint": fg(self.hint_fg),
            "error": fg(self.error_fg),
            "meta-label": fg(self.meta_label),
            "text": fg(self.text_fg),
            "text-dim": fg(self.text_dim),
        }

    def rich(self, role: str) -> str:
        """Rich markup prefix (open style) for *role*, without closing ``[/]``."""

        role_map: dict[str, str] = {
            "default": self.default_fg,
            "modified": self.modified_fg,
            "readonly": self.readonly_fg,
            "hint": self.hint_fg,
            "error": self.error_fg,
            "meta_label": self.meta_label,
            "meta": self.meta_label,
            "advanced": self.advanced_accent,
            "border_common": self.border_common,
            "border_advanced": self.border_advanced,
            "text": self.text_fg,
            "dim": self.text_dim,
            "focus": f"bold {self.focus_fg} on {self.focus_bg}",
            "focus_fg": self.focus_fg,
            "focus_bg": self.focus_bg,
        }
        if role not in role_map:
            msg = f"unknown rich role {role!r}; expected one of {sorted(role_map)!r}"
            raise ValueError(msg)
        payload = role_map[role]
        return f"[{payload}]"


DEFAULT_THEME = ParamGridTheme()
