from flask import Flask, render_template, jsonify, request, abort
import os
from dotenv import load_dotenv
from fredapi import Fred
import yfinance as yf
from urllib.parse import unquote
from threading import Thread
import time as systime
from datetime import datetime
import json
import time
import redis
from dotenv import load_dotenv
from datetime import datetime, time 
from flask import request




load_dotenv()



# Initialize Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
rdb = redis.Redis.from_url(REDIS_URL)



app = Flask(__name__)

# Load .env for FRED key
load_dotenv()

def cache_setex(key, value, ttl):
    rdb.setex(key, ttl, json.dumps(value))



def fetch_and_cache_quotes(symbols):
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo", interval="1d", prepost=True)
            intraday = ticker.history(period="1d", interval="1m", prepost=True)

            if intraday.empty and hist.empty:
                print(f"[QUOTE SKIP] {symbol} has no intraday or historical data")
                continue

            if not intraday.empty:
                last = intraday.iloc[-1]
                open_ = float(intraday["Open"].iloc[0])
                price = float(last["Close"])
                high = float(intraday["High"].max())
                low = float(intraday["Low"].min())
                volume = int(last["Volume"]) if "Volume" in last else None
                extended = last.name.time() > time(16, 0) or last.name.time() < time(9, 30)
            else:
                last = hist.iloc[-1]
                open_ = float(hist["Open"].iloc[-1])
                price = float(last["Close"])
                high = float(hist["High"].max())
                low = float(hist["Low"].min())
                volume = int(hist["Volume"].iloc[-1]) if "Volume" in hist else None
                extended = False

            change = price - open_
            percent = (change / open_) * 100 if open_ else 0

            perf = {
                "1d": None,
                "5d": None,
                "1m": None,
                "6m": None,
                "ytd": None,
                "high_52w": None,
                "low_52w": None
            }

            if not hist.empty:
                close_series = hist["Close"].dropna()
                if len(close_series) > 1:
                    perf["1d"] = round(((price - close_series.iloc[-2]) / close_series.iloc[-2]) * 100, 2)
                if len(close_series) > 5:
                    perf["5d"] = round(((price - close_series.iloc[-6]) / close_series.iloc[-6]) * 100, 2)
                if len(close_series) > 21:
                    perf["1m"] = round(((price - close_series.iloc[-22]) / close_series.iloc[-22]) * 100, 2)
                perf["6m"] = round(((price - close_series.iloc[0]) / close_series.iloc[0]) * 100, 2)
                ytd_series = close_series.loc[close_series.index >= f"{datetime.utcnow().year}-01-01"]
                if not ytd_series.empty:
                    perf["ytd"] = round(((price - ytd_series.iloc[0]) / ytd_series.iloc[0]) * 100, 2)
                perf["high_52w"] = round(close_series.max(), 2)
                perf["low_52w"] = round(close_series.min(), 2)

            payload = {
                "price": price,
                "open": open_,
                "volume": volume,
                "change": round(change, 2),
                "percent": round(percent, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "extended": extended,
                "timestamp": datetime.utcnow().isoformat(),
                "performance": perf
            }

            cache_setex(f"quote:{symbol}", payload, 300)
            print(f"[REDIS:QUOTE] {symbol} = {price} ({'EXT' if extended else 'REG'})")

        except Exception as e:
            print(f"[QUOTE FAIL] {symbol}: {e}")


def cache_get(key):
    val = rdb.get(key)
    return json.loads(val) if val else None


FRED_API_KEY = os.getenv("FRED_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
fred = Fred(api_key=FRED_API_KEY)

# Load dashboard config
with open("config.json", "r") as f:
    config = json.load(f)

fred_cache = {}
history_cache = {}
fred_cache_ttl_minutes = 5
history_cache_ttl_hours = 6
composite_score_cache = {"value": None, "timestamp": None}

INDICATOR_SOURCES = config.get("indicator_sources", {})


def weighted_average(values, weights):
    try:
        zipped = [(v, w) for v, w in zip(values, weights) if v is not None]
        if not zipped:
            return None
        total_weight = sum(w for _, w in zipped)
        return round(sum(v * w for v, w in zipped) / total_weight, 2)
    except:
        return None
    
def normalize_group(values, scale=100):
    return [min(scale, max(0, v)) if v is not None else None for v in values]



def calculate_composite_score(data):
    weights = {
        "rates_and_curve": 0.15,  # Reduced weight
        "credit_and_volatility": 0.40,  # Increased weight
        "macro_indicators": 0.25,
        "flight_to_safety": 0.20,
    }
    rates_and_curve = normalize_rates_and_curve(data)
    credit_and_volatility = normalize_credit_and_volatility(data)
    macro_indicators = normalize_macro_indicators(data)
    flight_to_safety = normalize_flight_to_safety(data)

    composite_score = (
        weights["rates_and_curve"] * rates_and_curve +
        weights["credit_and_volatility"] * credit_and_volatility +
        weights["macro_indicators"] * macro_indicators +
        weights["flight_to_safety"] * flight_to_safety
    )

    # Log the components for debugging
    print(f"[Composite Score Calculation] Rates & Curve: {rates_and_curve}, "
          f"Credit & Volatility: {credit_and_volatility}, "
          f"Macro Indicators: {macro_indicators}, "
          f"Flight to Safety: {flight_to_safety}, "
          f"Composite Score: {composite_score}")

    return round(composite_score, 2)

def normalize_rates_and_curve(data):
    two_year = data.get("two_year_yield", 0)
    ten_year = data.get("ten_year_yield", 0)
    thirty_year = data.get("thirty_year_yield", 0)
    ust_2s10s = data.get("ust_2s10s_curve", 0)
    ust_3m10y = data.get("ust_3m10y_curve", 0)

    # Penalize near-zero or barely positive spreads
    curve_inversion_score = max(0, min(100, (0.5 - ust_2s10s) * 300))  # Increased sensitivity
    rates_score = max(0, min(100, (two_year + ten_year + thirty_year - 9) * 15))  # Penalize high yields more

    normalized_score = (curve_inversion_score + rates_score) / 2

    print(f"[Rates & Curve] Inputs: 2Y={two_year}, 10Y={ten_year}, 30Y={thirty_year}, "
          f"2s10s={ust_2s10s}, 3m10y={ust_3m10y} | Normalized Score: {normalized_score}")

    return normalized_score

def normalize_credit_and_volatility(data):
    vix = data.get("vix", 0)
    move_index = data.get("move_index", 0)
    vx_tlt = data.get("vx_tlt", 0)
    hy_credit_spread = data.get("hy_credit_spread", 0)

    # Adjust thresholds for VIX and HY spreads
    vix_score = max(0, min(100, (vix - 15) * 6))  # Increased sensitivity for VIX > 35
    move_score = max(0, min(100, (move_index - 100) * 2))  # MOVE > 150 = 100
    credit_spread_score = max(0, min(100, hy_credit_spread * 15))  # Increased sensitivity for HY spreads

    normalized_score = (vix_score + move_score + credit_spread_score + vx_tlt) / 4

    print(f"[Credit & Volatility] Inputs: VIX={vix}, MOVE={move_index}, VXTLT={vx_tlt}, "
          f"HY Spread={hy_credit_spread} | Normalized Score: {normalized_score}")

    return normalized_score

def normalize_macro_indicators(data):
    fed_funds_rate = data.get("fed_funds_rate", 0)
    cpi_yoy = data.get("cpi_yoy", 0)
    unemployment_rate = data.get("unemployment_rate", 0)
    retail_sales = data.get("retail_sales", 0)

    # Penalize elevated unemployment and flat retail sales
    unemployment_score = max(0, min(100, (unemployment_rate - 3) * 30))  # Increased sensitivity
    inflation_score = max(0, min(100, (cpi_yoy - 2) * 50))  # CPI > 2 = stress
    retail_sales_score = max(0, min(100, 100 - (retail_sales / 8000)))  # Penalize lower sales more

    normalized_score = (inflation_score + unemployment_score + retail_sales_score + fed_funds_rate) / 4

    print(f"[Macro Indicators] Inputs: Fed Funds={fed_funds_rate}, CPI YoY={cpi_yoy}, "
          f"Unemployment={unemployment_rate}, Retail Sales={retail_sales} | "
          f"Normalized Score: {normalized_score}")

    return normalized_score


def normalize_flight_to_safety(data):
    gold_price = data.get("gold_price", 0)
    bitcoin_price = data.get("bitcoin_price", 0)
    sofr_spread = data.get("sofr_spread", 0)

    # Penalize rising gold and falling Bitcoin more heavily
    gold_score = max(0, min(100, (gold_price - 1800) / 1.5))  # Increased sensitivity for gold > 2000
    bitcoin_score = max(0, min(100, (60000 - bitcoin_price) / 400))  # Penalize falling BTC more

    normalized_score = (gold_score + bitcoin_score) / 2

    print(f"[Flight to Safety] Inputs: Gold={gold_price}, Bitcoin={bitcoin_price}, "
          f"SOFR Spread={sofr_spread} | Normalized Score: {normalized_score}")

    return normalized_score


def fetch_fred_series(series_ids):
    now = datetime.utcnow()
    for sid in series_ids:
        try:
            series = fred.get_series(sid)
            if sid == "CPIAUCSL" and len(series) >= 13:
                value = ((series.iloc[-1] - series.iloc[-13]) / series.iloc[-13]) * 100
            else:
                value = float(series.iloc[-1])
            cache_setex(f"fred:{sid}", {"value": round(value, 4), "timestamp": now.isoformat()}, 300)
            print(f"[REDIS:FRED] Cached {sid}: {value}")
        except Exception as e:
            print(f"[FRED] Error: {sid} - {e}")


def prefetch_history():
    durations = {
        "7d": {"period": "7d", "interval": "1d", "ttl": 21600},
        "30d": {"period": "1mo", "interval": "1d", "ttl": 21600},
        "90d": {"period": "3mo", "interval": "1d", "ttl": 21600}
    }

    # FRED + FRED Spread
    for name, source in config.get("indicator_sources", {}).items():
        try:
            if source[0] in ["fred", "fred_yoy"]:
                sid = source[1]
                series = fred.get_series(sid).dropna()
                for d in durations:
                    trimmed = series.tail(7 if d == "7d" else 30 if d == "30d" else 90)
                    values = [
                        {"date": str(date.date()), "value": round(val, 4)}
                        for date, val in trimmed.items()
                    ]
                    rdb.setex(f"history:{name}:{d}", durations[d]["ttl"], json.dumps(values))
                    print(f"[REDIS:HISTORY] {name}:{d} updated")
            elif source[0] == "fred_spread":
                sid = source[1][1]
                series = fred.get_series(sid).dropna()
                for d in durations:
                    trimmed = series.tail(7 if d == "7d" else 30 if d == "30d" else 90)
                    values = [
                        {"date": str(date.date()), "value": round(val, 4)}
                        for date, val in trimmed.items()
                    ]
                    rdb.setex(f"history:{name}:{d}", durations[d]["ttl"], json.dumps(values))
                    print(f"[REDIS:HISTORY] {name}:{d} updated")
        except Exception as e:
            print(f"[History:Fred] Error for {name}: {e}")

    # Yahoo tickers from redis_quotes
    for symbol in config.get("redis_quotes", []):
        try:
            ticker = yf.Ticker(symbol)
            for d in durations:
                hist = ticker.history(period=durations[d]["period"], interval=durations[d]["interval"])
                if hist.empty:
                    continue
                values = [
                    {"date": str(idx.date()), "value": round(val, 2)}
                    for idx, val in hist["Close"].dropna().items()
                ]
                rdb.setex(f"history:{symbol}:{d}", durations[d]["ttl"], json.dumps(values))
                print(f"[REDIS:HISTORY] {symbol}:{d} updated")
        except Exception as e:
            print(f"[History:Yahoo] Error for {symbol}: {e}")


def start_background_updaters():
    series_ids = set()
    for src in INDICATOR_SOURCES.values():
        if src[0] == "fred":
            series_ids.add(src[1])
        elif src[0] == "fred_spread":
            series_ids.update(src[1])
        elif src[0] == "fred_yoy":
            series_ids.add(src[1])
        elif src[0] == "mock_composite":
            series_ids.update(src[1])

    quote_symbols = config.get("redis_quotes", [])

    def loop_fred():
        while True:
            fetch_fred_series(series_ids)
            systime.sleep(fred_cache_ttl_minutes * 60)

    def loop_history():
        while True:
            prefetch_history()
            systime.sleep(history_cache_ttl_hours * 3600)

    def loop_composite_score():
        while True:
            update_composite_score()
            systime.sleep(fred_cache_ttl_minutes * 60)

    def loop_quotes():
        while True:
            fetch_and_cache_quotes(quote_symbols)
            systime.sleep(10)

    # Initial load (boot warmup)
    fetch_fred_series(series_ids)
    prefetch_history()
    fetch_and_cache_quotes(quote_symbols)
    update_composite_score()

    Thread(target=loop_fred, daemon=True).start()
    Thread(target=loop_history, daemon=True).start()
    Thread(target=loop_composite_score, daemon=True).start()
    Thread(target=loop_quotes, daemon=True).start()


def fetch_quote(symbol):
    import requests
    import json

    key = f"quote:{symbol}"
    cached = rdb.get(key)
    if cached:
        return json.loads(cached)

    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        data = res.json()
        meta = data["chart"]["result"][0]["meta"]

        price = meta.get("regularMarketPrice", 0.0)
        previous_close = meta.get("chartPreviousClose", 0.0)

        payload = {
            "price": price,
            "previous_close": previous_close
        }
        rdb.setex(key, 60, json.dumps(payload))
        return payload

    except Exception as e:
        return {"error": str(e), "price": 0.0, "previous_close": 0.0}


def update_composite_score():
    try:
        def get_redis_val(code):
            result = cache_get(f"fred:{code}")
            return result["value"] if result else None

        # --- Rates & Curve ---
        dgs2 = get_redis_val("DGS2")
        dgs10 = get_redis_val("DGS10")
        dgs30 = get_redis_val("DGS30")
        tb3ms = get_redis_val("TB3MS")

        avg_yield = sum(filter(None, [dgs2, dgs10, dgs30])) / len([v for v in [dgs2, dgs10, dgs30] if v is not None]) if all([dgs2, dgs10, dgs30]) else None
        ust_2s10s = dgs10 - dgs2 if dgs10 and dgs2 else None

        curve_score = min(100, max(0, -200 * min(0, ust_2s10s))) if ust_2s10s is not None else None
        rate_score = min(100, max(0, (avg_yield - 3.5) * 25)) if avg_yield is not None else None

        rates_curve = (curve_score + rate_score) / 2 if curve_score is not None and rate_score is not None else None

        print(f"[Rates & Curve] avg_yield={avg_yield}, ust_2s10s={ust_2s10s}, curve_score={curve_score}, rate_score={rate_score}, rates_curve={rates_curve}")

        # --- Credit & Volatility ---
        vix = (cache_get("quote:^VIX") or {}).get("price")
        move = (cache_get("quote:^MOVE") or {}).get("price")


        hy = get_redis_val("BAMLH0A0HYM2EY")

        vix_score = min(100, max(0, (vix - 15) * 5)) if vix is not None else None
        move_score = min(100, max(0, (move - 90) * 2)) if move is not None else None
        hy_score = min(100, max(0, (hy - 3) * 20)) if hy is not None else None

        credit_vol = sum([s for s in [vix_score, move_score, hy_score] if s is not None]) / len([s for s in [vix_score, move_score, hy_score] if s is not None]) if any([vix_score, move_score, hy_score]) else None

        print(f"[Credit & Volatility] vix={vix}, move={move}, hy={hy}, vix_score={vix_score}, move_score={move_score}, hy_score={hy_score}, credit_vol={credit_vol}")

        # --- Macro Indicators ---
        ffr = get_redis_val("FEDFUNDS")
        cpi = get_redis_val("CPIAUCSL")
        unrate = get_redis_val("UNRATE")
        retail = get_redis_val("RSAFS")

        ffr_score = min(100, max(0, (ffr - 2.5) * 20)) if ffr is not None else None
        cpi_score = min(100, max(0, (cpi - 2.0) * 25)) if cpi is not None else None
        unrate_score = min(100, max(0, (unrate - 4) * 20)) if unrate is not None else None
        retail_score = min(100, max(0, 100 - (retail / 10000 * 100))) if retail is not None else None

        macro = sum([s for s in [ffr_score, cpi_score, unrate_score, retail_score] if s is not None]) / len([s for s in [ffr_score, cpi_score, unrate_score, retail_score] if s is not None]) if any([ffr_score, cpi_score, unrate_score, retail_score]) else None

        print(f"[Macro Indicators] ffr={ffr}, cpi={cpi}, unrate={unrate}, retail={retail}, ffr_score={ffr_score}, cpi_score={cpi_score}, unrate_score={unrate_score}, retail_score={retail_score}, macro={macro}")

        # --- Flight to Safety ---
        gold = cache_get("quote:GC=F") or {}
        btc = cache_get("quote:BTC-USD") or {}
        gold = gold.get("price")
        btc = btc.get("price")


        gold_score = min(100, max(0, (gold - 1800) / 2)) if gold is not None else None
        btc_score = min(100, max(0, ((btc - 20000) / 400) * 10)) if btc is not None else None

        safety = (gold_score + btc_score) / 2 if gold_score is not None and btc_score is not None else None

        print(f"[Flight to Safety] gold={gold}, btc={btc}, gold_score={gold_score}, btc_score={btc_score}, safety={safety}")

        # --- Composite Score ---
        components = {
            "Rates & Curve": rates_curve,
            "Credit & Volatility": credit_vol,
            "Macro": macro,
            "Flight to Safety": safety,
        }
        weights = {
            "Rates & Curve": 0.25,
            "Credit & Volatility": 0.30,
            "Macro": 0.25,
            "Flight to Safety": 0.20,
        }

        composite = round(sum(components[k] * weights[k] for k in components if components[k] is not None), 2)
        composite_score_cache["value"] = composite
        cache_setex("composite_score", {
            "value": composite,
            "components": components,
            "weights": weights,
            "inputs": {
                "rates_and_curve": {
                    "dgs2": dgs2,
                    "dgs10": dgs10,
                    "dgs30": dgs30,
                    "tb3ms": tb3ms,
                    "avg_yield": avg_yield,
                    "ust_2s10s": ust_2s10s,
                    "curve_score": curve_score,
                    "rate_score": rate_score,
                    "final": rates_curve
                },
                "credit_and_volatility": {
                    "vix": vix,
                    "move": move,
                    "hy": hy,
                    "vix_score": vix_score,
                    "move_score": move_score,
                    "hy_score": hy_score,
                    "final": credit_vol
                },
                "macro_indicators": {
                    "ffr": ffr,
                    "cpi": cpi,
                    "unrate": unrate,
                    "retail": retail,
                    "ffr_score": ffr_score,
                    "cpi_score": cpi_score,
                    "unrate_score": unrate_score,
                    "retail_score": retail_score,
                    "final": macro
                },
                "flight_to_safety": {
                    "gold": gold,
                    "btc": btc,
                    "gold_score": gold_score,
                    "btc_score": btc_score,
                    "final": safety
                }
            }
        }, 300)


        print(f"[Composite Score] components={components}, weights={weights}, composite={composite}")

        # Redis history
        hist_key = "history:Stress Composite Score"
        prev = cache_get(hist_key) or []
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if not any(p["date"] == today for p in prev):
            prev.append({"date": today, "value": composite})
            prev = prev[-7:]
            cache_setex(hist_key, prev, 86400 * 7)
            print(f"[REDIS:HISTORY] Stress Composite Score updated")

    except Exception as e:
        print("[Composite Score] Error:", str(e))

def classify_risk_level(score):
    if score <= 20:
        return {
            "range": "0–20",
            "label": "Ultra Risk-On",
            "emoji": "🌈",
            "description": "Euphoria, melt-up, extreme greed"
        }
    elif score <= 40:
        return {
            "range": "21–40",
            "label": "Risk-On",
            "emoji": "😎",
            "description": "Constructive tone, bullish momentum"
        }
    elif score <= 60:
        return {
            "range": "41–60",
            "label": "Neutral / Transition",
            "emoji": "😐",
            "description": "Mixed or indecisive environment"
        }
    elif score <= 80:
        return {
            "range": "61–80",
            "label": "Risk-Off",
            "emoji": "⚠️",
            "description": "Defensive tone, rising volatility/stress"
        }
    else:
        return {
            "range": "81–100",
            "label": "Crisis Mode",
            "emoji": "🚨",
            "description": "Panic, safe-haven flight, system-wide risk"
        }

def fetch_latest_tweets(username="zerohedge", count=5):
    try:
        client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
        user = client.get_user(username=username)
        tweets = client.get_users_tweets(user.data.id, max_results=count)

        tweet_data = []
        for tweet in tweets.data:
            tweet_data.append({
                "text": tweet.text,
                "created_at": str(tweet.created_at) if tweet.created_at else "N/A"
            })
        return tweet_data
    except Exception as e:
        print(f"[Twitter] Error fetching tweets: {e}")
        return []




@app.route("/api/indicator/<path:indicator_name>")

def get_indicator_data(indicator_name):
    indicator_name = unquote(indicator_name)
    key = indicator_name.strip().lower()
    source_map = {k.lower(): v for k, v in INDICATOR_SOURCES.items()}
    source_info = source_map.get(key)

    if not source_info:
        return jsonify({"name": indicator_name, "value": None, "error": "No source"})

    try:
        if indicator_name == "Stress Composite Score":
            return get_composite_score()

        redis_key = None
        if source_info[0] in ["fred", "fred_yoy"]:
            redis_key = f"fred:{source_info[1]}"
        elif source_info[0] == "fred_spread":
            s1, s2 = source_info[1]
            v1 = cache_get(f"fred:{s1}")
            v2 = cache_get(f"fred:{s2}")
            if v1 and v2:
                spread = round(v2["value"] - v1["value"], 4)
                return jsonify({"name": indicator_name, "value": spread})
            else:
                return jsonify({"name": indicator_name, "value": None})
        elif source_info[0] == "yahoo":
            redis_key = f"history:{indicator_name}"

        if redis_key:
            result = cache_get(redis_key)
            if result:
                if isinstance(result, list) and result and "value" in result[-1]:
                    value = result[-1]["value"]
                else:
                    value = result.get("value") or result.get("price")
                return jsonify({"name": indicator_name, "value": value})

        return jsonify({"name": indicator_name, "value": None})
    except Exception as e:
        return jsonify({"name": indicator_name, "value": None, "error": str(e)})




@app.route("/api/history/<path:indicator_name>")
def get_indicator_history(indicator_name):
    from urllib.parse import unquote
    indicator_name = unquote(indicator_name)
    range_param = request.args.get("range", "7d").lower()
    if range_param not in ["7d", "30d", "90d"]:
        range_param = "7d"

    redis_key = f"history:{indicator_name}:{range_param}"
    try:
        data = cache_get(redis_key)
        if data and isinstance(data, list):
            return jsonify({"values": data})
        else:
            return jsonify({"values": []})
    except Exception as e:
        return jsonify({"error": str(e), "values": []})



@app.route("/dashboard")
def dashboard():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    all_baskets = config.get("baskets", [])
    return render_template("dashboard.html", config=config, all_baskets=all_baskets)



@app.route("/")
def home():
    return render_template("home.html")

@app.route("/api/status")
def server_status():
    try:
        # Perform a lightweight check (e.g., return a success message)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    

@app.route("/api/composite_score")
def get_composite_score():
    try:
        if composite_score_cache["value"] is None:
            update_composite_score()

        if composite_score_cache["value"] is None:
            return jsonify({"error": "Composite score not available"}), 503

        return jsonify({
            "composite_score": composite_score_cache["value"],
            "details": {
                "rates_and_curve": composite_score_cache.get("rates_and_curve"),
                "credit_and_volatility": composite_score_cache.get("credit_and_volatility"),
                "macro_indicators": composite_score_cache.get("macro_indicators"),
                "flight_to_safety": composite_score_cache.get("flight_to_safety"),
            },
            "risk_classification": classify_risk_level(composite_score_cache["value"])
        })
    except Exception as e:
        print(f"[Composite Score API] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/overview")
def market_overview():
    tickers = config.get("market_overview", [])

    # Safe fallback
    score_data = cache_get("composite_score") or {}
    sniff_score = score_data.get("value", "N/A")
    sniff_breakdown = score_data.get("components", {
        "Rates & Curve": "N/A",
        "Credit & Volatility": "N/A",
        "Macro": "N/A",
        "Flight to Safety": "N/A"
    })

    return render_template("overview.html",
                           tickers=tickers,
                           sniff_score=sniff_score,
                           sniff_breakdown=sniff_breakdown)

@app.route("/api/quote/<symbol>")
def quote_api(symbol):
    key = f"quote:{symbol}"
    cached = cache_get(key)
    if cached and "price" in cached:
        return jsonify({
            "price": cached["price"],
            "change": cached.get("change"),
            "percent": cached.get("percent"),
            "high": cached.get("high"),
            "low": cached.get("low"),
            "open": cached.get("open"),
            "volume": cached.get("volume"),
            "timestamp": cached.get("timestamp"),
            "performance": cached.get("performance"),
            "source": "redis"
        })

    # fallback: fetch fresh
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d", interval="1d")
        if data.empty:
            return jsonify({"error": "No data"}), 404

        close = float(data["Close"].iloc[-1])
        open_ = float(data["Open"].iloc[-1])
        high = float(data["High"].iloc[-1])
        low = float(data["Low"].iloc[-1])
        volume = int(data["Volume"].iloc[-1]) if "Volume" in data.columns else 0
        change = close - open_
        percent = (change / open_) * 100 if open_ else 0

        result = {
            "price": close,
            "change": round(change, 2),
            "percent": round(percent, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "open": open_,
            "volume": volume,
            "timestamp": datetime.utcnow().isoformat(),
            "performance": None  # not calculated in fallback
        }

        cache_setex(key, result, 300)
        return jsonify(result)
    except Exception as e:
        print(f"[QUOTE API ERROR] {symbol}: {e}")
        return jsonify({"error": "Fetch failed"}), 500


@app.route("/details/<symbol>")
def details(symbol):
    return render_template("details.html", symbol=symbol)

@app.route("/api/intraday/<path:symbol>")
def get_intraday_chart(symbol):
    import requests
    key = f"intraday:{symbol}"
    cached = rdb.get(key)
    if cached:
        return jsonify(json.loads(cached))

    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=5m&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        data = res.json()
        rdb.setex(key, 60, json.dumps(data))  # 60 seconds TTL
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/methodology")
def methodology():
    return render_template("methodology.html")

@app.route("/api/sniff_score_math")
def sniff_score_math():
    data = cache_get("composite_score")
    if not data:
        return jsonify({"error": "No score data"}), 404
    return jsonify(data)


@app.route("/baskets")
def baskets_dropdown():
    # Load the basket configuration from config.json
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        config_data = json.load(f)

    # In our nested JSON, baskets is an array of basket objects.
    basket_list = config_data.get("baskets", [])
    return render_template("baskets_dropdown.html", baskets=basket_list)





@app.route("/baskets/<basket_name>")
def show_baskets(basket_name):
    """
    Render the basket view for a given basket_name.

    Loads the basket configuration from config.json,
    selects the basket matching basket_name,
    fetches live quotes for each stock in the basket,
    computes current values and allocations,
    and calculates a total return percentage.

    :param basket_name: The identifier for the basket (e.g., "trump")
    :return: Rendered template for the basket page or a 404 error if not found.
    """


    # Load the basket configuration from config.json
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
    except Exception as e:
        return f"Error loading basket configuration: {e}", 500

    # Search for the basket with the matching name
    baskets = config_data.get("baskets", [])
    basket_data = next((b for b in baskets if b.get("name") == basket_name), None)
    if basket_data is None:
        abort(404, description=f"No basket found for '{basket_name}'")

    # Process stocks in the selected basket
    for stock in basket_data.get("stocks", []):
        try:
            quote = fetch_quote(stock["ticker"])  # Should return {"price": float}
            current_price = quote.get("price", 0.0)
        except Exception:
            current_price = 0.0
        stock["current_price"] = current_price
        stock["current_value"] = current_price * stock.get("shares", 0)

        # Optional: handle missing initial investment gracefully
        initial_investment = stock.get("initial_investment", 0.0)
        stock["return_percent"] = ((stock["current_value"] - initial_investment) / initial_investment * 100) if initial_investment else 0.0

        # Get prior close (if available from quote)
        previous_close = quote.get("previous_close", None)
        if previous_close:
            stock["change_percent"] = ((current_price - previous_close) / previous_close * 100) if previous_close else 0.0
        else:
            stock["change_percent"] = 0.0

    # Calculate total current value of the basket
    total_value = sum(stock.get("current_value", 0.0) for stock in basket_data.get("stocks", []))

    # Add allocation percentage to each stock
    for stock in basket_data.get("stocks", []):
        stock_value = stock.get("current_value", 0.0)
        stock["allocation_percent"] = (stock_value / total_value * 100) if total_value else 0.0

    # Calculate total initial investment and total return %
    initial_total = sum(stock.get("initial_investment", 0.0) for stock in basket_data.get("stocks", []))
    total_return_percent = ((total_value - initial_total) / initial_total * 100) if initial_total else 0.0

    # Render the basket page
    return render_template(
        "ned_baskets.html",
        trump_basket=basket_data.get("stocks", []),
        total_value=total_value,
        basket_info=basket_data,
        total_return_percent=total_return_percent,
        all_baskets=baskets
    )



if __name__ == "__main__":
    start_background_updaters()
    app.run(host="127.0.0.1", port=5000)
