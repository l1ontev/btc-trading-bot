import time
import requests
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = "8674379393:AAFDUHr-oF3FHJqIfhhXZKcsN3d37__mnms"
CHAT_ID = "755816889"

TIMEFRAME = "4h"
LIMIT = 200
SCAN_INTERVAL = 600

# ========== НАСТРОЙКИ ДЛЯ КАЖДОЙ МОНЕТЫ ==========
SYMBOLS_CONFIG = [
    {
        "symbol": "BTC/USDT",
        "impulse_pct": 2.0,
        "impulse_period": 10,
        "fib_level": 0.618,
        "oi_threshold": -1.0,
        "stop_mult": 1.5,
        "rr_ratio": 2.0,
        "winrate": 90.0,
        "return": 38.6
    },
    {
        "symbol": "ETH/USDT",
        "impulse_pct": 2.0,
        "impulse_period": 10,
        "fib_level": 0.5,
        "oi_threshold": -1.0,
        "stop_mult": 2.0,
        "rr_ratio": 2.0,
        "winrate": 68.8,
        "return": 99.4
    }
]

RISK_PER_TRADE = 3.0

# ========== ХРАНИЛИЩЕ ПОСЛЕДНИХ СИГНАЛОВ ==========
last_signals = {}

def send_tg(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print("Sent")
    except Exception as e:
        print(f"TG error: {e}")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

log("BOT STARTED (BTC+ETH, Impulse+Fibo+OI)")
send_tg("BTC+ETH Bot (Impulse+Fibo+OI) started!")

exchange = ccxt.binance({'enableRateLimit': True})

def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT)
        df = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        return df
    except Exception as e:
        log(f"Data error {symbol}: {e}")
        return None

def add_indicators(df):
    tr1 = df['h'] - df['l']
    tr2 = abs(df['h'] - df['c'].shift())
    tr3 = abs(df['l'] - df['c'].shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    return df

def get_oi_change(df, idx, lookback=2):
    if idx < lookback:
        return 0
    now = df['v'].iloc[idx]
    past = df['v'].iloc[idx-lookback]
    return round((now - past) / past * 100, 2) if past != 0 else 0

def find_impulse_up(df, idx, impulse_pct, impulse_period):
    if idx < impulse_period:
        return None, None
    start = idx - impulse_period
    start_price = df['c'].iloc[start]
    end_price = df['c'].iloc[idx]
    change = (end_price - start_price) / start_price * 100
    if change >= impulse_pct:
        return start, idx
    return None, None

def find_fib_level(df, impulse_start, impulse_end, fib_level):
    if impulse_start is None or impulse_end is None:
        return None
    high = df['h'].iloc[impulse_start:impulse_end+1].max()
    low = df['l'].iloc[impulse_start:impulse_end+1].min()
    range_ = high - low
    return high - range_ * fib_level

def check_correction(df, idx, impulse_start, impulse_end, fib_level):
    fib_price = find_fib_level(df, impulse_start, impulse_end, fib_level)
    if fib_price is None:
        return None
    
    current_price = df['c'].iloc[idx]
    if abs(current_price - fib_price) / fib_price > 0.003:
        return None
    
    body = abs(df['c'].iloc[idx] - df['o'].iloc[idx])
    if body == 0:
        return None
    lower_wick = min(df['o'].iloc[idx], df['c'].iloc[idx]) - df['l'].iloc[idx]
    
    if lower_wick > body * 1.5:
        return fib_price
    return None

def is_duplicate_signal(symbol, entry_price, tolerance_pct=1.0):
    if symbol not in last_signals:
        return False
    
    last_entry = last_signals[symbol]['entry_price']
    last_time = last_signals[symbol]['timestamp']
    current_time = datetime.now()
    
    if (current_time - last_time).total_seconds() > 24 * 3600:
        return False
    
    price_diff_pct = abs(entry_price - last_entry) / last_entry * 100
    return price_diff_pct < tolerance_pct

def save_signal(symbol, entry_price):
    last_signals[symbol] = {
        'entry_price': entry_price,
        'timestamp': datetime.now()
    }

def check_signal(df, cfg):
    if len(df) < cfg['impulse_period'] + 30:
        return None
    
    idx = len(df) - 1
    price = df['c'].iloc[idx]
    oi = get_oi_change(df, idx)
    atr = df['atr'].iloc[idx] if not pd.isna(df['atr'].iloc[idx]) else 0
    
    if atr == 0:
        return None
    
    imp_start, imp_end = find_impulse_up(df, idx, cfg['impulse_pct'], cfg['impulse_period'])
    if imp_start is None:
        return None
    
    if oi > cfg['oi_threshold']:
        return None
    
    fib_price = check_correction(df, idx, imp_start, imp_end, cfg['fib_level'])
    if fib_price is None:
        return None
    
    entry = price
    stop = entry - atr * cfg['stop_mult']
    risk = entry - stop
    
    if risk <= 0:
        return None
    
    tp = entry + risk * cfg['rr_ratio']
    risk_pct = round(risk / entry * 100, 2)
    impulse_change = (df['c'].iloc[imp_end] - df['c'].iloc[imp_start]) / df['c'].iloc[imp_start] * 100
    
    return {
        'entry': entry,
        'stop': stop,
        'tp': tp,
        'risk_pct': risk_pct,
        'oi': oi,
        'fib_price': fib_price,
        'impulse_change': impulse_change
    }

log("Starting scan...")

while True:
    try:
        for cfg in SYMBOLS_CONFIG:
            symbol = cfg['symbol']
            df = get_data(symbol)
            if df is None or len(df) < 80:
                continue
            
            df = add_indicators(df)
            signal = check_signal(df, cfg)
            
            if signal:
                if is_duplicate_signal(symbol, signal['entry']):
                    log(f"Skip duplicate {symbol} at {signal['entry']:.0f}")
                    continue
                
                save_signal(symbol, signal['entry'])
                
                emoji = "🟢"
                fib_emoji = "🔸" if cfg['fib_level'] == 0.618 else "🔹"
                msg = f"""{emoji} LONG {symbol} (4H)

Impulse: {signal['impulse_change']:.1f}% / {cfg['impulse_period']} candles
{fib_emoji} Fibo {cfg['fib_level']}: ${signal['fib_price']:.0f}
Entry: ${signal['entry']:.0f}
Stop: ${signal['stop']:.0f}
TP: ${signal['tp']:.0f}
Risk: {signal['risk_pct']}%
OI (8h): {signal['oi']:.1f}%

Backtest WR: {cfg['winrate']:.1f}% | RR 1:{cfg['rr_ratio']:.0f}

⚠️ DYOR & manage risk!"""
                send_tg(msg)
                log(f"SIGNAL {symbol} at ${signal['entry']:.0f}")
        
        time.sleep(SCAN_INTERVAL)
        
    except Exception as e:
        log(f"Error: {e}")
        time.sleep(60)
