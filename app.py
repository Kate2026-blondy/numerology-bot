import os
import time
import threading
from flask import Flask
import subprocess
import asyncio

# Принудительно создаём event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

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
    
    time.sleep(2)
    print("✅ Flask запущен")
    
    # Запускаем бота через subprocess (отдельный процесс)
    print("🚀 Запуск бота...")
    os.system("python -c \"import bot; bot.main()\"")