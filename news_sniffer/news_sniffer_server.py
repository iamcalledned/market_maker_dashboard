from flask import Flask, request, jsonify

from apscheduler.schedulers.background import BackgroundScheduler
from fetcher import fetch_all_google_topics, fetch_zerohedge_rss
from database import init_db, insert_articles, get_latest_articles
import os
from dotenv import load_dotenv
from flask import request, jsonify
from newspaper import Article
from datetime import datetime
from database import insert_articles
from scraper import fetch_full_text_from_archive_md

from scraper import fetch_full_text_with_playwright, extract_text_from_html


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

@app.route("/api/add_url", methods=["POST", "GET"])
def add_url():
    if request.method == "POST":
        data = request.get_json()
        url = data.get("url") if data else None
    else:  # GET method
        url = request.args.get("url")

    if not url:
        return jsonify({"error": "Missing URL"}), 400

    

    try:
        if "archive.md" in url:
            full_text = fetch_full_text_from_archive_md(url)
            headline = full_text.split("\n")[0][:140] if full_text else "Untitled"
            snippet = full_text
            source = "https://archive.md"

        else:
            article = Article(url)
            article.download()
            article.parse()
            headline = article.title
            snippet = article.text[:500]
            full_text = article.text
            source = article.source_url or "external"

        article_data = [{
            "headline": headline,
            "url": url,
            "source": source,
            "snippet": snippet,
            "full_text": full_text,
            "timestamp": datetime.utcnow().isoformat()
        }]

        insert_articles(article_data)
        return jsonify({"status": "saved", "article": article_data[0]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    scheduled_news_scan()  # Run immediately at startup
    app.run(host="0.0.0.0", port=5001)
