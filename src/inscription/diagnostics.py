from __future__ import annotations


class InscriptionError(Exception):
    """Base diagnostic for deterministic compiler failures."""

    def __init__(self, message: str, line: int | None = None):
        self.message = message
        self.line = line
        if line is None:
            super().__init__(message)
        else:
            super().__init__(f"line {line}: {message}")
