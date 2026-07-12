from flask import Flask
import os
import threading

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Бот для нумерологии работает!"

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    flask_app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке, чтобы не мешать боту
    threading.Thread(target=run_flask, daemon=True).start()
    # Запускаем основную функцию бота
    main()