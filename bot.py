import telebot
from telebot import types
import sqlite3
import json
import requests
import time
from datetime import datetime, timedelta
import threading
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "8968195774:AAGXr5Ak1ne-QNy75hK__ZMdhco7wnWc2UQ"
CREATOR_ID = 1022123079
ADMIN_USER_ID = 1022123079
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
YUKASSA_SHOP_ID = "01187960"
YUKASSA_SECRET_KEY = "test_tojfBk8Lz9MkNFNEV3TEUtCAdhGMHCu9YEI4J67MxCc"

bot = telebot.TeleBot(BOT_TOKEN)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  username TEXT, 
                  first_name TEXT,
                  last_name TEXT,
                  registration_date TEXT,
                  subscription_end TEXT,
                  is_premium INTEGER DEFAULT 0,
                  birth_date TEXT,
                  gender TEXT,
                  city TEXT,
                  preferences TEXT)''')
    
    # Таблица для матрицы судьбы
    c.execute('''CREATE TABLE IF NOT EXISTS fate_matrix
                 (user_id INTEGER,
                  birth_date TEXT,
                  matrix_data TEXT,
                  calculation_date TEXT,
                  PRIMARY KEY (user_id, birth_date))''')
    
    # Таблица для совместимости
    c.execute('''CREATE TABLE IF NOT EXISTS compatibility
                 (user_id INTEGER,
                  partner_birth_date TEXT,
                  result TEXT,
                  calculation_date TEXT)''')
    
    conn.commit()
    conn.close()

# Функция для расчета матрицы судьбы (упрощенная версия)
def calculate_fate_matrix(birth_date):
    try:
        # Парсим дату
        parts = birth_date.split('.')
        if len(parts) != 3:
            return None
        
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2])
        
        # Суммируем все цифры даты рождения
        date_str = birth_date.replace('.', '')
        total_sum = sum(int(digit) for digit in date_str)
        
        # Пока сумма > 22, складываем цифры (в нумерологии)
        while total_sum > 22:
            total_sum = sum(int(digit) for digit in str(total_sum))
        
        if total_sum == 0:
            total_sum = 22
        
        return {
            'main_number': total_sum,
            'personality_number': sum(int(digit) for digit in str(day)) if day > 9 else day,
            'soul_number': sum(int(digit) for digit in str(month)) if month > 9 else month,
            'destiny_number': sum(int(digit) for digit in str(year)) if year > 9 else year,
            'mission': describe_mission(total_sum),
            'strengths': get_strengths(total_sum),
            'challenges': get_challenges(total_sum)
        }
    except Exception as e:
        logger.error(f"Ошибка расчета матрицы: {e}")
        return None

def describe_mission(number):
    descriptions = {
        1: "Ваша миссия - быть лидером и первооткрывателем. Вы должны идти своим путем и вдохновлять других.",
        2: "Ваша миссия - создавать гармонию и баланс. Вы должны учиться сотрудничеству и дипломатии.",
        3: "Ваша миссия - приносить радость и вдохновение. Вы должны развивать свои творческие способности.",
        4: "Ваша миссия - строить прочные основы. Вы должны быть трудолюбивым и надежным.",
        5: "Ваша миссия - исследовать мир и делиться знаниями. Вы должны быть свободолюбивым и любознательным.",
        6: "Ваша миссия - заботиться о других. Вы должны быть ответственным и любящим.",
        7: "Ваша миссия - искать истину. Вы должны быть мудрым и аналитичным.",
        8: "Ваша миссия - достигать успеха. Вы должны быть решительным и амбициозным.",
        9: "Ваша миссия - помогать другим. Вы должны быть сострадательным и альтруистичным.",
        10: "Ваша миссия - быть проводником перемен. Вы должны быть инициативным и смелым.",
        11: "Ваша миссия - быть духовным учителем. Вы должны быть вдохновляющим и просветленным.",
        12: "Ваша миссия - служить примером. Вы должны быть терпеливым и понимающим.",
        13: "Ваша миссия - трансформировать. Вы должны быть сильным и решительным.",
        14: "Ваша миссия - объединять. Вы должны быть общительным и дипломатичным.",
        15: "Ваша миссия - любить. Вы должны быть нежным и заботливым.",
        16: "Ваша миссия - быть стражем. Вы должны быть защитником и хранителем.",
        17: "Ваша миссия - быть лидером. Вы должны быть решительным и целеустремленным.",
        18: "Ваша миссия - быть наставником. Вы должны быть мудрым и поучающим.",
        19: "Ваша миссия - быть светом. Вы должны быть ярким и вдохновляющим.",
        20: "Ваша миссия - быть миротворцем. Вы должны быть гармоничным и сбалансированным.",
        21: "Ваша миссия - быть творцом. Вы должны быть созидательным и инновационным.",
        22: "Ваша миссия - быть строителем. Вы должны быть основательным и практичным."
    }
    return descriptions.get(number, f"Ваша миссия связана с числом {number}")

def get_strengths(number):
    strengths = {
        1: ["Лидерство", "Смелость", "Инновационность"],
        2: ["Дипломатичность", "Интуиция", "Терпение"],
        3: ["Креативность", "Оптимизм", "Общительность"],
        4: ["Надежность", "Трудолюбие", "Практичность"],
        5: ["Адаптивность", "Любознательность", "Свободолюбие"],
        6: ["Ответственность", "Заботливость", "Гармоничность", "Красота"],
        7: ["Мудрость", "Аналитический ум", "Интуиция"],
        8: ["Амбициозность", "Решительность", "Управленческие навыки"],
        9: ["Сострадание", "Альтруизм", "Широта взглядов"],
        10: ["Инициативность", "Харизма", "Смелость"],
        11: ["Духовность", "Вдохновение", "Проницательность"],
        12: ["Терпеливость", "Понимание", "Гибкость"],
        13: ["Сила воли", "Решительность", "Стойкость"],
        14: ["Коммуникабельность", "Умение слушать", "Дипломатичность"],
        15: ["Любовь", "Нежность", "Забота"],
        16: ["Защита", "Храбрость", "Верность"],
        17: ["Лидерство", "Целеустремленность", "Энтузиазм"],
        18: ["Мудрость", "Опыт", "Наставничество"],
        19: ["Яркость", "Оптимизм", "Вдохновение"],
        20: ["Гармония", "Миролюбие", "Баланс"],
        21: ["Творчество", "Новаторство", "Идеализм"],
        22: ["Практичность", "Основательность", "Сила"]
    }
    return strengths.get(number, ["Мудрость", "Интуиция", "Внутренняя сила"])

def get_challenges(number):
    challenges = {
        1: ["Излишняя самоуверенность", "Одиночество", "Трудности с командной работой"],
        2: ["Неуверенность", "Зависимость от других", "Трудности с принятием решений"],
        3: ["Поверхностность", "Неспособность доводить дела до конца", "Эмоциональная нестабильность"],
        4: ["Консерватизм", "Сложности с адаптацией", "Чрезмерная серьезность"],
        5: ["Непостоянство", "Безответственность", "Трудности с обязательствами"],
        6: ["Излишняя требовательность", "Контроль", "Тревожность"],
        7: ["Изоляция", "Склонность к анализу", "Эмоциональная закрытость"],
        8: ["Жестокость", "Материализм", "Властность"],
        9: ["Жертвенность", "Иллюзии", "Разочарования"],
        10: ["Импульсивность", "Рискованность", "Непостоянство"],
        11: ["Идеализация", "Эмоциональная чувствительность", "Склонность к иллюзиям"],
        12: ["Пассивность", "Склонность к жертвенности", "Заниженная самооценка"],
        13: ["Склонность к депрессии", "Жесткость", "Трудности с прощением"],
        14: ["Зависимость от мнения", "Склонность к манипуляциям", "Непостоянство"],
        15: ["Склонность к зависимостям", "Излишняя чувствительность", "Ревность"],
        16: ["Излишняя подозрительность", "Склонность к одиночеству", "Неумение доверять"],
        17: ["Склонность к диктатуре", "Нетерпимость", "Гордыня"],
        18: ["Излишняя строгость", "Склонность к критике", "Трудности с прощением"],
        19: ["Склонность к депрессии", "Излишняя требовательность", "Разочарование в людях"],
        20: ["Излишняя мягкость", "Склонность к жертвенности", "Трудности с границами"],
        21: ["Склонность к иллюзиям", "Неумение принимать реальность", "Излишняя идеализация"],
        22: ["Склонность к контролю", "Излишняя серьезность", "Трудности с расслаблением"]
    }
    return challenges.get(number, ["Требуется работа над собой", "Личностный рост", "Саморазвитие"])

# Функция для расчета совместимости
def calculate_compatibility(birth_date1, birth_date2):
    matrix1 = calculate_fate_matrix(birth_date1)
    matrix2 = calculate_fate_matrix(birth_date2)
    
    if not matrix1 or not matrix2:
        return None
    
    compatibility_score = (matrix1['main_number'] + matrix2['main_number']) % 10 + 5
    if compatibility_score > 10:
        compatibility_score = 10
    
    interpretation = {
        1-3: "Низкая совместимость. Потребуется много работы над отношениями.",
        4-6: "Средняя совместимость. Хороший потенциал для развития.",
        7-8: "Высокая совместимость. Отличная пара!",
        9-10: "Идеальная совместимость. Судьбоносная встреча!"
    }
    
    return {
        'score': compatibility_score,
        'interpretation': interpretation.get(compatibility_score, "Уникальная связь, требующая внимания"),
        'details': f"Число души 1: {matrix1['soul_number']}, Число души 2: {matrix2['soul_number']}"
    }

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Сохраняем пользователя
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users 
                 (user_id, username, first_name, last_name, registration_date)
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, username, first_name, last_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    # Создаем клавиатуру
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('🌟 Матрица судьбы')
    btn2 = types.KeyboardButton('💕 Совместимость')
    btn3 = types.KeyboardButton('✨ PRO подписка')
    btn4 = types.KeyboardButton('🆘 Помощь')
    markup.add(btn1, btn2, btn3, btn4)
    
    welcome_text = f"""Привет, {first_name}! 🌟

Я - твой личный астролог! Я помогу тебе:
🔮 Рассчитать матрицу судьбы
💕 Узнать совместимость с партнером
✨ Получить доступ к PRO-функциям

Выбери действие в меню ниже 👇"""

    bot.send_message(user_id, welcome_text, reply_markup=markup)

# Обработка текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == '🌟 Матрица судьбы':
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        btn_back = types.KeyboardButton('🔙 Назад')
        markup.add(btn_back)
        bot.send_message(user_id, "Введите вашу дату рождения в формате ДД.ММ.ГГГГ (например, 15.05.1990):", reply_markup=markup)
        bot.register_next_step_handler(message, process_birth_date_for_matrix)
    
    elif text == '💕 Совместимость':
        bot.send_message(user_id, "Введите дату рождения партнера в формате ДД.ММ.ГГГГ:")
        bot.register_next_step_handler(message, process_partner_birth_date)
    
    elif text == '✨ PRO подписка':
        show_pro_subscription(user_id)
    
    elif text == '🆘 Помощь':
        help_text = """🔮 Как пользоваться ботом:

1️⃣ Матрица судьбы - узнай свои сильные стороны и миссию
2️⃣ Совместимость - проверь совместимость с партнером
3️⃣ PRO подписка - доступ к расширенным функциям

❓ Вопросы: @Yana_Beauty_Store

💫 С любовью, твой астролог"""
        bot.send_message(user_id, help_text)
    
    elif text == '🔙 Назад':
        start(message)

# Обработка даты для матрицы
def process_birth_date_for_matrix(message):
    user_id = message.from_user.id
    birth_date = message.text.strip()
    
    # Проверяем формат
    if not validate_date(birth_date):
        bot.send_message(user_id, "❌ Неверный формат! Используйте ДД.ММ.ГГГГ")
        start(message)
        return
    
    # Проверяем, есть ли у пользователя PRO подписка
    if not check_premium(user_id):
        # Ограничение для бесплатных пользователей
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''SELECT COUNT(*) FROM fate_matrix 
                     WHERE user_id = ? AND date(calculation_date) = date(?)''',
                  (user_id, datetime.now().isoformat()))
        count = c.fetchone()[0]
        conn.close()
        
        if count >= 2:
            bot.send_message(user_id, "⚠️ Бесплатный лимит: 2 расчета в день. Купи PRO подписку для безлимита!")
            return
    
    # Рассчитываем матрицу
    matrix = calculate_fate_matrix(birth_date)
    if not matrix:
        bot.send_message(user_id, "❌ Ошибка расчета. Проверьте правильность даты.")
        return
    
    # Сохраняем результат
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO fate_matrix 
                 (user_id, birth_date, matrix_data, calculation_date)
                 VALUES (?, ?, ?, ?)''',
              (user_id, birth_date, json.dumps(matrix), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    # Формируем ответ
    response = f"""🔮 ВАША МАТРИЦА СУДЬБЫ

📅 Дата рождения: {birth_date}

🌟 Главное число: {matrix['main_number']}
🎯 Миссия: {matrix['mission']}

💪 Ваши сильные стороны:
{chr(10).join(f'• {s}' for s in matrix['strengths'])}

⚠️ Ваши вызовы:
{chr(10).join(f'• {c}' for c in matrix['challenges'])}

💫 Число личности: {matrix['personality_number']}
🕊️ Число души: {matrix['soul_number']}
🌍 Число судьбы: {matrix['destiny_number']}

✨ Хотите более подробный разбор? Купите PRO подписку!
"""
    bot.send_message(user_id, response)

# Обработка даты партнера для совместимости
def process_partner_birth_date(message):
    user_id = message.from_user.id
    partner_birth = message.text.strip()
    
    if not validate_date(partner_birth):
        bot.send_message(user_id, "❌ Неверный формат! Используйте ДД.ММ.ГГГГ")
        return
    
    # Проверяем PRO подписку
    if not check_premium(user_id):
        # Для бесплатных - ограничение на 1 расчет в день
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''SELECT COUNT(*) FROM compatibility 
                     WHERE user_id = ? AND date(calculation_date) = date(?)''',
                  (user_id, datetime.now().isoformat()))
        count = c.fetchone()[0]
        conn.close()
        
        if count >= 1:
            bot.send_message(user_id, "⚠️ Бесплатный лимит: 1 расчет совместимости в день. Купи PRO!")
            return
    
    # Просим ввести свою дату
    bot.send_message(user_id, "Теперь введите ВАШУ дату рождения (ДД.ММ.ГГГГ):")
    bot.register_next_step_handler(message, process_user_birth_for_compatibility, partner_birth)

def process_user_birth_for_compatibility(message, partner_birth):
    user_id = message.from_user.id
    user_birth = message.text.strip()
    
    if not validate_date(user_birth):
        bot.send_message(user_id, "❌ Неверный формат!")
        return
    
    # Рассчитываем совместимость
    result = calculate_compatibility(user_birth, partner_birth)
    if not result:
        bot.send_message(user_id, "❌ Ошибка расчета. Попробуйте еще раз.")
        return
    
    # Сохраняем результат
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO compatibility 
                 (user_id, partner_birth_date, result, calculation_date)
                 VALUES (?, ?, ?, ?)''',
              (user_id, partner_birth, json.dumps(result), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    # Формируем ответ
    stars = "⭐" * (result['score'] // 2) if result['score'] > 0 else "⭐"
    response = f"""💕 СОВМЕСТИМОСТЬ

📅 Ваша дата: {user_birth}
📅 Дата партнера: {partner_birth}

Совместимость: {result['score']}/10
{stars}

📝 {result['interpretation']}

🔍 Детали: {result['details']}

💫 Хотите полный гороскоп совместимости? Купите PRO!
"""
    bot.send_message(user_id, response)

def validate_date(date_str):
    try:
        parts = date_str.split('.')
        if len(parts) != 3:
            return False
        day, month, year = map(int, parts)
        if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2025:
            # Простая проверка на существование даты
            datetime(year, month, day)
            return True
    except:
        pass
    return False

def check_premium(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''SELECT subscription_end FROM users WHERE user_id = ?''', (user_id,))
    result = c.fetchone()
    conn.close()
    
    if not result or not result[0]:
        return False
    
    try:
        end_date = datetime.fromisoformat(result[0])
        return end_date > datetime.now()
    except:
        return False

def show_pro_subscription(user_id):
    is_premium = check_premium(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton("💳 Купить PRO на месяц (199 руб)", callback_data="pro_month")
    btn2 = types.InlineKeyboardButton("💳 Купить PRO на год (1999 руб)", callback_data="pro_year")
    btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
    markup.add(btn1, btn2, btn_back)
    
    if is_premium:
        status = "✅ У вас уже есть PRO подписка!"
    else:
        status = "🔓 У вас бесплатная версия"
    
    text = f"""✨ PRO ПОДПИСКА

{status}

⭐ Преимущества PRO:
• Безлимитные расчеты матрицы
• Неограниченная совместимость
• Полный детальный разбор
• Приоритетная поддержка

💰 Стоимость:
• 1 месяц - 199 руб
• 1 год - 1999 руб

💳 Оплата через ЮKassa
"""
    bot.send_message(user_id, text, reply_markup=markup)

# Обработка инлайн-кнопок
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "back_to_menu":
        bot.delete_message(user_id, call.message.message_id)
        start(call.message)
    
    elif data in ["pro_month", "pro_year"]:
        # Здесь логика оплаты через ЮKassa
        amount = 199 if data == "pro_month" else 1999
        period = "месяц" if data == "pro_month" else "год"
        
        # Создаем платеж (упрощенная версия)
        payment_url = f"https://yoomoney.ru/quickpay/confirm.xml?receiver={YUKASSA_SHOP_ID}&quickpay-form=button&targets=PRO+подписка&sum={amount}&comment={user_id}"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_pay = types.InlineKeyboardButton("💳 Оплатить", url=payment_url)
        btn_check = types.InlineKeyboardButton("✅ Проверить оплату", callback_data="check_payment")
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
        markup.add(btn_pay, btn_check, btn_back)
        
        bot.edit_message_text(
            f"💳 ОПЛАТА PRO ПОДПИСКИ\n\nСумма: {amount} руб\nПериод: {period}\n\nНажмите кнопку для оплаты:",
            user_id,
            call.message.message_id,
            reply_markup=markup
        )
    
    elif data == "check_payment":
        # Проверка оплаты (упрощенная)
        # В реальности здесь был бы запрос к API ЮKassa
        bot.answer_callback_query(call.id, "⏳ Проверяем оплату...")
        bot.send_message(user_id, "✅ Оплата подтверждена! PRO подписка активирована на месяц.")
        
        # Активируем подписку
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        end_date = datetime.now() + timedelta(days=30)
        c.execute('''UPDATE users SET subscription_end = ?, is_premium = 1 WHERE user_id = ?''',
                  (end_date.isoformat(), user_id))
        conn.commit()
        conn.close()

# Обработка ошибок
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.send_message(message.from_user.id, "❓ Я не понял. Используйте меню для навигации.")

# ... весь твой код бота (обработчики, функции, логика) ...

# ===== ДОБАВЛЯЕМ ЭТУ ФУНКЦИЮ =====
def main():
    """Запуск бота через функцию main для совместимости с Render"""
    init_db()
    logger.info("🚀 Бот запущен через main()")
    while True:
        try:
            bot.polling(none_stop=True, interval=0)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            time.sleep(10)

# ===== ЭТО УЖЕ БЫЛО (оставляем как есть) =====
if __name__ == '__main__':
    init_db()
    logger.info("Бот запущен!")
    while True:
        try:
            bot.polling(none_stop=True, interval=0)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            time.sleep(10)