"""Быстрый локальный кэш Лилит"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Optional


class LocalCache:
    def __init__(self):
        base = os.getenv("APPDATA") or os.path.expanduser("~/.lilit")
        self.base_dir = os.path.join(base, "A_ljurnal")
        os.makedirs(self.base_dir, exist_ok=True)
        self.path = os.path.join(self.base_dir, "cache.sqlite3")
        self._lock = threading.RLock()
        self._init()

    def _connect(self):
        con = sqlite3.connect(self.path, timeout=5)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        return con

    def _init(self):
        with self._connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at REAL NOT NULL)")

    def get(self, key: str) -> Optional[Any]:
        with self._lock, self._connect() as con:
            row = con.execute("SELECT value FROM cache WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None

    def age(self, key: str) -> Optional[float]:
        with self._lock, self._connect() as con:
            row = con.execute("SELECT updated_at FROM cache WHERE key=?", (key,)).fetchone()
        return None if not row else max(0.0, time.time() - float(row[0]))

    def set(self, key: str, value: Any):
        payload = json.dumps(value, ensure_ascii=False, default=str)
        with self._lock, self._connect() as con:
            con.execute(
                "INSERT INTO cache(key,value,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, payload, time.time()),
            )

    def delete(self, key: str):
        with self._lock, self._connect() as con:
            con.execute("DELETE FROM cache WHERE key=?", (key,))

    def clear_prefix(self, prefix: str):
        with self._lock, self._connect() as con:
            con.execute("DELETE FROM cache WHERE key LIKE ?", (prefix + "%",))

    def clear_user(self, user_id: str):
        prefix = f"user:{user_id}:"
        with self._lock, self._connect() as con:
            con.execute("DELETE FROM cache WHERE key LIKE ?", (prefix + "%",))


cache = LocalCache()
