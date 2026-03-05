"""
Mutelens - Badge Store
=======================
SQLite-backed storage for evaluation results.
Each evaluation generates a short unique badge ID that can be used
to serve SVG badges and verification pages.
"""

import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional

if os.environ.get("VERCEL"):
    DB_DIR = "/tmp"
else:
    DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "mutelens.db")

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        os.makedirs(DB_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _init_db(_local.conn)
    return _local.conn


def _init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            badge_id      TEXT PRIMARY KEY,
            url           TEXT NOT NULL,
            domain        TEXT,
            title         TEXT,
            author        TEXT,
            published     TEXT,
            cover_image   TEXT,
            word_count    INTEGER,
            language      TEXT,
            content_preview TEXT,
            overall_score REAL,
            grade         TEXT,
            vetoed        INTEGER DEFAULT 0,
            veto_reason   TEXT,
            dimensions    TEXT,
            weights       TEXT,
            analysis_summary TEXT,
            created_at    TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_eval_url ON evaluations(url)
    """)
    conn.commit()


def _generate_badge_id() -> str:
    return secrets.token_urlsafe(6)[:8]


@dataclass
class StoredEvaluation:
    badge_id: str
    url: str
    domain: str
    title: str
    author: str
    published: str
    cover_image: str
    word_count: int
    language: str
    content_preview: str
    overall_score: float
    grade: str
    vetoed: bool
    veto_reason: str
    dimensions: list[dict]
    weights: dict[str, float]
    analysis_summary: str
    created_at: str


def save_evaluation(
    url: str,
    domain: str,
    title: str,
    author: str,
    published: str,
    cover_image: str,
    word_count: int,
    language: str,
    content_preview: str,
    overall_score: float,
    grade: str,
    vetoed: bool,
    veto_reason: str,
    dimensions: list[dict],
    weights: dict[str, float],
    analysis_summary: str,
) -> str:
    """Save an evaluation and return the badge_id."""
    conn = _get_conn()
    badge_id = _generate_badge_id()

    for _ in range(5):
        try:
            conn.execute(
                """INSERT INTO evaluations
                   (badge_id, url, domain, title, author, published, cover_image,
                    word_count, language, content_preview, overall_score, grade,
                    vetoed, veto_reason, dimensions, weights, analysis_summary, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    badge_id, url, domain, title, author, published, cover_image,
                    word_count, language, content_preview, overall_score, grade,
                    1 if vetoed else 0, veto_reason,
                    json.dumps(dimensions, ensure_ascii=False),
                    json.dumps(weights, ensure_ascii=False),
                    analysis_summary,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            return badge_id
        except sqlite3.IntegrityError:
            badge_id = _generate_badge_id()

    raise RuntimeError("Failed to generate unique badge ID")


def get_evaluation(badge_id: str) -> Optional[StoredEvaluation]:
    """Retrieve an evaluation by badge_id."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM evaluations WHERE badge_id = ?", (badge_id,)
    ).fetchone()
    if not row:
        return None

    return StoredEvaluation(
        badge_id=row["badge_id"],
        url=row["url"],
        domain=row["domain"],
        title=row["title"],
        author=row["author"],
        published=row["published"],
        cover_image=row["cover_image"],
        word_count=row["word_count"],
        language=row["language"],
        content_preview=row["content_preview"],
        overall_score=row["overall_score"],
        grade=row["grade"],
        vetoed=bool(row["vetoed"]),
        veto_reason=row["veto_reason"],
        dimensions=json.loads(row["dimensions"]),
        weights=json.loads(row["weights"]),
        analysis_summary=row["analysis_summary"],
        created_at=row["created_at"],
    )
