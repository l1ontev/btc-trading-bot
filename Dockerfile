FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot_15m.py .

# Принудительно запускаем Python скрипт
CMD ["python", "bot_15m.py"]
