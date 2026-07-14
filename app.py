import asyncio
import sys
import threading
import os
from flask import Flask
import bot

# Исправление для event loop
if sys.platform == "win32" or sys.platform.startswith("linux"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
    threading.Thread(target=run_flask, daemon=True).start()
    print("✅ Flask запущен")
    try:
        bot.main()
    except RuntimeError as e:
        if "event loop" in str(e):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            bot.main()
        else:
            raise