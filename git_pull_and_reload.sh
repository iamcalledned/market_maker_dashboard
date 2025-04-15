#!/bin/bash
cd /home/ned/projects/market_maker_dashboard || exit 1
echo "[DEPLOY] Pulling latest code..."
git pull origin main

# Optional: restart Flask app if needed
# pkill -f "flask run"
# nohup flask run --host=127.0.0.1 --port=5000 &

# Or if you're using Apache WSGI:
# touch /var/www/iamcalledned.ai/wsgi.py
