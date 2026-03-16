import sqlite3
import os
from pathlib import Path

DATA_DIR = os.environ.get("DATA_DIR", str(Path(__file__).parent))
DB_PATH = Path(DATA_DIR) / "fashion.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            source_url TEXT,
            source_platform TEXT DEFAULT '其他',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            status TEXT DEFAULT 'pending',
            ai_tags TEXT DEFAULT '[]',
            ai_style TEXT DEFAULT '',
            ai_color TEXT DEFAULT '',
            ai_category TEXT DEFAULT '',
            ai_notes TEXT DEFAULT '',
            user_notes TEXT DEFAULT '',
            is_favorite INTEGER DEFAULT 0
        )
    """)
    # 兼容旧数据库：补充字段（若已存在则忽略）
    try:
        conn.execute("ALTER TABLE images ADD COLUMN is_favorite INTEGER DEFAULT 0")
    except Exception:
        pass
    conn.commit()
    conn.close()
