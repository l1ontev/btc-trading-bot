import time
import requests
import ccxt
import pandas as pd
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = "8674379393:AAFDUHr-oF3FHJqIfhhXZKcsN3d37__mnms"
CHAT_ID = "755816889"

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
OI_THRESHOLD = 0.5          # 0.5% — низкий порог для частых сигналов
TIMEFRAME = "15m"
LIMIT = 100

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

log("🚀 БОТ MACD+EMA+OI ЗАПУЩЕН")
send_tg("✅ Бот (MACD+EMA+OI) запущен! Жди сигналов.")

# ========== BINANCE ==========
exchange = ccxt.binance({'enableRateLimit': True})

def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        log(f"Ошибка {symbol}: {e}")
        return None

def get_oi(symbol):
    """Изменение объёма за 30 минут (простой OI)"""
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
    """Добавляет EMA и MACD"""
    # EMA 50 и 200
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # MACD: 12, 26, 9
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Histogram'] = df['MACD'] - df['Signal']
    
    return df

def check_signals(df, symbol, oi, price):
    if df is None or len(df) < 35:
        return None
    
    ema50 = df['EMA50'].iloc[-1]
    ema200 = df['EMA200'].iloc[-1]
    
    # MACD пересечения
    macd_now = df['MACD'].iloc[-1]
    signal_now = df['Signal'].iloc[-1]
    macd_prev = df['MACD'].iloc[-2]
    signal_prev = df['Signal'].iloc[-2]
    
    # LONG: MACD пересекает сигнальную снизу вверх + EMA50 > EMA200 + OI падает
    if (macd_prev <= signal_prev and macd_now > signal_now and 
        ema50 > ema200 and oi <= -OI_THRESHOLD):
        return {'type': 'LONG', 'entry': price, 'oi': f"{oi:.1f}%"}
    
    # SHORT: MACD пересекает сигнальную сверху вниз + EMA50 < EMA200 + OI растёт
    if (macd_prev >= signal_prev and macd_now < signal_now and 
        ema50 < ema200 and oi >= OI_THRESHOLD):
        return {'type': 'SHORT', 'entry': price, 'oi': f"{oi:.1f}%"}
    
    return None

log("Начинаю сканирование...")

# ========== ОСНОВНОЙ ЦИКЛ ==========
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
                msg = f"""{emoji} СИГНАЛ {signal['type']} ({TIMEFRAME})

{symbol}
💰 Вход: ${price:.0f}
🔥 OI за 30мин: {signal['oi']}
📊 MACD пересечение + EMA + OI

⚠️ Управляй рисками!"""
                send_tg(msg)
                log(f"🔥 {symbol} {signal['type']} | OI: {signal['oi']}")
            else:
                # Диагностика раз в 20 циклов (≈1.5 часа)
                if int(time.time()) % 3600 < 30:
                    ema50 = df['EMA50'].iloc[-1]
                    ema200 = df['EMA200'].iloc[-1]
                    log(f"Диагностика {symbol}: цена={price:.0f}, OI={oi:.1f}%, EMA50/200={ema50:.0f}/{ema200:.0f}")
        
        time.sleep(300)  # 5 минут
        
    except Exception as e:
        log(f"Ошибка: {e}")
        time.sleep(60)
