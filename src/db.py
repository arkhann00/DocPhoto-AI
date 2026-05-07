from __future__ import annotations

from pathlib import Path

import aiosqlite

SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS users (
    telegram_id   INTEGER PRIMARY KEY,
    username      TEXT    NOT NULL DEFAULT '',
    balance       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


class Database:
    def __init__(self, path: Path, *, initial_balance: int = 0) -> None:
        self._path = path
        self._initial_balance = initial_balance
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    def _conn_or_raise(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    # ── users ────────────────────────────────────────────────

    async def get_or_create_user(
        self, telegram_id: int, username: str = ""
    ) -> dict:
        conn = self._conn_or_raise()
        async with conn.execute(
            "SELECT telegram_id, username, balance FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ) as cur:
            row = await cur.fetchone()

        if row is not None:
            if username and row["username"] != username:
                await conn.execute(
                    "UPDATE users SET username = ? WHERE telegram_id = ?",
                    (username, telegram_id),
                )
                await conn.commit()
            return {
                "telegram_id": row["telegram_id"],
                "username": username or row["username"],
                "balance": row["balance"],
            }

        await conn.execute(
            "INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, ?)",
            (telegram_id, username, self._initial_balance),
        )
        await conn.commit()
        return {
            "telegram_id": telegram_id,
            "username": username,
            "balance": self._initial_balance,
        }

    async def get_balance(self, telegram_id: int) -> int:
        conn = self._conn_or_raise()
        async with conn.execute(
            "SELECT balance FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ) as cur:
            row = await cur.fetchone()
        return int(row["balance"]) if row else 0

    async def add_balance(self, telegram_id: int, amount: int) -> int:
        """Add `amount` generations and return new balance."""
        conn = self._conn_or_raise()
        await conn.execute(
            "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
            (amount, telegram_id),
        )
        await conn.commit()
        return await self.get_balance(telegram_id)

    async def consume_generation(self, telegram_id: int) -> bool:
        """Deduct 1 generation if balance > 0. Returns True on success."""
        conn = self._conn_or_raise()
        async with conn.execute(
            "UPDATE users SET balance = balance - 1 WHERE telegram_id = ? AND balance > 0",
            (telegram_id,),
        ) as cur:
            await conn.commit()
            return cur.rowcount > 0
