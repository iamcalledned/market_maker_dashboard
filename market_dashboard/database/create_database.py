import os
import sqlite3
from datetime import datetime


DB_PATH = os.getenv("SNIFFER_DB_PATH")

def init_db():
    print("[DB] Initializing articles table if not exists...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT,
            url TEXT UNIQUE,
            source TEXT,
            snippet TEXT,
            timestamp TEXT,
            score INTEGER DEFAULT 0,
            bot_response TEXT,
            retrieved_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

