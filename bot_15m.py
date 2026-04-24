cat > bot_15m.py << 'EOF'
import time
import requests
import ccxt
import pandas as pd
from datetime import datetime

TOKEN = "8674379393:AAFDUHr-oF3FHJqIfhhXZKcsN3d37__mnms"
CHAT_ID = "755816889"

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
TIMEFRAME = "15m"
LIMIT = 100
OI_THRESHOLD_LONG = -0.8
OI_THRESHOLD_SHORT = 0.8
STOP_ATR_MULTIPLIER = 1.2
RR_RATIO = 3.0
SCAN_INTERVAL = 300

def send_tg(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print("Sent")
    except Exception as e:
        print(f"TG error: {e}")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

log("BOT STARTED")
send_tg("BOT STARTED (FVG+EMA+OI RR1:3)")

exchange = ccxt.binance({'enableRateLimit': True})
EOF
