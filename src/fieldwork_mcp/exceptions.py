"""Typed errors for the Fieldwork client / MCP tools."""

from __future__ import annotations


class FieldworkError(Exception):
    """Base error for all Fieldwork MCP failures."""


class FieldworkConfigError(FieldworkError):
    """Missing or invalid local configuration (usually the API key)."""


class FieldworkReadOnlyError(FieldworkError):
    """Raised when code attempts a non-GET request.

    This package is intentionally read-only. Write endpoints are not exposed.
    """


class FieldworkAuthError(FieldworkError):
    """Authentication failed (HTTP 401/403)."""


class FieldworkNotFoundError(FieldworkError):
    """Resource not found (HTTP 404)."""


class FieldworkRateLimitError(FieldworkError):
    """Rate limited (HTTP 429)."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class FieldworkConnectionError(FieldworkError):
    """Network failure talking to Fieldwork."""


class FieldworkAPIError(FieldworkError):
    """Unexpected Fieldwork API error."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        body: object | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.body = body