import time
import requests
import ccxt
import pandas as pd
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = "8674379393:AAFDUHr-oF3FHJqIfhhXZKcsN3d37__mnms"
CHAT_ID = "755816889"

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
TIMEFRAME = "1h"
LIMIT = 200
OI_THRESHOLD_LONG = -0.8
OI_THRESHOLD_SHORT = 0.8
STOP_ATR_MULTIPLIER = 1.2
RR_RATIO = 3.0
SCAN_INTERVAL = 600  # 10 минут

# ========== TELEGRAM ==========
def send_tg(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print("✅ Отправлено")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

log("🚀 БОТ MACD+EMA+OI (1H, RR 1:3) ЗАПУЩЕН")
send_tg("✅ Бот (MACD+EMA+OI, 1H, RR 1:3) запущен!")

# ========== BINANCE ==========
exchange = ccxt.binance({'enableRateLimit': True})

def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT)
        return pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
    except Exception as e:
        log(f"Ошибка {symbol}: {e}")
        return None

def add_indicators(df):
    # EMA
    df['ema50'] = df['c'].ewm(50).mean()
    df['ema200'] = df['c'].ewm(200).mean()
    
    # MACD
    exp1 = df['c'].ewm(span=12, adjust=False).mean()
    exp2 = df['c'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # ATR
    tr1 = df['h'] - df['l']
    tr2 = abs(df['h'] - df['c'].shift())
    tr3 = abs(df['l'] - df['c'].shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    return df

def get_oi_change(df, idx):
    """Изменение объёма за 2 часа (2 свечи на 1H)"""
    if idx < 2:
        return 0
    now = df['v'].iloc[idx]
    past = df['v'].iloc[idx-2]
    if past == 0:
        return 0
    return round((now - past) / past * 100, 2)

def check_signals(df, symbol, oi, price, atr, ema50, ema200, idx):
    if idx < 2:
        return None
    
    macd_now = df['macd'].iloc[idx]
    signal_now = df['signal'].iloc[idx]
    macd_prev = df['macd'].iloc[idx-1]
    signal_prev = df['signal'].iloc[idx-1]
    
    # LONG: MACD пересекает сигнальную снизу вверх
    if (macd_prev <= signal_prev and macd_now > signal_now and 
        ema50 > ema200 and oi <= OI_THRESHOLD_LONG):
        
        stop = price - atr * STOP_ATR_MULTIPLIER
        risk = price - stop
        return {
            'type': 'LONG',
            'entry': price,
            'stop': stop,
            'tp': price + risk * RR_RATIO,
            'risk_pct': round(risk / price * 100, 2)
        }
    
    # SHORT: MACD пересекает сигнальную сверху вниз
    if (macd_prev >= signal_prev and macd_now < signal_now and 
        ema50 < ema200 and oi >= OI_THRESHOLD_SHORT):
        
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

log("Начинаю сканирование...")

while True:
    try:
        for symbol in SYMBOLS:
            df = get_data(symbol)
            if df is None or len(df) < 50:
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
                msg = f"""{emoji} {signal['type']} {symbol} (1H)

💰 Вход: ${signal['entry']:.0f}
📉 Стоп: ${signal['stop']:.0f}
🎯 Тейк: ${signal['tp']:.0f}
📐 Риск: {signal['risk_pct']}%
🔥 OI за 2ч: {oi:.1f}%
📊 MACD + EMA + OI
⚡ 1:{RR_RATIO}

⚠️ Управляй рисками!"""
                send_tg(msg)
                log(f"🔥 СИГНАЛ {symbol} {signal['type']}")
        
        time.sleep(SCAN_INTERVAL)
        
    except Exception as e:
        log(f"Ошибка: {e}")
        time.sleep(60)
