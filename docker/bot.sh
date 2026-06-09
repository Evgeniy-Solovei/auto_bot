#!/bin/sh
set -e

python - <<'PYWAIT'
import os
import time
import urllib.error
import urllib.request

base_url = os.getenv("BOT_API_BASE_URL", "http://web:8000/api").rstrip("/")
url = f"{base_url}/categories/"
api_key = os.getenv("INTERNAL_API_KEY", "")
headers = {"X-API-Key": api_key} if api_key else {}

for attempt in range(1, 61):
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            if response.status < 500:
                print("Django API is ready")
                break
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Waiting for Django API ({attempt}/60): {exc}")
        time.sleep(2)
else:
    raise SystemExit("Django API is not available")
PYWAIT

exec python bot.py
