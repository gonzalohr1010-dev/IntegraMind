"""personalization.py
Simple user profile storage (SQLite) and personalization hooks (classifier stub).
"""
from __future__ import annotations
import sqlite3
import os

DB = 'users.sqlite'


def init_user_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            profile_json TEXT
        )
    ''')
    conn.commit()
    conn.close()


def save_profile(user_id: str, profile_json: str):
    init_user_db()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO users (id, created_at, profile_json) VALUES (?, datetime("now"), ?)', (user_id, profile_json))
    conn.commit()
    conn.close()


def load_profile(user_id: str) -> str:
    init_user_db()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT profile_json FROM users WHERE id=?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else '{}'


def classify_user_type(text: str) -> str:
    # stub: simple heuristic
    t = text.lower()
    if 'profesor' in t or 'docente' in t:
        return 'educator'
    if 'estudiante' in t or 'estudio' in t:
        return 'student'
    return 'general'
