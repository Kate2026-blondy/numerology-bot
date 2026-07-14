from flask import Flask
import os
import threading
import bot  # Импортируем нашего бота

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Бот для нумерологии работает!"

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    """Запускает Flask-сервер для Render"""
    port = int(os.environ.get('PORT', 5000))
    flask_app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке, чтобы он не блокировал бота
    threading.Thread(target=run_flask, daemon=True).start()
    print("✅ Flask-сервер запущен в фоновом режиме")
    
    # Запускаем основную функцию бота из bot.py
    print("🚀 Запуск бота...")
    bot.main()