import sqlite3
from pathlib import Path
from config import DATA_DIR

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
            user_notes TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()
