"""Local token vault: connect token -> Fieldwork API key.

This is NOT Dropbox-style OAuth. Fieldwork only exposes API keys today, so owners
paste a key once; we return a bearer token for the HTTP MCP.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import sqlite3
import time
from pathlib import Path

from cryptography.fernet import Fernet


def _default_db_path() -> Path:
    override = os.environ.get("FIELDWORK_VAULT_DB")
    if override:
        return Path(override)
    # Prefer project data dir when running from a checkout
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            data = parent / ".data"
            data.mkdir(exist_ok=True)
            return data / "vault.sqlite3"
    return Path.home() / ".fieldwork-mcp" / "vault.sqlite3"


def _fernet() -> Fernet:
    secret = os.environ.get("FIELDWORK_VAULT_SECRET", "").strip()
    if not secret:
        # Dev-only fallback so local connect works out of the box.
        # Set FIELDWORK_VAULT_SECRET in any shared/hosted deploy.
        secret = "fieldwork-mcp-dev-only-change-me"
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class Vault:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fernet = _fernet()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connections (
                    token_hash TEXT PRIMARY KEY,
                    api_key_encrypted TEXT NOT NULL,
                    label TEXT,
                    created_at REAL NOT NULL
                )
                """
            )

    def create(self, api_key: str, *, label: str | None = None) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        encrypted = self._fernet.encrypt(api_key.encode("utf-8")).decode("utf-8")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO connections (token_hash, api_key_encrypted, label, created_at) "
                "VALUES (?, ?, ?, ?)",
                (token_hash, encrypted, label, time.time()),
            )
        return token

    def get_api_key(self, token: str) -> str | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT api_key_encrypted FROM connections WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
        if not row:
            return None
        try:
            return self._fernet.decrypt(row["api_key_encrypted"].encode("utf-8")).decode(
                "utf-8"
            )
        except Exception:  # noqa: BLE001
            return None
