import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "scheduler.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Table for scheduled posts
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        drive_url TEXT NOT NULL,
        title TEXT,
        caption TEXT,
        hashtags TEXT,
        status TEXT DEFAULT 'pending',
        media_type TEXT,
        error_message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        posted_at TEXT
    )
    ''')
    
    # Table for app settings & session tokens
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

def add_post(drive_url: str, title: str, caption: str, hashtags: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO posts (drive_url, title, caption, hashtags, status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (drive_url, title, caption, hashtags))
    conn.commit()
    post_id = cursor.lastrowid
    conn.close()
    return post_id

def get_all_posts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM posts ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_next_pending_post():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM posts WHERE status = 'pending' ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_post_by_id(post_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_post_status(post_id: int, status: str, media_type: str = None, error_message: str = None):
    conn = get_db()
    cursor = conn.cursor()
    posted_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if status == 'posted' else None
    
    cursor.execute('''
        UPDATE posts 
        SET status = ?, 
            media_type = COALESCE(?, media_type), 
            error_message = ?, 
            posted_at = COALESCE(?, posted_at)
        WHERE id = ?
    ''', (status, media_type, error_message, posted_at, post_id))
    conn.commit()
    conn.close()

def delete_post(post_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()

def set_setting(key: str, value: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    ''', (key, value))
    conn.commit()
    conn.close()

def get_setting(key: str, default=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default

def remove_setting(key: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
    conn.commit()
    conn.close()
