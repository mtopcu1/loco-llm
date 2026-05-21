"""Errors from `loco serve` / `loco switch` with user-visible messages."""


class ServeError(Exception):
    """Serve or switch failed; message is safe to show in API job logs."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        self.message = message
        self.exit_code = exit_code
        super().__init__(message)
