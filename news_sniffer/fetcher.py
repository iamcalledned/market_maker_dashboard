import os
import requests
import feedparser
from dotenv import load_dotenv
from datetime import datetime
import time

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

NEWS_QUERIES = {
    "Yield Curve / Rates": "yield curve inversion OR 2s10s spread",
    "Credit Stress": "high yield spreads OR credit risk OR bond market stress",
    "Volatility": "VIX spike OR MOVE Index OR bond volatility",
    "Macro Indicators": "CPI report OR retail sales OR unemployment rate",
    "Flight to Safety": "gold surges OR bitcoin breakout OR flight to safety",
    "Fed / Policy Shift": "Powell speech OR FOMC minutes OR rate cut odds",
    "Trade / China": "Trump tariffs OR China retaliation OR supply chain risks"
}

def fetch_google_results(query, num_results=3):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": num_results
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    data = res.json()

    results = []
    for item in data.get("items", []):
        results.append({
            "headline": item.get("title"),
            "url": item.get("link"),
            "source": item.get("displayLink"),
            "snippet": item.get("snippet"),
            "timestamp": datetime.utcnow().isoformat()
        })

    return results


def fetch_all_google_topics():
    all_articles = []
    for category, query in NEWS_QUERIES.items():
        print(f"[Fetcher] Querying category: {category}")
        try:
            articles = fetch_google_results(query, num_results=3)
            all_articles.extend(articles)
            time.sleep(2)  # ← ✅ Slow down!
        except Exception as e:
            print(f"[Fetcher] Error fetching results for '{category}': {e}")
            time.sleep(4)  # ← ⏱ Backoff on error to cool down
    return all_articles


def fetch_zerohedge_rss():
    feed_url = "https://feeds.feedburner.com/zerohedge/feed"
    feed = feedparser.parse(feed_url)
    results = []

    for entry in feed.entries[:10]:
        results.append({
            "headline": entry.get("title"),
            "url": entry.get("link"),
            "source": "ZeroHedge",
            "snippet": entry.get("summary", ""),
            "timestamp": entry.get("published", datetime.utcnow().isoformat())
        })

    return results
