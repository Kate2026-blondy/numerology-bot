import os
import re
import sqlite3
import logging
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from dotenv import load_dotenv

# ==== ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CREATOR_ID = int(os.getenv("CREATOR_ID", 0))
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0))
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")
FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", 5))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан! Добавь его в переменные окружения на Render.")

# ==== НАСТРОЙКА ЛОГИРОВАНИЯ ====
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("numerology_bot")
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
                    daily_requests INTEGER DEFAULT 0,
                    last_request_date TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    subscription_type TEXT,
                    start_date TEXT,
                    expiry_date TEXT,
                    payment_status TEXT,
                    payment_id TEXT
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
            cursor.execute("INSERT INTO usage_stats (user_id, action_type, timestamp) VALUES (?, ?, ?)",
                           (user_id, action_type, datetime.now().isoformat()))
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

def daily_number(date: datetime) -> int:
    day_sum = digit_sum(date.day)
    month_sum = digit_sum(date.month)
    total = day_sum + month_sum
    return reduce_to_1_9(total)

# ==== ОПИСАНИЯ ====
CONSCIOUSNESS_DESC = {
    1: {"plus": "Лидерство, решительность, энергия", "minus": "Упрямство, эгоцентричность", "nuance": "Слышать других и не давить."},
    2: {"plus": "Дипломатия, партнёрство, мягкость", "minus": "Неуверенность, зависимость", "nuance": "Развивать самостоятельность."},
    3: {"plus": "Креатив, самовыражение, харизма", "minus": "Поверхностность, хаос", "nuance": "Дисциплина для идей."},
    4: {"plus": "Справедливость, система, новаторство", "minus": "Незавершённость, перегруз", "nuance": "Структура и финиш задач."},
    5: {"plus": "Свобода, коммуникация, гибкость", "minus": "Разбросанность, бунт", "nuance": "Ответственность и завершение."},
    6: {"plus": "Забота, ответственность, красота внешняя и внутренняя", "minus": "Жертвенность, контроль", "nuance": "Здоровые границы."},
    7: {"plus": "Глубина, интуиция, анализ", "minus": "Замкнутость, хаос", "nuance": "Доверие и осознанность."},
    8: {"plus": "Сила, управление, амбиции", "minus": "Жёсткость, давление", "nuance": "Мудрое лидерство."},
    9: {"plus": "Гуманизм, миссия, завершение", "minus": "Идеализм, выгорание", "nuance": "Практичность и мера."},
    11: {"plus": "Интуиция, вдохновение, духовное лидерство", "minus": "Тревожность, перфекционизм", "nuance": "Доверять интуиции, но сохранять связь с реальностью."},
    22: {"plus": "Креатив, трансформация, строительство", "minus": "Перегрузка, давление", "nuance": "Использовать силу для созидания."},
    33: {"plus": "Служение, любовь, исцеление", "minus": "Жертвенность, выгорание", "nuance": "Забота о себе = забота о мире."}
}

MISSION_DESC = {
    1: {"plus": "Воля, цельность", "minus": "Эго и жёсткость", "goal": "Учиться вести мягко."},
    2: {"plus": "Гармония, дипломатия", "minus": "Зависимость", "goal": "Баланс и самостоятельность."},
    3: {"plus": "Идеи, радость", "minus": "Расфокус", "goal": "Дисциплина для творчества."},
    4: {"plus": "Структура, фундамент", "minus": "Застревание", "goal": "Гибкость и финиш задач."},
    5: {"plus": "Перемены, свобода", "minus": "Хаос", "goal": "Свобода с ответственностью."},
    6: {"plus": "Ответственность, забота", "minus": "Перегруз", "goal": "Границы и баланс."},
    7: {"plus": "Смысл, мудрость", "minus": "Кризисы", "goal": "Доверие и осознанность."},
    8: {"plus": "Результат, масштаб", "minus": "Контроль", "goal": "Этика + эффективность."},
    9: {"plus": "Служение, завершение", "minus": "Выгорание", "goal": "Практичность."},
    11: {"plus": "Вдохновение, интуиция", "minus": "Тревожность", "goal": "Вдохновлять и реализовывать."},
    22: {"plus": "Трансформация", "minus": "Перегрузка", "goal": "Строить на благо."},
    33: {"plus": "Служение", "minus": "Выгорание", "goal": "Любить и созидать."}
}

ACTION_DESC = {
    1: {"plus": "Решительность, напор", "minus": "Грубость", "title": "Действует прямо и быстро."},
    2: {"plus": "Согласование, мирность", "minus": "Колебания", "title": "Через сотрудничество и баланс."},
    3: {"plus": "Динамика, креатив", "minus": "Хаос", "title": "Через идеи и движение."},
    4: {"plus": "Система, шаги", "minus": "Застревание", "title": "Через порядок и дисциплину."},
    5: {"plus": "Гибкость, скорость", "minus": "Раздрай", "title": "Через перемены и общение."},
    6: {"plus": "Ответственность, забота", "minus": "Перегруз", "title": "Через красоту и поддержку."},
    7: {"plus": "Аналитика, интуиция", "minus": "Изоляция", "title": "Через смысл и глубину."},
    8: {"plus": "Сила, управление", "minus": "Давление", "title": "Через цель и результат."},
    9: {"plus": "Миссия, гуманизм", "minus": "Идеализм", "title": "Через завершение и пользу."}
}

FINANCE_NOTES = {
    1: "Деньги через личную инициативу и лидерство. Риск — давить.",
    2: "Деньги через партнёрства и доверие. Риск — зависимость.",
    3: "Деньги через креатив и контент. Риск — хаос.",
    4: "Деньги через систему и процессы. Риск — незавершённость.",
    5: "Деньги через маркетинг и перемены. Риск — расфокус.",
    6: "Деньги через красоту и заботу. Риск — перегруз.",
    7: "Деньги через знания и аналитику. Риск — кризисы.",
    8: "Деньги через управление и масштаб. Риск — жёсткость.",
    9: "Деньги через миссию и пользу людям. Риск — выгорание."
}

MATRIX_MEANINGS = {
    1: "Лидерство, воля, решительность",
    2: "Дипломатия, партнёрство, мягкость",
    3: "Креатив, самовыражение, харизма",
    4: "Система, дисциплина, порядок",
    5: "Гибкость, перемены, свобода",
    6: "Забота, ответственность, красота",
    7: "Интуиция, анализ, глубина",
    8: "Амбиции, управление, сила",
    9: "Миссия, гуманизм, завершение"
}

GROWTH_TIPS = {
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

def get_consciousness_desc(number: int) -> str:
    c = CONSCIOUSNESS_DESC.get(number, {})
    return f"✅ {c.get('plus', '—')}\n❌ {c.get('minus', '—')}\n💡 {c.get('nuance', '—')}"

def get_mission_desc(number: int) -> str:
    m = MISSION_DESC.get(number, {})
    return f"✅ {m.get('plus', '—')}\n❌ {m.get('minus', '—')}\n🎯 {m.get('goal', '—')}"

def get_action_desc(number: int) -> str:
    a = ACTION_DESC.get(number, {})
    return f"✅ {a.get('plus', '—')}\n❌ {a.get('minus', '—')}\n💡 {a.get('title', '—')}"

def get_finance_desc(number: int) -> str:
    return FINANCE_NOTES.get(number, "Описание отсутствует.")

def get_strong_desc(numbers: List[int]) -> str:
    parts = [f"<b>{n}</b> — {MATRIX_MEANINGS.get(n, '—')}" for n in sorted(numbers) if n in MATRIX_MEANINGS]
    return "\n".join(parts) if parts else "Сильные стороны не определены."

def get_missing_desc(numbers: List[int]) -> str:
    parts = [f"<b>{n}</b> — {GROWTH_TIPS.get(n, '—')}" for n in sorted(numbers) if n in GROWTH_TIPS]
    return "\n".join(parts) if parts else "Зоны роста не определены."

# ==== ГЛАВНОЕ МЕНЮ С КНОПКАМИ ====
def main_menu(is_pro: bool = False) -> InlineKeyboardMarkup:
    if is_pro:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Моя карта", callback_data="card"),
             InlineKeyboardButton("❤️ Совместимость", callback_data="compat")],
            [InlineKeyboardButton("✨ Практики роста", callback_data="practices"),
             InlineKeyboardButton("📚 Личный гайд", callback_data="guide")],
            [InlineKeyboardButton("🎬 Книги и фильмы", callback_data="media"),
             InlineKeyboardButton("📝 Мини-тест", callback_data="test")],
            [InlineKeyboardButton("🤖 Спросить AI", callback_data="ask_ai"),
             InlineKeyboardButton("📅 Календарь", callback_data="calendar")],
            [InlineKeyboardButton("🗑 Очистить историю", callback_data="clear_history"),
             InlineKeyboardButton("👤 Профиль", callback_data="profile")]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Моя карта", callback_data="card")],
            [InlineKeyboardButton("❤️ Совместимость 🔒", callback_data="compat"),
             InlineKeyboardButton("✨ Практики роста 🔒", callback_data="practices")],
            [InlineKeyboardButton("📚 Личный гайд 🔒", callback_data="guide"),
             InlineKeyboardButton("🎬 Книги и фильмы 🔒", callback_data="media")],
            [InlineKeyboardButton("📝 Мини-тест 🔒", callback_data="test"),
             InlineKeyboardButton("🤖 AI 🔒", callback_data="ask_ai")],
            [InlineKeyboardButton("📅 Календарь 🔒", callback_data="calendar"),
             InlineKeyboardButton("👤 Профиль", callback_data="profile")],
            [InlineKeyboardButton("⭐ Оформить PRO", callback_data="subscription")]
        ])

def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В меню", callback_data="menu")]])

# ==== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====
def build_user_profile_context(user_id: int) -> str:
    user = db.get_user(user_id)
    if not user or not user.get('birthdate'):
        return ""
    d = datetime.strptime(user['birthdate'], "%d.%m.%Y")
    cn = consciousness_number(d.day)
    ms = mission_number(d)
    act = action_number(d)
    strong, missing = matrix_counts(d)
    fcode, froot = finance_code(d)
    return (
        f"Имя: {user['name']}\n"
        f"Дата рождения: {user['birthdate']}\n"
        f"Число Сознания: {cn}\n"
        f"Число Миссии: {ms}\n"
        f"Стиль действия: {act}\n"
        f"Сильные числа: {strong}\n"
        f"Зоны роста: {missing}\n"
        f"Финансовый код: {fcode} (корень: {froot})\n"
    )

def build_full_report(name: str, d: datetime) -> str:
    day_raw = d.day
    cn = consciousness_number(d.day)
    ms = mission_number(d)
    act = action_number(d)
    strong, missing = matrix_counts(d)
    fcode, froot = finance_code(d)
    c = CONSCIOUSNESS_DESC.get(cn, {})
    m = MISSION_DESC.get(ms, {})
    a = ACTION_DESC.get(act, {})
    strong_lines = [f"• <b>{x}</b> — {MATRIX_MEANINGS.get(x, '—')}" for x in strong]
    growth_lines = [f"• <b>{x}</b> — {GROWTH_TIPS.get(x, 'Нарабатывай постепенно.')}" for x in missing]
    f_note = FINANCE_NOTES.get(froot, "")
    return (
        f"👋 <b>{name}</b>, вот твой персональный нумерологический отчёт\n"
        f"📅 Дата рождения: <b>{d.strftime('%d.%m.%Y')}</b>\n\n"
        f"🔑 <b>Число Сознания: {day_raw} → {cn}</b>\n"
        f"• ✅ {c.get('plus', '—')}\n"
        f"• ❌ {c.get('minus', '—')}\n"
        f"• 💡 {c.get('nuance', '—')}\n\n"
        f"🌟 <b>Миссия: {ms}</b>\n"
        f"• ✅ {m.get('plus', '—')}\n"
        f"• ❌ {m.get('minus', '—')}\n"
        f"• 🎯 {m.get('goal', '—')}\n\n"
        f"🧭 <b>Стиль действия: {act}</b>\n"
        f"• ✅ {a.get('plus', '—')}\n"
        f"• ❌ {a.get('minus', '—')}\n"
        f"• 💡 {a.get('title', '—')}\n\n"
        f"✨ <b>Сильные стороны:</b>\n" + ("\n".join(strong_lines) if strong_lines else "—") + "\n\n"
        f"🎯 <b>Зоны роста:</b>\n" + ("\n".join(growth_lines) if growth_lines else "—") + "\n\n"
        f"💰 <b>Финансовый код: {fcode}</b> (корень: {froot})\n" + (f"• {f_note}" if f_note else "")
    )

def ask_deepseek_ai(prompt: str, user_id: int = None, max_tokens: int = 1500, use_history: bool = True) -> str:
    if not DEEPSEEK_API_KEY:
        return "⚠️ API-ключ DeepSeek не настроен. Добавь DEEPSEEK_API_KEY в переменные окружения."
    try:
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
        messages = [{"role": "system", "content": "Ты — цифровой психолог-нумеролог. Отвечай в формате Telegram-HTML."}]
        messages.append({"role": "user", "content": prompt})
        data = {"model": "deepseek-chat", "messages": messages, "max_tokens": max_tokens, "temperature": 0.7}
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"DeepSeek API Error: {e}")
        return f"⚠️ Ошибка при запросе к AI: {str(e)}"

# ==== ОБРАБОТЧИКИ КОМАНД ====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    db.create_user(user_id, username)
    user = db.get_user(user_id)
    if user and user.get('name') and user.get('birthdate'):
        is_pro = db.is_pro_user(user_id)
        await update.message.reply_text(
            f"👋 С возвращением, <b>{user['name']}</b>!\n\nВыбери нужный раздел:",
            parse_mode=constants.ParseMode.HTML,
            reply_markup=main_menu(is_pro)
        )
        return
    db.update_user(user_id, state='awaiting_name')
    await update.message.reply_text(
        "👋 <b>Привет! Я твой бот-нумеролог</b>\n\n"
        "📝 Для начала, как к тебе обращаться? Напиши своё имя:",
        parse_mode=constants.ParseMode.HTML
    )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.update_user(user_id, state='idle')
    is_pro = db.is_pro_user(user_id)
    await update.message.reply_text(
        "🏠 <b>Главное меню</b>",
        parse_mode=constants.ParseMode.HTML,
        reply_markup=main_menu(is_pro)
    )

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
            await update.message.reply_text("❌ Имя слишком длинное. Попробуй ещё раз:")
            return
        db.update_user(user_id, name=text, state='awaiting_birthdate')
        await update.message.reply_text(
            f"Отлично, <b>{text}</b>! 👍\n\nТеперь введи дату рождения в формате <b>ДД.ММ.ГГГГ</b>\nНапример: 22.06.1995",
            parse_mode=constants.ParseMode.HTML
        )
        return
    
    if state == 'awaiting_birthdate':
        birthdate = parse_date(text)
        if not birthdate:
            await update.message.reply_text(
                "❌ Неверный формат даты.\n\nВведи дату в формате <b>ДД.ММ.ГГГГ</b>",
                parse_mode=constants.ParseMode.HTML
            )
            return
        if birthdate.year < 1900 or birthdate > datetime.now():
            await update.message.reply_text("❌ Некорректная дата рождения. Попробуй ещё раз:")
            return
        db.update_user(user_id, birthdate=text, state='idle')
        db.log_action(user_id, 'registration_complete')
        user = db.get_user(user_id)
        d = datetime.strptime(user['birthdate'], "%d.%m.%Y")
        report = build_full_report(user['name'], d)
        await update.message.reply_text(report, parse_mode=constants.ParseMode.HTML)
        is_pro = db.is_pro_user(user_id)
        await update.message.reply_text(
            "✅ <b>Регистрация завершена!</b>\n\nВыбери нужный раздел:",
            parse_mode=constants.ParseMode.HTML,
            reply_markup=main_menu(is_pro)
        )
        return
    
    await update.message.reply_text(
        "Я тебя слышу! 😊\n\nЧтобы получить отчёт, напиши /start\nЧтобы открыть меню, нажми /menu"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    callback_data = query.data
    user = db.get_user(user_id)
    if not user:
        db.create_user(user_id, query.from_user.username)
        user = db.get_user(user_id)
    is_pro = db.is_pro_user(user_id)
    
    if callback_data == "menu":
        await query.message.reply_text("🏠 <b>Главное меню</b>", parse_mode=constants.ParseMode.HTML, reply_markup=main_menu(is_pro))
        return
    
    if not user.get('birthdate'):
        await query.message.reply_text("⚠️ Сначала пройди регистрацию: /start", reply_markup=back_menu())
        return
    
    pro_required = ['compat', 'practices', 'guide', 'media', 'test', 'ask_ai', 'calendar']
    if callback_data in pro_required and not is_pro:
        await query.message.reply_text(
            "🔒 Этот раздел доступен только в PRO версии.\n\n⭐ Оформи подписку!",
            parse_mode=constants.ParseMode.HTML,
            reply_markup=main_menu(is_pro)
        )
        return
    
    if callback_data == "card":
        d = datetime.strptime(user['birthdate'], "%d.%m.%Y")
        report = build_full_report(user['name'], d)
        await query.message.reply_text(report, parse_mode=constants.ParseMode.HTML, reply_markup=back_menu())
        return
    
    if callback_data == "compat":
        await query.message.reply_text(
            "❤️ <b>Совместимость</b>\n\nВведи дату рождения партнёра в формате <b>ДД.ММ.ГГГГ</b>",
            parse_mode=constants.ParseMode.HTML,
            reply_markup=back_menu()
        )
        return
    
    if callback_data == "practices":
        await query.message.reply_text("✨ <b>Практики роста</b>\n\nСкоро здесь будут персональные рекомендации!", parse_mode=constants.ParseMode.HTML, reply_markup=back_menu())
        return
    
    if callback_data == "guide":
        await query.message.reply_text("📚 <b>Личный гайд</b>\n\nСкоро здесь будет твой план развития!", parse_mode=constants.ParseMode.HTML, reply_markup=back_menu())
        return
    
    if callback_data == "media":
        await query.message.reply_text("🎬 <b>Книги и фильмы</b>\n\nСкоро здесь будут рекомендации!", parse_mode=constants.ParseMode.HTML, reply_markup=back_menu())
        return
    
    if callback_data == "test":
        await query.message.reply_text("📝 <b>Мини-тест</b>\n\nСкоро здесь будет тест!", parse_mode=constants.ParseMode.HTML, reply_markup=back_menu())
        return
    
    if callback_data == "ask_ai":
        await query.message.reply_text(
            "🤖 <b>Спросить AI</b>\n\nЗадай любой вопрос о своей личности, отношениях, карьере.",
            parse_mode=constants.ParseMode.HTML,
            reply_markup=back_menu()
        )
        return
    
    if callback_data == "calendar":
        await query.message.reply_text("📅 <b>Календарь</b>\n\nСкоро здесь будет твой календарь!", parse_mode=constants.ParseMode.HTML, reply_markup=back_menu())
        return
    
    if callback_data == "profile":
        status = "⭐ PRO" if is_pro else "🆓 FREE"
        await query.message.reply_text(
            f"👤 <b>Профиль</b>\n\nИмя: {user['name']}\nДата рождения: {user['birthdate']}\nСтатус: {status}",
            parse_mode=constants.ParseMode.HTML,
            reply_markup=back_menu()
        )
        return
    
    if callback_data == "clear_history":
        await query.message.reply_text("🗑 История диалога очищена!", parse_mode=constants.ParseMode.HTML, reply_markup=back_menu())
        return
    
    if callback_data == "subscription":
        await query.message.reply_text(
            "⭐ <b>PRO подписка</b>\n\n"
            "✅ Безлимит запросов\n"
            "✅ AI с памятью\n"
            "✅ Совместимость\n"
            "✅ Практики и рекомендации\n"
            "✅ Книги и фильмы\n"
            "✅ Календарь\n\n"
            "💳 1 месяц — 319₽\n"
            "💳 1 год — 1990₽",
            parse_mode=constants.ParseMode.HTML,
            reply_markup=back_menu()
        )
        return

# ==== ЗАПУСК БОТА ====
def main():
    logger.info("🚀 Запуск бота...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("✅ Бот успешно запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
async def main_async():
    """Асинхронная версия main для Python 3.14"""
    import logging
    logger = logging.getLogger("numerology_bot")
    logger.info("🚀 Запуск бота (async)...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("✅ Бот успешно запущен!")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Синхронная обёртка"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_async())

if __name__ == "__main__":
    main()
    
async def main_async():
    """Асинхронная версия main для Python 3.14"""
    logger.info("🚀 Запуск бота (async)...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("✅ Бот успешно запущен!")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Синхронная обёртка"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_async())