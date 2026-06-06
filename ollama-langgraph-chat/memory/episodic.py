import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("episodes.db")


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                role      TEXT NOT NULL,
                content   TEXT NOT NULL,
                topic     TEXT,
                ts        TEXT NOT NULL,
                extracted INTEGER DEFAULT 0
            )
        """)


def save_episode(role: str, content: str, topic: str = None):
    with _conn() as c:
        c.execute(
            "INSERT INTO episodes (role, content, topic, ts) VALUES (?,?,?,?)",
            (role, content, topic, datetime.utcnow().isoformat())
        )


def get_unextracted(limit: int = 10) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, role, content, ts FROM episodes WHERE extracted=0 LIMIT ?",
            (limit,)
        ).fetchall()
    return [{"id": r[0], "role": r[1], "content": r[2], "ts": r[3]} for r in rows]


def mark_extracted(ids: list[int]):
    with _conn() as c:
        c.executemany(
            "UPDATE episodes SET extracted=1 WHERE id=?",
            [(i,) for i in ids]
        )


def get_recent(n: int = 5) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content, ts FROM episodes ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
    return [{"role": r[0], "content": r[1], "ts": r[2]} for r in reversed(rows)]