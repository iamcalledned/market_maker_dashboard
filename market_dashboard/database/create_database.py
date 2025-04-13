import os
import sqlite3
from datetime import datetime


DB_PATH = os.getenv("SNIFFER_DB_PATH")

def init_db():
    if not os.path.exists(DB_PATH):
        print("[DB] Initializing new SQLite database...")
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
                retrieved_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    else:
        print("[DB] Database already exists.")

