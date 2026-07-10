import os
import sqlite3
from typing import Optional, Dict, Any

# Repo-relative data dir (…/CivicOS-AI/data), portable across machines.
DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
DB_PATH = os.path.join(DB_DIR, "civicos.db")

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            current_step INTEGER NOT NULL,
            status TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_session(session_id: str, domain: str, current_step: int, status: str):
    init_db()  # Make sure DB and directory exist
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (session_id, domain, current_step, status, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id) DO UPDATE SET
            current_step = excluded.current_step,
            status = excluded.status,
            updated_at = CURRENT_TIMESTAMP
    """, (session_id, domain, current_step, status))
    conn.commit()
    conn.close()

def get_last_active_session(domain: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT session_id, domain, current_step, status, updated_at
        FROM sessions
        WHERE domain = ? AND status = 'active'
        ORDER BY updated_at DESC
        LIMIT 1
    """, (domain,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def clear_session(session_id: str):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET status = 'completed' WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
