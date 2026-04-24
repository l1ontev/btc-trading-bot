import time
import requests
import ccxt
import pandas as pd
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = "8674379393:AAFDUHr-oF3FHJqIfhhXZKcsN3d37__mnms"
CHAT_ID = "755816889"

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
OI_THRESHOLD = 0.5
TIMEFRAME = "15m"
LIMIT = 100
STOP_ATR_MULTIPLIER = 1.2
RR_RATIO = 2.0
SCAN_INTERVAL = 300
HEARTBEAT_INTERVAL = 3600

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

log("🚀 БОТ MACD+EMA+OI ЗАПУЩЕН")
send_tg("✅ Бот (MACD+EMA+OI) запущен! Жди сигналов.")

# ========== BINANCE ==========
exchange = ccxt.binance({'enableRateLimit': True})

def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT)
        return pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    except Exception as e:
        log(f"Ошибка {symbol}: {e}")
        return None

def get_oi(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=4)
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
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean()
    return df

def check_signals(df, symbol, oi, price):
    if df is None or len(df) < 35:
        return None
    ema50 = df['EMA50'].iloc[-1]
    ema200 = df['EMA200'].iloc[-1]
    atr = df['ATR'].iloc[-1]
    macd_now = df['MACD'].iloc[-1]
    signal_now = df['Signal'].iloc[-1]
    macd_prev = df['MACD'].iloc[-2]
    signal_prev = df['Signal'].iloc[-2]
    
    if (macd_prev <= signal_prev and macd_now > signal_now and 
        ema50 > ema200 and oi <= -OI_THRESHOLD):
        stop = price - atr * STOP_ATR_MULTIPLIER
        risk = price - stop
        return {'type': 'LONG', 'entry': price, 'stop': stop, 'tp': price + risk * RR_RATIO, 'risk_pct': round((risk/price)*100,1), 'oi': f"{oi:.1f}%"}
    
    if (macd_prev >= signal_prev and macd_now < signal_now and 
        ema50 < ema200 and oi >= OI_THRESHOLD):
        stop = price + atr * STOP_ATR_MULTIPLIER
        risk = stop - price
        return {'type': 'SHORT', 'entry': price, 'stop': stop, 'tp': price - risk * RR_RATIO, 'risk_pct': round((risk/price)*100,1), 'oi': f"{oi:.1f}%"}
    
    return None

last_heartbeat = 0
last_signal_time = time.time()
log("Начинаю сканирование...")

while True:
    try:
        signal_found = False
        for symbol in SYMBOLS:
            df = get_data(symbol)
            if df is None: continue
            df = add_indicators(df)
            oi = get_oi(symbol)
            price = get_price(symbol)
            signal = check_signals(df, symbol, oi, price)
            if signal:
                signal_found = True
                last_signal_time = time.time()
                emoji = "🟢" if signal['type'] == 'LONG' else "🔴"
                msg = f"""{emoji} {signal['type']} {symbol}

💰 Вход: ${signal['entry']:.0f}
📉 Стоп: ${signal['stop']:.0f}
🎯 Тейк: ${signal['tp']:.0f}
📐 Риск: {signal['risk_pct']}%
🔥 OI: {signal['oi']}

⚡ 1:{RR_RATIO}"""
                send_tg(msg)
                log(f"🔥 {symbol} {signal['type']}")
        
        if not signal_found and (time.time() - last_heartbeat) >= HEARTBEAT_INTERVAL:
            last_heartbeat = time.time()
            hours = int((time.time() - last_signal_time) / 3600)
            msg = f"💤 Нет сигналов {hours}ч. Отдыхай молодой, епт! 🧘" if hours > 0 else "💤 Нет сигналов. Отдыхай молодой, епт! 🧘"
            send_tg(msg)
            log(msg)
        
        time.sleep(SCAN_INTERVAL)
    except Exception as e:
        log(f"Ошибка: {e}")
        time.sleep(60)
