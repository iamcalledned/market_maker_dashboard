from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from fetcher import fetch_all_google_topics, fetch_zerohedge_rss
from database import init_db, insert_articles, get_latest_articles
import os
from dotenv import load_dotenv

load_dotenv()

SNIFFER_DB_PATH = os.getenv("SNIFFER_DB_PATH")
DB_PATH = SNIFFER_DB_PATH

app = Flask(__name__)

# Initialize the database
init_db()

# Background job to run every 30 minutes
def scheduled_news_scan():
    print("[NewsSniffer] Running scheduled scan...")
    try:
        articles = fetch_all_google_topics() + fetch_zerohedge_rss()
        insert_articles(articles)
        print(f"[NewsSniffer] Inserted {len(articles)} articles.")
    except Exception as e:
        print(f"[NewsSniffer] Error during scan: {e}")

# Set up scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_news_scan, 'interval', minutes=30)
scheduler.start()

@app.route("/api/news", methods=["GET"])
def api_get_news():
    latest = get_latest_articles(limit=20)
    return jsonify(latest)

@app.route("/api/scan", methods=["POST"])
def run_manual_scan():
    scheduled_news_scan()
    return jsonify({"status": "Scan triggered"})

if __name__ == "__main__":
    scheduled_news_scan()  # Run immediately at startup
    app.run(host="0.0.0.0", port=5001)
