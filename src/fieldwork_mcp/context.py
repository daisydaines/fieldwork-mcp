"""Request-scoped Fieldwork API key (used by hosted HTTP bearer auth)."""

from __future__ import annotations

import contextvars

_api_key_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "fieldwork_api_key", default=None
)


def set_api_key(api_key: str | None) -> contextvars.Token[str | None]:
    return _api_key_var.set(api_key)


def reset_api_key(token: contextvars.Token[str | None]) -> None:
    _api_key_var.reset(token)


def get_api_key() -> str | None:
    return _api_key_var.get()
