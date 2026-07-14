import asyncio
import sys
import threading
import os
import time
from flask import Flask
import bot

# Исправление для event loop на Linux
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Даём Flask время запуститься
    time.sleep(2)
    print("✅ Flask запущен, теперь запускаем бота...")
    
    # Создаём event loop для бота
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        bot.main()
    except RuntimeError as e:
        if "event loop" in str(e):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            bot.main()
        else:
            raise