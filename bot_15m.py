import time
import requests
from datetime import datetime

TOKEN = "8674379393:AAFDUHr-oF3FHJqIfhhXZKcsN3d37__mnms"
CHAT_ID = "755816889"

def send_tg(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print(f"Статус: {r.status_code}")
    except Exception as e:
        print(f"Ошибка: {e}")

print("⚠️ ТЕСТОВЫЙ СКРИПТ ЗАПУЩЕН")
send_tg("🧪 Тестовый скрипт работает! Если ты видишь это сообщение — бот может отправлять сообщения в Telegram.")

count = 0
while True:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Жив! count={count}")
    if count % 12 == 0 and count > 0:  # раз в час (12 раз по 5 минут)
        send_tg(f"💚 Бот жив. Прошло {count//12} часов без сигналов (тестовый режим)")
    count += 1
    time.sleep(300)  # 5 минут
