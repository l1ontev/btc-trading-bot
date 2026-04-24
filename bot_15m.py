import time
import requests
import ccxt
import pandas as pd
from datetime import datetime

# ========== НАСТРОЙКИ ==========
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

# ========== TELEGRAM ==========
def send_tg(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print("✅ Сообщение отправлено")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

log("🚀 БОТ ЗАПУЩЕН")
send_tg("✅ Бот (FVG+EMA+OI, RR 1:3) запущен!")

# ========== BINANCE ==========
exchange = ccxt.binance({'enableRateLimit': True})

def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT)
        return pd.DataFrame(ohlcv, columns=['ts','o','h','l','c','v'])
    except Exception as e:
        log(f"Ошибка {symbol}: {e}")
        return None

def add_indicators(df):
    df['ema50'] = df['c'].ewm(50).mean()
    df['ema200'] = df['c'].ewm(200).mean()
    tr1 = df['h'] - df['l']
    tr2 = abs(df['h'] - df['c'].shift())
    tr3 = abs(df['l'] - df['c'].shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    return df

def find_fvg(df, idx):
    if idx < 2 or idx >= len(df) - 1:
        return None
    if df['h'].iloc[idx-1] < df['l'].iloc[idx+1]:
        return ('bullish', df['h'].iloc[idx-1], df['l'].iloc[idx+1'])
    if df['l'].iloc[idx-1] > df['h'].iloc[idx+1]:
        return ('bearish', df['h'].iloc[idx+1], df['l'].iloc[idx-1])
    return None

def get_oi_change(df, idx):
    if idx < 2:
        return 0
    now = df['v'].iloc[idx]
    past = df['v'].iloc[idx-2]
    return round((now - past) / past * 100, 2) if past != 0 else 0

def check_signals(df, symbol, oi, price, atr, ema50, ema200, idx):
    fvg = find_fvg(df, idx)
    if not fvg:
        return None

    if oi <= OI_THRESHOLD_LONG and ema50 > ema200 and fvg[0] == 'bullish' and fvg[1] <= price <= fvg[2]:
        stop = price - atr * STOP_ATR_MULTIPLIER
        risk = price - stop
        return {
            'type': 'LONG',
            'entry': price,
            'stop': stop,
            'tp': price + risk * RR_RATIO,
            'risk_pct': round(risk / price * 100, 2)
        }

    if oi >= OI_THRESHOLD_SHORT and ema50 < ema200 and fvg[0] == 'bearish' and fvg[1] <= price <= fvg[2]:
        stop = price + atr * STOP_ATR_MULTIPLIER
        risk = stop - price
        return {
            'type': 'SHORT',
            'entry': price,
            'stop': stop,
            'tp': price - risk * RR_RATIO,
            'risk_pct': round(risk / price * 100, 2)
        }

    return None

# ========== ОСНОВНОЙ ЦИКЛ ==========
log("Начинаю сканирование...")

while True:
    try:
        for symbol in SYMBOLS:
            df = get_data(symbol)
            if df is None or len(df) < 80:
                continue

            df = add_indicators(df)
            idx = len(df) - 1

            price = df['c'].iloc[idx]
            oi = get_oi_change(df, idx)
            ema50 = df['ema50'].iloc[idx]
            ema200 = df['ema200'].iloc[idx]
            atr = df['atr'].iloc[idx]

            signal = check_signals(df, symbol, oi, price, atr, ema50, ema200, idx)

            if signal:
                emoji = "🟢" if signal['type'] == 'LONG' else "🔴"
                msg = f"""{emoji} {signal['type']} {symbol}
💰 Вход: ${signal['entry']:.0f}
📉 Стоп: ${signal['stop']:.0f}
🎯 Тейк: ${signal['tp']:.0f}
📐 Риск: {signal['risk_pct']}%
🔥 OI: {oi:.1f}%
⚡ 1:3"""
                send_tg(msg)
                log(f"🔥 СИГНАЛ {symbol} {signal['type']}")

        time.sleep(SCAN_INTERVAL)

    except Exception as e:
        log(f"Ошибка: {e}")
        time.sleep(60)
