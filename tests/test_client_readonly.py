"""Unit tests that do not call the live Fieldwork API."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from fieldwork_mcp.client import FieldworkClient
from fieldwork_mcp.exceptions import FieldworkConfigError, FieldworkReadOnlyError


def test_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIELDWORK_API_KEY", raising=False)
    with pytest.raises(FieldworkConfigError):
        FieldworkClient()


@pytest.mark.asyncio
async def test_refuses_non_get(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIELDWORK_API_KEY", "test-key-not-real")
    client = FieldworkClient()
    with pytest.raises(FieldworkReadOnlyError):
        await client.request("POST", "/customers")


@pytest.mark.asyncio
@respx.mock
async def test_get_profile_uses_api_key_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIELDWORK_API_KEY", "test-key-not-real")
    monkeypatch.delenv("FIELDWORK_AUTH_SCHEME", raising=False)
    route = respx.get("https://api3.fieldworkhq.com/v3.1/profile").mock(
        return_value=Response(200, json={"user_id": 1, "name": "API User"})
    )
    client = FieldworkClient()
    data = await client.get_profile()
    assert data["name"] == "API User"
    assert route.called
    assert route.calls.last.request.headers["api-key"] == "test-key-not-real"


@pytest.mark.asyncio
@respx.mock
async def test_query_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIELDWORK_API_KEY", "test-key-not-real")
    monkeypatch.setenv("FIELDWORK_AUTH_SCHEME", "query")
    route = respx.get("https://api3.fieldworkhq.com/v3.1/materials").mock(
        return_value=Response(200, json=[{"id": 9, "name": "Termidor"}])
    )
    client = FieldworkClient()
    data = await client.list_materials()
    assert data[0]["name"] == "Termidor"
    assert route.calls.last.request.url.params["api_key"] == "test-key-not-real"
    assert "api-key" not in route.calls.last.request.headers