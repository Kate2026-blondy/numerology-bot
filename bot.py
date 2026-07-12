import asyncio
import os
import re
import sqlite3
import logging
import json
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, constants
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ==== НАСТРОЙКА ЛОГИРОВАНИЯ ====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("numerology_bot")

# ==== ТОКЕН ====
BOT_TOKEN = "8968195774:AAGXr5Ak1ne-QNy75hK__ZMdhco7wnWc2UQ"
CREATOR_ID = 1022123079
ADMIN_USER_ID = 1022123079
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DATABASE_PATH = "bot.db"

logger.info("✅ Переменные окружения загружены")

# ==== БАЗА ДАННЫХ ====
class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.init_database()
        logger.info(f"✅ База данных инициализирована: {db_path}")

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    name TEXT,
                    birthdate TEXT,
                    registration_date TEXT,
                    state TEXT DEFAULT 'idle',
                    language TEXT DEFAULT 'ru',
                    daily_requests INTEGER DEFAULT 0,
                    last_request_date TEXT,
                    daily_forecast_enabled INTEGER DEFAULT 1
                )
            """)
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN daily_forecast_enabled INTEGER DEFAULT 1")
            except sqlite3.OperationalError:
                pass
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    subscription_type TEXT,
                    start_date TEXT,
                    expiry_date TEXT,
                    payment_status TEXT,
                    payment_id TEXT,
                    auto_renew INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action_type TEXT,
                    timestamp TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    content TEXT,
                    timestamp TEXT
                )
            """)
            conn.commit()

    def get_user(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_user(self, user_id: int, username: str = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, registration_date, last_request_date)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, datetime.now().isoformat(), datetime.now().date().isoformat()))
            conn.commit()

    def update_user(self, user_id: int, **kwargs):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [user_id]
            cursor.execute(f"UPDATE users SET {fields} WHERE user_id = ?", values)
            conn.commit()

    def is_pro_user(self, user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM subscriptions
                WHERE user_id = ?
                AND payment_status = 'succeeded'
                AND expiry_date > ?
            """, (user_id, datetime.now().isoformat()))
            return cursor.fetchone() is not None

    def log_action(self, user_id: int, action_type: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usage_stats (user_id, action_type, timestamp)
                VALUES (?, ?, ?)
            """, (user_id, action_type, datetime.now().isoformat()))
            conn.commit()

db = Database()

# ==== НУМЕРОЛОГИЧЕСКИЕ ФУНКЦИИ ====
def digit_sum(number: int) -> int:
    return sum(int(d) for d in str(number))

def reduce_to_1_9(number: int, preserve_master: bool = False) -> int:
    while number > 9:
        if preserve_master and number in [11, 22, 33]:
            return number
        number = digit_sum(number)
    return number if number != 0 else 9

def parse_date(text: str):
    text = text.strip()
    pattern = r'^(\d{2})\.(\d{2})\.(\d{4})$'
    match = re.match(pattern, text)
    if not match:
        return None
    try:
        return datetime.strptime(text, "%d.%m.%Y")
    except ValueError:
        return None

def consciousness_number(day: int) -> int:
    return reduce_to_1_9(digit_sum(day))

def mission_number(d: datetime) -> int:
    total = digit_sum(d.day) + digit_sum(d.month) + digit_sum(d.year)
    return reduce_to_1_9(total, preserve_master=True)

def action_number(d: datetime) -> int:
    return reduce_to_1_9(digit_sum(int(d.strftime("%d%m%Y"))))

def matrix_counts(d: datetime):
    date_str = d.strftime("%d%m%Y")
    counts = {str(i): 0 for i in range(1, 10)}
    for ch in date_str:
        if ch in counts:
            counts[ch] += 1
    strong = [int(k) for k, v in counts.items() if v > 0]
    missing = [int(k) for k, v in counts.items() if v == 0]
    return strong, missing

def finance_code(d: datetime):
    date_str = d.strftime("%d%m%Y")
    root = reduce_to_1_9(digit_sum(int(date_str)))
    return date_str, root

# ==== ОПИСАНИЯ ====
def get_consciousness_desc(number: int) -> str:
    descriptions = {
        1: "✅ Лидерство, решительность, энергия\n❌ Упрямство, эгоцентричность\n💡 Нюанс: Слышать других и не давить.",
        2: "✅ Дипломатия, партнёрство, мягкость\n❌ Неуверенность, зависимость\n💡 Нюанс: Развивать самостоятельность.",
        3: "✅ Креатив, самовыражение, харизма\n❌ Поверхностность, хаос\n💡 Нюанс: Дисциплина для идей.",
        4: "✅ Справедливость, система, новаторство\n❌ Незавершённость, перегруз\n💡 Нюанс: Структура и финиш задач.",
        5: "✅ Свобода, коммуникация, гибкость\n❌ Разбросанность, бунт\n💡 Нюанс: Ответственность и завершение.",
        6: "✅ Забота, ответственность, качество\n❌ Жертвенность, контроль\n💡 Нюанс: Здоровые границы.",
        7: "✅ Глубина, интуиция, анализ\n❌ Замкнутость, хаос\n💡 Нюанс: Доверие и осознанность.",
        8: "✅ Сила, управление, амбиции\n❌ Жёсткость, давление\n💡 Нюанс: Мудрое лидерство.",
        9: "✅ Гуманизм, миссия, завершение\n❌ Идеализм, выгорание\n💡 Нюанс: Практичность и мера.",
        11: "🌟 МАСТЕР-ЧИСЛО!\n✅ Интуиция, вдохновение\n❌ Тревожность, перфекционизм\n💡 Нюанс: Доверять интуиции.",
        22: "🌟 МАСТЕР-ЧИСЛО!\n✅ Креатив, трансформация\n❌ Перегрузка\n💡 Нюанс: Использовать силу для созидания.",
        33: "🌟 МАСТЕР-ЧИСЛО!\n✅ Служение, любовь\n❌ Жертвенность\n💡 Нюанс: Забота о себе = забота о мире."
    }
    return descriptions.get(number, f"Описание для числа {number} пока отсутствует.")

def get_mission_desc(number: int) -> str:
    descriptions = {
        1: "✅ Воля, цельность\n❌ Эго и жёсткость\n🎯 Цель: Учиться вести мягко.",
        2: "✅ Гармония, дипломатия\n❌ Зависимость\n🎯 Цель: Баланс и самостоятельность.",
        3: "✅ Идеи, радость\n❌ Расфокус\n🎯 Цель: Дисциплина для творчества.",
        4: "✅ Структура, фундамент\n❌ Застревание\n🎯 Цель: Гибкость и финиш задач.",
        5: "✅ Перемены, свобода\n❌ Хаос\n🎯 Цель: Свобода с ответственностью.",
        6: "✅ Ответственность, забота\n❌ Перегруз\n🎯 Цель: Границы и баланс.",
        7: "✅ Смысл, мудрость\n❌ Кризисы\n🎯 Цель: Доверие и осознанность.",
        8: "✅ Результат, масштаб\n❌ Контроль\n🎯 Цель: Этика + эффективность.",
        9: "✅ Служение, завершение\n❌ Выгорание\n🎯 Цель: Практичность.",
        11: "🌟 МАСТЕР-ЧИСЛО!\n✅ Вдохновение, интуиция\n❌ Тревожность\n🎯 Цель: Вдохновлять.",
        22: "🌟 МАСТЕР-ЧИСЛО!\n✅ Трансформация\n❌ Перегрузка\n🎯 Цель: Строить на благо.",
        33: "🌟 МАСТЕР-ЧИСЛО!\n✅ Служение\n❌ Выгорание\n🎯 Цель: Любить и созидать."
    }
    return descriptions.get(number, f"Описание для числа {number} пока отсутствует.")

def get_action_desc(number: int) -> str:
    descriptions = {
        1: "✅ Решительность, напор\n❌ Грубость\n💡 Действует прямо и быстро.",
        2: "✅ Согласование, мирность\n❌ Колебания\n💡 Через сотрудничество и баланс.",
        3: "✅ Динамика, креатив\n❌ Хаос\n💡 Через идеи и движение.",
        4: "✅ Система, шаги\n❌ Застревание\n💡 Через порядок и дисциплину.",
        5: "✅ Гибкость, скорость\n❌ Раздрай\n💡 Через перемены и общение.",
        6: "✅ Ответственность, забота\n❌ Перегруз\n💡 Через качество и поддержку.",
        7: "✅ Аналитика, интуиция\n❌ Изоляция\n💡 Через смысл и глубину.",
        8: "✅ Сила, управление\n❌ Давление\n💡 Через цель и результат.",
        9: "✅ Миссия, гуманизм\n❌ Идеализм\n💡 Через завершение и пользу."
    }
    return descriptions.get(number, f"Описание для числа {number} пока отсутствует.")

def get_finance_desc(number: int) -> str:
    descriptions = {
        1: "Деньги через личную инициативу и лидерство. Риск — давить.",
        2: "Деньги через партнёрства и доверие. Риск — зависимость.",
        3: "Деньги через креатив и контент. Риск — хаос.",
        4: "Деньги через систему и процессы. Риск — незавершённость.",
        5: "Деньги через маркетинг и перемены. Риск — расфокус.",
        6: "Деньги через качество и заботу. Риск — перегруз.",
        7: "«Финансовый философ»: деньги через знания и аналитику. Риск — кризисы.",
        8: "Деньги через управление и масштаб. Риск — жёсткость.",
        9: "Деньги через миссию и пользу людям. Риск — выгорание."
    }
    return descriptions.get(number, f"Описание для финансового кода {number} пока отсутствует.")

def get_strong_desc(numbers: List[int]) -> str:
    meanings = {
        1: "Лидерство, воля, решительность",
        2: "Дипломатия, партнёрство, мягкость",
        3: "Креатив, самовыражение, харизма",
        4: "Система, дисциплина, порядок",
        5: "Гибкость, перемены, свобода",
        6: "Забота, ответственность, качество",
        7: "Интуиция, анализ, глубина",
        8: "Амбиции, управление, сила",
        9: "Миссия, гуманизм, завершение"
    }
    parts = []
    for n in sorted(numbers):
        if n in meanings:
            parts.append(f"<b>{n}</b> — {meanings[n]}")
    return "\n".join(parts) if parts else "Сильные стороны не определены."

def get_missing_desc(numbers: List[int]) -> str:
    tips = {
        1: "Учиться мягкому лидерству и договариваться.",
        2: "Отстаивать свои границы и самостоятельность.",
        3: "Прокачивать регулярное самовыражение.",
        4: "Выстраивать порядок и доводить до конца.",
        5: "Фокус и завершение: меньше задач — больше качества.",
        6: "Забота о себе наравне с заботой о других.",
        7: "Доверие к миру, дневник наблюдений.",
        8: "Мягкая сила: ответственность без давления.",
        9: "Практичность: доводить миссию до результата."
    }
    parts = []
    for n in sorted(numbers):
        if n in tips:
            parts.append(f"<b>{n}</b> — {tips[n]}")
    return "\n".join(parts) if parts else "Зоны роста не определены."

# ==== ОБРАБОТЧИКИ ====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    db.create_user(user_id, username)
    user = db.get_user(user_id)
    if user and user.get('name') and user.get('birthdate'):
        await update.message.reply_text(
            f"👋 С возвращением, {user['name']}!",
            parse_mode=constants.ParseMode.HTML
        )
        return
    db.update_user(user_id, state='awaiting_name')
    await update.message.reply_text(
        "👋 Привет! Как к тебе обращаться? Напиши своё имя:",
        parse_mode=constants.ParseMode.HTML
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats - показать статистику пользователей"""
    user_id = update.effective_user.id

    # Проверяем, что это админ
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ У вас нет доступа к этой команде.")
        return

    # Получаем статистику из базы данных
    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Всего пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        # Зарегистрировались сегодня
        today = datetime.now().date().isoformat()
        cursor.execute("SELECT COUNT(*) FROM users WHERE registration_date LIKE ?", (today + '%',))
        today_users = cursor.fetchone()[0]

        # Зарегистрировались за неделю
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM users WHERE registration_date > ?", (week_ago,))
        week_users = cursor.fetchone()[0]

        # Всего действий
        cursor.execute("SELECT COUNT(*) FROM usage_stats")
        total_actions = cursor.fetchone()[0]

        # Действий за сегодня
        cursor.execute("SELECT COUNT(*) FROM usage_stats WHERE timestamp LIKE ?", (today + '%',))
        today_actions = cursor.fetchone()[0]

        # PRO пользователей
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) FROM subscriptions
            WHERE payment_status = 'succeeded' AND expiry_date > ?
        """, (datetime.now().isoformat(),))
        pro_users = cursor.fetchone()[0]

    # Формируем ответ
    stats_text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 <b>Всего пользователей:</b> {total_users}\n"
        f"📅 <b>Зарегистрировались сегодня:</b> {today_users}\n"
        f"📆 <b>За неделю:</b> {week_users}\n"
        f"⭐ <b>PRO пользователей:</b> {pro_users}\n\n"
        f"📈 <b>Активность:</b>\n"
        f"• Всего действий: {total_actions}\n"
        f"• Сегодня: {today_actions}\n\n"
        f"💡 <i>Данные обновляются автоматически</i>"
    )

    await update.message.reply_text(stats_text, parse_mode=constants.ParseMode.HTML)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    user = db.get_user(user_id)
    if not user:
        db.create_user(user_id, update.effective_user.username)
        user = db.get_user(user_id)
    state = user.get('state', 'idle')

    if state == 'awaiting_name':
        if len(text) > 50:
            await update.message.reply_text("❌ Имя слишком длинное. Попробуйте ещё раз:")
            return
        db.update_user(user_id, name=text, state='awaiting_birthdate')
        await update.message.reply_text(
            f"Отлично, {text}! 👍\n\nТеперь введи дату рождения в формате <b>ДД.ММ.ГГГГ</b>\nНапример: 22.06.1995",
            parse_mode=constants.ParseMode.HTML
        )
        return

    if state == 'awaiting_birthdate':
        birthdate = parse_date(text)
        if not birthdate:
            await update.message.reply_text(
                "❌ Неверный формат даты.\n\nВведи дату в формате <b>ДД.ММ.ГГГГ</b>\nНапример: 22.06.1995",
                parse_mode=constants.ParseMode.HTML
            )
            return
        if birthdate.year < 1900 or birthdate > datetime.now():
            await update.message.reply_text("❌ Некорректная дата рождения. Попробуйте ещё раз:")
            return
        db.update_user(user_id, birthdate=text, state='idle')
        db.log_action(user_id, 'registration_complete')
        user = db.get_user(user_id)
        d = datetime.strptime(user['birthdate'], "%d.%m.%Y")
        cn = consciousness_number(d.day)
        ms = mission_number(d)
        act = action_number(d)
        strong, missing = matrix_counts(d)
        fcode, froot = finance_code(d)

        report = (
            f"👋 <b>{user['name']}</b>, вот твой нумерологический отчёт:\n\n"
            f"📅 Дата рождения: <b>{user['birthdate']}</b>\n\n"
            f"🔑 <b>Число Сознания: {cn}</b>\n{get_consciousness_desc(cn)}\n\n"
            f"🌟 <b>Число Миссии: {ms}</b>\n{get_mission_desc(ms)}\n\n"
            f"🧭 <b>Стиль действия: {act}</b>\n{get_action_desc(act)}\n\n"
            f"💰 <b>Финансовый код: {fcode}</b> (корень: {froot})\n{get_finance_desc(froot)}\n\n"
            f"✨ <b>Сильные числа:</b> {strong}\n{get_strong_desc(strong)}\n\n"
            f"🎯 <b>Зоны роста:</b> {missing}\n{get_missing_desc(missing)}\n\n"
            f"💡 <i>Чтобы узнать подробнее о любом числе, напиши:\n"
            f"«Число сознания», «Число миссии», «Сильные числа» или «Зоны роста»</i>"
        )
        await update.message.reply_text(report, parse_mode=constants.ParseMode.HTML)
        return

    if user and user.get('birthdate'):
        d = datetime.strptime(user['birthdate'], "%d.%m.%Y")
        cn = consciousness_number(d.day)
        ms = mission_number(d)
        act = action_number(d)
        strong, missing = matrix_counts(d)
        fcode, froot = finance_code(d)
        text_lower = text.lower()

        if "сознание" in text_lower or "число сознания" in text_lower:
            await update.message.reply_text(
                f"🔑 <b>Число Сознания: {cn}</b>\n\n{get_consciousness_desc(cn)}",
                parse_mode=constants.ParseMode.HTML
            )
            return

        if "мисси" in text_lower or "число миссии" in text_lower:
            await update.message.reply_text(
                f"🌟 <b>Число Миссии: {ms}</b>\n\n{get_mission_desc(ms)}",
                parse_mode=constants.ParseMode.HTML
            )
            return

        if "действ" in text_lower or "стиль" in text_lower:
            await update.message.reply_text(
                f"🧭 <b>Стиль действия: {act}</b>\n\n{get_action_desc(act)}",
                parse_mode=constants.ParseMode.HTML
            )
            return

        if "финанс" in text_lower or "деньг" in text_lower or "код" in text_lower:
            await update.message.reply_text(
                f"💰 <b>Финансовый код: {fcode}</b> (корень: {froot})\n\n{get_finance_desc(froot)}",
                parse_mode=constants.ParseMode.HTML
            )
            return

        if "сильн" in text_lower or "сильные" in text_lower:
            await update.message.reply_text(
                f"✨ <b>Ваши сильные числа:</b> {strong}\n\n{get_strong_desc(strong)}",
                parse_mode=constants.ParseMode.HTML
            )
            return

        if "зоны" in text_lower or "рост" in text_lower or "слабы" in text_lower:
            await update.message.reply_text(
                f"🎯 <b>Зоны роста:</b> {missing}\n\n{get_missing_desc(missing)}",
                parse_mode=constants.ParseMode.HTML
            )
            return

    await update.message.reply_text(
        "Я тебя слышу! 😊\n\n"
        "Чтобы получить отчёт, напиши /start\n"
        "Чтобы узнать значение чисел, напиши:\n"
        "• «Число сознания»\n"
        "• «Число миссии»\n"
        "• «Стиль действия»\n"
        "• «Финансовый код»\n"
        "• «Сильные числа»\n"
        "• «Зоны роста»"
    )

# ==== ЗАПУСК ====
def main():
    logger.info("=" * 50)
    logger.info("🚀 Запуск Telegram бота для нумерологии v5.0")
    logger.info("=" * 50)
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не задан")
        return
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    logger.info("✅ Бот успешно запущен!")
    logger.info("Нажмите Ctrl+C для остановки")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()