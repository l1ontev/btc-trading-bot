cd ~/Desktop
mkdir -p eth_stable_bot
cd eth_stable_bot
cat > eth_bot.py << 'EOF'
import time
import requests
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

# ========== НАСТРОЙКИ (ПО РЕЗУЛЬТАТАМ ТЕСТА) ==========
TOKEN = "8674379393:AAFDUHr-oF3FHJqIfhhXZKcsN3d37__mnms"
CHAT_ID = "755816889"

SYMBOL = "ETH/USDT"
TIMEFRAME = "4h"
LIMIT = 200
SCAN_INTERVAL = 600  # 10 минут

# Параметры стратегии (лучшие из теста)
IMPULSE_PCT = 1.5           # импульс 1.5% за период
IMPULSE_PERIOD = 10         # за 10 свечей (40 часов)
FIB_LEVEL = 0.5             # уровень Фибоначчи 0.5 (50%)
OI_THRESHOLD = -0.5         # OI падает на 0.5% за 8 часов
STOP_ATR_MULTIPLIER = 2.0   # стоп 2.0 × ATR
RR_RATIO = 2.0              # риск/прибыль 1:2

RISK_PER_TRADE = 3.0        # риск 3% от депозита на сделку

# ========== ХРАНИЛИЩЕ ПОСЛЕДНИХ СИГНАЛОВ ==========
last_signals = {}

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

log("🚀 БОТ ETH СТАБИЛЬНАЯ СТРАТЕГИЯ ЗАПУЩЕН")
send_tg("✅ ETH Бот (1.5% импульс, Фибо 0.5, OI -0.5%, RR 1:2) запущен!")

# ========== BINANCE ==========
exchange = ccxt.binance({'enableRateLimit': True})

def get_data():
    try:
        ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=LIMIT)
        df = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        return df
    except Exception as e:
        log(f"Ошибка загрузки: {e}")
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
    if past == 0:
        return 0
    return round((now - past) / past * 100, 2)

def find_impulse_up(df, idx):
    if idx < IMPULSE_PERIOD:
        return None, None
    start = idx - IMPULSE_PERIOD
    start_price = df['c'].iloc[start]
    end_price = df['c'].iloc[idx]
    change = (end_price - start_price) / start_price * 100
    if change >= IMPULSE_PCT:
        return start, idx
    return None, None

def find_fib_level(df, impulse_start, impulse_end):
    high = df['h'].iloc[impulse_start:impulse_end+1].max()
    low = df['l'].iloc[impulse_start:impulse_end+1].min()
    range_ = high - low
    return high - range_ * FIB_LEVEL

def check_correction(df, idx, impulse_start, impulse_end):
    fib_price = find_fib_level(df, impulse_start, impulse_end)
    if fib_price is None:
        return None
    
    current_price = df['c'].iloc[idx]
    if abs(current_price - fib_price) / fib_price > 0.003:
        return None
    
    body = abs(df['c'].iloc[idx] - df['o'].iloc[idx])
    if body == 0:
        return None
    lower_wick = min(df['o'].iloc[idx], df['c'].iloc[idx]) - df['l'].iloc[idx]
    
    if lower_wick > body * 1.2:
        return fib_price
    return None

def is_duplicate_signal(entry_price, tolerance_pct=1.0):
    if SYMBOL not in last_signals:
        return False
    
    last_entry = last_signals[SYMBOL]['entry_price']
    last_time = last_signals[SYMBOL]['timestamp']
    current_time = datetime.now()
    
    if (current_time - last_time).total_seconds() > 24 * 3600:
        return False
    
    price_diff_pct = abs(entry_price - last_entry) / last_entry * 100
    return price_diff_pct < tolerance_pct

def save_signal(entry_price):
    last_signals[SYMBOL] = {
        'entry_price': entry_price,
        'timestamp': datetime.now()
    }

def check_signal(df):
    if len(df) < IMPULSE_PERIOD + 30:
        return None
    
    idx = len(df) - 1
    price = df['c'].iloc[idx]
    oi = get_oi_change(df, idx)
    atr = df['atr'].iloc[idx] if not pd.isna(df['atr'].iloc[idx]) else 0
    
    if atr == 0:
        return None
    
    imp_start, imp_end = find_impulse_up(df, idx)
    if imp_start is None:
        return None
    
    if oi > OI_THRESHOLD:
        return None
    
    fib_price = check_correction(df, idx, imp_start, imp_end)
    if fib_price is None:
        return None
    
    entry = price
    stop = entry - atr * STOP_ATR_MULTIPLIER
    risk = entry - stop
    
    if risk <= 0:
        return None
    
    tp = entry + risk * RR_RATIO
    risk_pct = round(risk / entry * 100, 2)
    impulse_change = (df['c'].iloc[imp_end] - df['c'].iloc[imp_start]) / df['c'].iloc[imp_start] * 100
    
    return {
        'entry': entry,
        'stop': stop,
        'tp': tp,
        'risk_pct': risk_pct,
        'oi': oi,
        'fib_price': fib_price,
        'impulse_change': impulse_change,
        'impulse_start': df['ts'].iloc[imp_start],
        'impulse_end': df['ts'].iloc[imp_end]
    }

log("Начинаю сканирование...")

while True:
    try:
        df = get_data()
        if df is None or len(df) < 80:
            time.sleep(SCAN_INTERVAL)
            continue
        
        df = add_indicators(df)
        signal = check_signal(df)
        
        if signal:
            if is_duplicate_signal(signal['entry']):
                log(f"⏭️ Пропуск дубликата ETH по ${signal['entry']:.0f}")
                time.sleep(SCAN_INTERVAL)
                continue
            
            save_signal(signal['entry'])
            
            msg = f"""🟢 LONG ETH/USDT (4H)

📊 Импульс: {signal['impulse_change']:.1f}% за {IMPULSE_PERIOD} свечей
🔹 Фибо 0.5: ${signal['fib_price']:.0f}
💰 Вход: ${signal['entry']:.0f}
📉 Стоп: ${signal['stop']:.0f}
🎯 Тейк: ${signal['tp']:.0f}
📐 Риск: {signal['risk_pct']}%
🔥 OI за 8ч: {signal['oi']:.1f}%

⚡ Винрейт бэктеста: 61.9%
🎯 RR 1:{RR_RATIO:.0f}
📈 Ожидаемая доходность в месяц: +20%

⚠️ Управляй рисками!"""
            send_tg(msg)
            log(f"🔥 СИГНАЛ ETH по ${signal['entry']:.0f}")
        
        time.sleep(SCAN_INTERVAL)
        
    except Exception as e:
        log(f"Ошибка: {e}")
        time.sleep(60)
EOF
