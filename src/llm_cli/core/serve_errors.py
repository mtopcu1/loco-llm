"""Errors from `loco serve` / `loco switch` with user-visible messages."""


class ServeError(Exception):
    """Serve or switch failed; message is safe to show in API job logs."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int = 1,
        hint: str | None = None,
    ) -> None:
        self.message = message
        self.exit_code = exit_code
        self.hint = hint
        super().__init__(message)
