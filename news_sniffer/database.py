import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SNIFFER_DB_PATH = os.getenv("SNIFFER_DB_PATH")
DB_PATH = SNIFFER_DB_PATH

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

def insert_articles(articles):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    count = 0
    for article in articles:
        try:
            c.execute('''
                INSERT OR IGNORE INTO articles (headline, url, source, snippet, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                article.get("headline"),
                article.get("url"),
                article.get("source"),
                article.get("snippet"),
                article.get("timestamp") or datetime.utcnow().isoformat()
            ))
            count += c.rowcount
        except Exception as e:
            print(f"[DB] Error inserting article: {e}")
    conn.commit()
    conn.close()
    print(f"[DB] Inserted {count} new articles.")

def get_latest_articles(limit=20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT headline, url, source, snippet, timestamp
        FROM articles
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    rows = c.fetchall()
    conn.close()
    articles = []
    for row in rows:
        articles.append({
            "headline": row[0],
            "url": row[1],
            "source": row[2],
            "snippet": row[3],
            "timestamp": row[4]
        })
    return articles
