import asyncio
import sys
import threading
import os
import time
from flask import Flask
import bot

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Бот для нумерологии работает!"

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    print(f"🚀 Запуск Flask на порту {port}...")
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Запускаем Flask
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)
    print("✅ Flask запущен")

    # Запускаем бота ПРЯМО, без лишних обёрток
    print("🚀 Запуск бота...")
    bot.main()