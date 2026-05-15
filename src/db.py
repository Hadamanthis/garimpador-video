import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "videos.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id        TEXT PRIMARY KEY,
                url       TEXT NOT NULL,
                title     TEXT,
                source    TEXT,
                duration  INTEGER,
                score     INTEGER,
                hook_score INTEGER,
                reason    TEXT,
                angle     TEXT,
                status    TEXT DEFAULT 'novo',
                found_at  TEXT
            )
        """)
        conn.commit()


def video_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def is_seen(url: str) -> bool:
    with _conn() as conn:
        row = conn.execute(
            "SELECT status FROM videos WHERE id = ?", (video_id(url),)
        ).fetchone()
        return row is not None and row["status"] == "visto"


def upsert_video(video: dict):
    vid = video_id(video["url"])
    with _conn() as conn:
        existing = conn.execute(
            "SELECT status FROM videos WHERE id = ?", (vid,)
        ).fetchone()
        if existing and existing["status"] == "salvo":
            return
        conn.execute("""
            INSERT INTO videos (id, url, title, source, duration, score,
                                hook_score, reason, angle, status, found_at)
            VALUES (:id, :url, :title, :source, :duration, :score,
                    :hook_score, :reason, :angle, :status, :found_at)
            ON CONFLICT(id) DO UPDATE SET
                hook_score = excluded.hook_score,
                reason     = excluded.reason,
                angle      = excluded.angle,
                found_at   = excluded.found_at
        """, {
            "id": vid,
            "url": video["url"],
            "title": video.get("title", ""),
            "source": video.get("source", ""),
            "duration": video.get("duration"),
            "score": video.get("score"),
            "hook_score": video.get("hook_score"),
            "reason": video.get("reason", ""),
            "angle": video.get("angle", ""),
            "status": video.get("status", "novo"),
            "found_at": datetime.utcnow().isoformat(),
        })
        conn.commit()


def mark_status(url: str, status: str):
    with _conn() as conn:
        conn.execute(
            "UPDATE videos SET status = ? WHERE id = ?",
            (status, video_id(url))
        )
        conn.commit()


def get_saved() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM videos WHERE status = 'salvo' ORDER BY hook_score DESC"
        ).fetchall()
        return [dict(r) for r in rows]
