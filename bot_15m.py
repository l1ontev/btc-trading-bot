import time
import requests
import ccxt
import pandas as pd
from datetime import datetime

TOKEN = "8674379393:AAFDUHr-oF3FHJqIfhhXZKcsN3d37__mnms"
CHAT_ID = "755816889"

def send_tg(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print("✅ Сообщение отправлено")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

log("🚀 БОТ 15m ЗАПУЩЕН (ПОРОГ OI: 0.8%)")
send_tg("✅ Бот перезапущен с порогом OI 0.8%")

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
OI_THRESHOLD = 0.8
LIMIT = 100

exchange = ccxt.binance({'enableRateLimit': True})

def get_data(symbol, limit=LIMIT):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=limit)
        return pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    except Exception as e:
        log(f"Ошибка {symbol}: {e}")
        return None

def get_oi(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=4)
        if len(ohlcv) < 4:
            return 0
        now = ohlcv[-1][5]
        past = ohlcv[-3][5]
        if past == 0:
            return 0
        return round((now - past) / past * 100, 2)
    except:
        return 0

def get_price(symbol):
    try:
        return exchange.fetch_ticker(symbol)['last']
    except:
        return 0

def add_indicators(df):
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean()
    return df

def find_fvg(df):
    if len(df) < 10:
        return None
    for offset in [3, 4, 5]:
        i = len(df) - offset
        if i < 2 or i >= len(df) - 1:
            continue
        try:
            if df['high'].iloc[i-1] < df['low'].iloc[i+1]:
                return ('bullish', df['high'].iloc[i-1], df['low'].iloc[i+1])
            elif df['low'].iloc[i-1] > df['high'].iloc[i+1]:
                return ('bearish', df['high'].iloc[i+1], df['low'].iloc[i-1])
        except:
            continue
    return None

def check_signals(df, symbol, oi, price):
    if df is None or len(df) < 30:
        return None
    
    ema50 = df['EMA50'].iloc[-1]
    ema200 = df['EMA200'].iloc[-1]
    atr = df['ATR'].iloc[-1]
    
    if oi <= -OI_THRESHOLD and ema50 > ema200:
        fvg = find_fvg(df)
        if fvg and fvg[0] == 'bullish' and fvg[1] <= price <= fvg[2]:
            stop = price - atr * 1.2
            risk = (price - stop) / price * 100
            if 0.5 <= risk <= 2.5:
                return {'type': 'LONG', 'trigger': 'A (FVG)', 'entry': price, 'stop': stop, 'tp': price + (price - stop) * 1.5, 'risk': f"{risk:.1f}%", 'oi': f"{oi:.1f}%"}
    
    if oi >= OI_THRESHOLD and ema50 < ema200:
        fvg = find_fvg(df)
        if fvg and fvg[0] == 'bearish' and fvg[1] <= price <= fvg[2]:
            stop = price + atr * 1.2
            risk = (stop - price) / price * 100
            if 0.5 <= risk <= 2.5:
                return {'type': 'SHORT', 'trigger': 'A (FVG)', 'entry': price, 'stop': stop, 'tp': price - (stop - price) * 1.5, 'risk': f"{risk:.1f}%", 'oi': f"{oi:.1f}%"}
    
    return None

log("Начинаю сканирование...")

while True:
    try:
        for symbol in SYMBOLS:
            df = get_data(symbol)
            if df is None:
                continue
            df = add_indicators(df)
            oi = get_oi(symbol)
            price = get_price(symbol)
            signal = check_signals(df, symbol, oi, price)
            if signal:
                emoji = "🟢" if signal['type'] == 'LONG' else "🔴"
                msg = f"""{emoji} СИГНАЛ {signal['type']}

{symbol} | {signal['trigger']}
💰 Вход: ${signal['entry']:.0f}
📉 Стоп: ${signal['stop']:.0f}
🎯 Тейк: ${signal['tp']:.0f}
📐 Риск: {signal['risk']}
🔥 OI: {signal['oi']}%"""
                send_tg(msg)
                log(f"🔥 СИГНАЛ {symbol} {signal['type']}")
        time.sleep(300)
    except Exception as e:
        log(f"Ошибка: {e}")
        time.sleep(60)
