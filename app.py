import os
import time
import threading
from flask import Flask
import subprocess

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

def run_bot():
    """Запускаем бота в отдельном процессе"""
    print("🚀 Запуск бота в отдельном процессе...")
    # Используем subprocess, чтобы бот работал в своём собственном процессе
    subprocess.Popen(["python", "-c", 
        "import bot; bot.main()"
    ], stdout=None, stderr=None)

if __name__ == "__main__":
    # Запускаем бота в отдельном процессе (не потоке!)
    run_bot()
    
    # Даём боту время запуститься
    time.sleep(3)
    
    # Запускаем Flask в основном потоке
    run_flask()
    