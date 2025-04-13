import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SNIFFER_DB_PATH = os.getenv("SNIFFER_DB_PATH")
DB_PATH = SNIFFER_DB_PATH

def init_db():
    print("[DB] Initializing articles table if not exists...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS articles (
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

def insert_articles(articles):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    count = 0
    for article in articles:
        try:
            c.execute('''
                INSERT OR IGNORE INTO articles
                (headline, url, source, snippet, full_text, timestamp, score, bot_response)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article.get("headline"),
                article.get("url"),
                article.get("source"),
                article.get("snippet"),
                article.get("full_text"),
                article.get("timestamp"),
                article.get("score", 0),
                article.get("bot_response")
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
