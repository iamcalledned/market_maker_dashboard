import os
import sqlite3
from datetime import datetime


DB_PATH = os.getenv("SNIFFER_DB_PATH")

def init_db():
    print("[DB] Initializing articles table if not exists...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        id INT AUTO_INCREMENT PRIMARY KEY,
        headline TEXT,
        url VARCHAR(1000) UNIQUE,
        source VARCHAR(255),
        snippet TEXT,
        full_text LONGTEXT,
        timestamp DATETIME,
        score INT DEFAULT 0,
        bot_response TEXT,
        retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

