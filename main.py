import logging
import os
import sqlite3
import requests
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ================== НАСТРОЙКИ ==================
TELEGRAM_BOT_TOKEN = '8107230002:AAEWIQiPbgL4lXJ6eeYwrOA3-jFYDQeuV04'   # замените на свой токен
CRYPTO_BOT_TOKEN = '509179:AAHycIbTUPLk87WcaOiTFob9mvNQ3FmEZT6'       # токен от @CryptoBot
ADMIN_IDS = [5459547413]                           # ID администраторов

WELCOME_IMAGE = 'welcome.png'
BUY_IMAGE = 'buy.png'

FILES_DIR = 'product_files'
os.makedirs(FILES_DIR, exist_ok=True)

# ================== БД ==================
conn = sqlite3.connect('shop.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    is_blocked INTEGER DEFAULT 0,
    is_admin INTEGER DEFAULT 0,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER,
    name TEXT,
    description TEXT,
    price_ton REAL,
    price_btc REAL,
    price_eth REAL,
    price_usdt REAL,
    price_bnb REAL,
    price_ltc REAL,
    price_doge REAL,
    price_trx REAL,
    price_not REAL,
    file_path TEXT,
    FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    invoice_id TEXT,
    currency TEXT,
    amount REAL,
    status TEXT,
    paid_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (product_id) REFERENCES products (id)
)
''')
conn.commit()

# ================== БОТ ==================
storage = MemoryStorage()
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=storage)

logging.basicConfig(level=logging.INFO)

CRYPTO_API_URL = 'https://pay.crypt.bot/api'

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================
def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    return cursor.fetchone()

def add_user(user_id, username, first_name, last_name):
    cursor.execute('''
        INSERT OR IGNORE INTO users (id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name))
    conn.commit()

def is_blocked(user_id):
    user = get_user(user_id)
    return user and user[4] == 1

def is_admin(user_id):
    if user_id in ADMIN_IDS:
        return True
    user = get_user(user_id)
    return user and user[5] == 1

def create_invoice(asset, amount, description):
    url = f"{CRYPTO_API_URL}/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "asset": asset,
        "amount": str(amount),
        "description": description,
        "payload": "custom_payload"
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Ошибка создания счета: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Исключение при создании счета: {e}")
        return None

def check_invoice_status(invoice_id):
    url = f"{CRYPTO_API_URL}/getInvoices"
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    params = {"invoice_ids": invoice_id}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Ошибка проверки статуса: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Исключение при проверке статуса: {e}")
        return None

# ================== FSM ==================
class AddCategory(StatesGroup):
    name = State()

class AddProduct(StatesGroup):
    category = State()
    name = State()
    description = State()
    price_ton = State()
    price_btc = State()
    price_eth = State()
    price_usdt = State()
    price_bnb = State()
    price_ltc = State()
    price_doge = State()
    price_trx = State()
    price_not = State()
    file = State()

# ================== КЛАВИАТУРЫ ==================
def main_menu_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.row(
        InlineKeyboardButton("📁 Категории", callback_data="categories_page_1"),
        InlineKeyboardButton("📢 Канал", url="https://t.me/nevsky_chanel")  # ← ссылка изменена
    )
    keyboard.row(InlineKeyboardButton("💬 Поддержка", callback_data="support"))
    if is_admin(user_id):
        keyboard.row(InlineKeyboardButton("⚙️ Админ панель", callback_data="admin_panel"))
    return keyboard

def back_to_main_button():
    return InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ На главную", callback_data="back_to_main"))

# ================== ОБРАБОТЧИКИ ==================
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    if is_blocked(user_id):
        await message.reply("⛔ Вы заблокированы и не можете пользоваться ботом.")
        return

    add_user(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )

    first_name = message.from_user.first_name or "пользователь"
    welcome_text = (f"👋 Добро пожаловать, {first_name}!\n"
                    f"Создатель этого бота: @ponevsky\n"
                    f"Приятного времяпрепровождения в Nevsky Shop!")

    if os.path.exists(WELCOME_IMAGE):
        with open(WELCOME_IMAGE, 'rb') as photo:
            await bot.send_photo(
                message.chat.id,
                photo,
                caption=welcome_text,
                reply_markup=main_menu_keyboard(user_id)
            )
    else:
        await message.answer(welcome_text, reply_markup=main_menu_keyboard(user_id))

@dp.callback_query_handler(lambda c: c.data == 'back_to_main')
async def back_to_main(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if is_blocked(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Вы заблокированы.")
        return

    await bot.answer_callback_query(callback_query.id)
    await start(callback_query.message)

# ================== КАТЕГОРИИ И ТОВАРЫ (ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ) ==================
@dp.callback_query_handler(lambda c: c.data.startswith('categories_page_'))
async def show_categories(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if is_blocked(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Вы заблокированы.")
        return

    page = int(callback_query.data.split('_')[-1])
    cursor.execute('SELECT id, name FROM categories ORDER BY name')
    categories = cursor.fetchall()
    if not categories:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="📂 Категории пока пусты.",
            reply_markup=back_to_main_button()
        )
        return

    per_page = 5
    total_pages = (len(categories) + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    page_cats = categories[start:end]

    keyboard = InlineKeyboardMarkup(row_width=2)
    for cat_id, cat_name in page_cats:
        keyboard.add(InlineKeyboardButton(cat_name, callback_data=f"category_{cat_id}_page_1"))

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"categories_page_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"categories_page_{page+1}"))
    if nav_buttons:
        keyboard.row(*nav_buttons)
    keyboard.row(InlineKeyboardButton("⬅️ На главную", callback_data="back_to_main"))

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="📂 Выберите категорию:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('category_'))
async def show_products(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if is_blocked(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Вы заблокированы.")
        return

    _, cat_id, _, page = callback_query.data.split('_')
    cat_id = int(cat_id)
    page = int(page)

    cursor.execute('SELECT id, name, description, price_usdt FROM products WHERE category_id = ?', (cat_id,))
    products = cursor.fetchall()
    if not products:
        await bot.answer_callback_query(callback_query.id, "В этой категории пока нет товаров.")
        return

    per_page = 5
    total_pages = (len(products) + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    page_prods = products[start:end]

    keyboard = InlineKeyboardMarkup(row_width=1)
    for prod_id, name, desc, price in page_prods:
        btn_text = f"{name} - {price} USDT"
        keyboard.add(InlineKeyboardButton(btn_text, callback_data=f"product_{prod_id}"))

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"category_{cat_id}_page_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"category_{cat_id}_page_{page+1}"))
    if nav_buttons:
        keyboard.row(*nav_buttons)
    keyboard.row(InlineKeyboardButton("⬅️ К категориям", callback_data="categories_page_1"))

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="📦 Выберите товар:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('product_'))
async def show_product_details(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if is_blocked(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Вы заблокированы.")
        return

    prod_id = int(callback_query.data.split('_')[1])
    cursor.execute('''
        SELECT name, description, price_ton, price_btc, price_eth, price_usdt,
               price_bnb, price_ltc, price_doge, price_trx, price_not, category_id
        FROM products WHERE id = ?
    ''', (prod_id,))
    prod = cursor.fetchone()
    if not prod:
        await bot.answer_callback_query(callback_query.id, "Товар не найден.")
        return

    name, desc, *prices, cat_id = prod
    currency_names = ['TON', 'BTC', 'ETH', 'USDT', 'BNB', 'LTC', 'DOGE', 'TRX', 'NOT']
    price_text = ""
    for i, curr in enumerate(currency_names):
        if prices[i] and prices[i] > 0:
            price_text += f"{curr}: {prices[i]}\n"

    caption = f"<b>{name}</b>\n\n{desc}\n\nЦены:\n{price_text}"

    if os.path.exists(BUY_IMAGE):
        with open(BUY_IMAGE, 'rb') as photo:
            await bot.send_photo(
                callback_query.from_user.id,
                photo,
                caption=caption,
                reply_markup=get_product_buy_keyboard(prod_id, cat_id)
            )
    else:
        await bot.send_message(
            callback_query.from_user.id,
            caption,
            reply_markup=get_product_buy_keyboard(prod_id, cat_id)
        )
    await bot.answer_callback_query(callback_query.id)

def get_product_buy_keyboard(prod_id, cat_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("💳 Купить", callback_data=f"buy_{prod_id}"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"category_{cat_id}_page_1"))
    return keyboard

# ================== ПОКУПКА ==================
@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def buy_product(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if is_blocked(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Вы заблокированы.")
        return

    prod_id = int(callback_query.data.split('_')[1])
    cursor.execute('SELECT name FROM products WHERE id = ?', (prod_id,))
    prod_name = cursor.fetchone()
    if not prod_name:
        await bot.answer_callback_query(callback_query.id, "Товар не найден.")
        return

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        f"💰 Выберите способ оплаты для товара \"{prod_name[0]}\":",
        reply_markup=get_payment_keyboard(prod_id)
    )

def get_payment_keyboard(prod_id):
    cursor.execute('''
        SELECT price_ton, price_btc, price_eth, price_usdt,
               price_bnb, price_ltc, price_doge, price_trx, price_not
        FROM products WHERE id = ?
    ''', (prod_id,))
    prices = cursor.fetchone()
    if not prices:
        return InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Ошибка", callback_data="none"))

    currency_names = ['TON', 'BTC', 'ETH', 'USDT', 'BNB', 'LTC', 'DOGE', 'TRX', 'NOT']
    keyboard = InlineKeyboardMarkup(row_width=2)
    for i, curr in enumerate(currency_names):
        if prices[i] and prices[i] > 0:
            keyboard.add(InlineKeyboardButton(f"💸 {curr} - {prices[i]}", callback_data=f"pay_{prod_id}_{curr}"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"product_{prod_id}"))
    return keyboard

@dp.callback_query_handler(lambda c: c.data.startswith('pay_'))
async def process_payment(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if is_blocked(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Вы заблокированы.")
        return

    _, prod_id, currency = callback_query.data.split('_')
    prod_id = int(prod_id)

    cursor.execute(f'SELECT price_{currency.lower()}, name FROM products WHERE id = ?', (prod_id,))
    result = cursor.fetchone()
    if not result or not result[0]:
        await bot.answer_callback_query(callback_query.id, "Цена для этой валюты не установлена.")
        return
    amount, prod_name = result

    invoice = create_invoice(asset=currency, amount=amount, description=f"Оплата за {prod_name}")
    if invoice and 'result' in invoice:
        pay_url = invoice['result']['pay_url']
        invoice_id = invoice['result']['invoice_id']

        cursor.execute('''
            INSERT INTO payments (user_id, product_id, invoice_id, currency, amount, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (user_id, prod_id, invoice_id, currency, amount))
        conn.commit()

        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(
            callback_query.from_user.id,
            f"💳 Ссылка для оплаты: {pay_url}\n\n"
            f"После оплаты товар будет отправлен автоматически."
        )
        asyncio.create_task(check_payment_loop(user_id, invoice_id, prod_id))
    else:
        await bot.answer_callback_query(callback_query.id, "❌ Ошибка при создании счета")

async def check_payment_loop(user_id, invoice_id, prod_id):
    while True:
        await asyncio.sleep(5)
        invoice_status = check_invoice_status(invoice_id)
        if invoice_status and 'result' in invoice_status:
            items = invoice_status['result'].get('items', [])
            if items and items[0]['status'] == 'paid':
                cursor.execute('''
                    UPDATE payments SET status = 'paid', paid_at = CURRENT_TIMESTAMP
                    WHERE invoice_id = ?
                ''', (invoice_id,))
                conn.commit()

                cursor.execute('SELECT file_path, name FROM products WHERE id = ?', (prod_id,))
                file_path, prod_name = cursor.fetchone()
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        await bot.send_document(
                            user_id,
                            f,
                            caption=f"✅ Спасибо за покупку!\n\nВаш товар: {prod_name}"
                        )
                else:
                    await bot.send_message(user_id, "❌ Файл товара не найден. Обратитесь в поддержку.")
                break

# ================== ПОДДЕРЖКА ==================
@dp.callback_query_handler(lambda c: c.data == 'support')
async def support_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if is_blocked(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Вы заблокированы.")
        return

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        "📩 Напишите ваше сообщение для поддержки. Можно отправить текст, фото, видео или другой файл."
    )

@dp.message_handler(content_types=['text', 'photo', 'video', 'document'])
async def handle_support_message(message: types.Message):
    user_id = message.from_user.id
    if is_blocked(user_id):
        await message.reply("⛔ Вы заблокированы.")
        return

    first_name = message.from_user.first_name or "отсутствует"
    last_name = message.from_user.last_name or "отсутствует"
    username = message.from_user.username or "отсутствует"

    admin_message = f"👤 Вам написал пользователь {user_id}\n" \
                    f"Имя: {first_name}\n" \
                    f"Фамилия: {last_name}\n" \
                    f"Username: @{username}\n\n"

    if message.text:
        admin_message += f"📄 Текст сообщения:\n{message.text}"
    elif message.photo:
        admin_message += "📷 Фото сообщения:"
    elif message.video:
        admin_message += "🎥 Видео сообщения:"
    elif message.document:
        admin_message += "📄 Файл сообщения:"

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_message)
            if message.photo or message.video or message.document:
                await message.copy_to(admin_id)
        except:
            pass

    await message.reply("✅ Ваше сообщение отправлено администратору на рассмотрение. Ожидайте ответа.")

# ================== АДМИН ПАНЕЛЬ ==================
@dp.callback_query_handler(lambda c: c.data == 'admin_panel')
async def admin_panel(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ У вас нет прав администратора.")
        return

    await bot.answer_callback_query(callback_query.id)
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👥 Пользователи", callback_data="admin_users_page_1"),
        InlineKeyboardButton("📁 Категории", callback_data="admin_categories"),
        InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add_product"),
        InlineKeyboardButton("📦 Список товаров", callback_data="admin_products_page_1"),
        InlineKeyboardButton("⬅️ На главную", callback_data="back_to_main")
    )
    await bot.send_message(
        callback_query.from_user.id,
        "⚙️ Административная панель:",
        reply_markup=keyboard
    )

# ================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ==================
@dp.callback_query_handler(lambda c: c.data.startswith('admin_users_page_'))
async def admin_users_list(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Нет прав.")
        return

    page = int(callback_query.data.split('_')[-1])
    cursor.execute('SELECT id, username, first_name, last_name, is_blocked FROM users ORDER BY id')
    users = cursor.fetchall()

    per_page = 5
    total_pages = (len(users) + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    page_users = users[start:end]

    text = f"👥 Список пользователей (страница {page}/{total_pages}):\n\n"
    keyboard = InlineKeyboardMarkup(row_width=1)
    for uid, uname, fname, lname, blocked in page_users:
        status = "🔴 Заблокирован" if blocked else "🟢 Активен"
        name = fname or "нет имени"
        if uname:
            name += f" (@{uname})"
        text += f"ID: {uid} - {name} - {status}\n"
        keyboard.add(InlineKeyboardButton(
            f"{'🔓 Разблокировать' if blocked else '🔒 Заблокировать'} {uid}",
            callback_data=f"admin_toggle_block_{uid}_{page}"
        ))

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"admin_users_page_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"admin_users_page_{page+1}"))
    if nav_buttons:
        keyboard.row(*nav_buttons)
    keyboard.row(InlineKeyboardButton("⬅️ Назад в админку", callback_data="admin_panel"))

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_toggle_block_'))
async def toggle_block_user(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Нет прав.")
        return

    _, _, _, uid, page = callback_query.data.split('_')
    uid = int(uid)
    cursor.execute('SELECT is_blocked FROM users WHERE id = ?', (uid,))
    res = cursor.fetchone()
    if res:
        new_status = 0 if res[0] == 1 else 1
        cursor.execute('UPDATE users SET is_blocked = ? WHERE id = ?', (new_status, uid))
        conn.commit()
        await bot.answer_callback_query(callback_query.id, "✅ Статус обновлён.")
    else:
        await bot.answer_callback_query(callback_query.id, "❌ Пользователь не найден.")

    callback_query.data = f"admin_users_page_{page}"
    await admin_users_list(callback_query)

# ================== УПРАВЛЕНИЕ КАТЕГОРИЯМИ ==================
@dp.callback_query_handler(lambda c: c.data == 'admin_categories')
async def admin_categories(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Нет прав.")
        return

    cursor.execute('SELECT id, name FROM categories')
    cats = cursor.fetchall()

    text = "📁 Категории:\n"
    keyboard = InlineKeyboardMarkup(row_width=2)
    for cat_id, name in cats:
        text += f"• {name} (ID: {cat_id})\n"
        keyboard.add(InlineKeyboardButton(f"❌ Удалить {name}", callback_data=f"admin_del_cat_{cat_id}"))
    if not cats:
        text += "Список пуст.\n"

    keyboard.row(InlineKeyboardButton("➕ Добавить категорию", callback_data="admin_add_cat"))
    keyboard.row(InlineKeyboardButton("⬅️ Назад в админку", callback_data="admin_panel"))

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_del_cat_'))
async def admin_delete_category(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Нет прав.")
        return

    cat_id = int(callback_query.data.split('_')[-1])
    cursor.execute('SELECT file_path FROM products WHERE category_id = ?', (cat_id,))
    for row in cursor.fetchall():
        file_path = row[0]
        if os.path.exists(file_path):
            os.remove(file_path)
    cursor.execute('DELETE FROM products WHERE category_id = ?', (cat_id,))
    cursor.execute('DELETE FROM categories WHERE id = ?', (cat_id,))
    conn.commit()
    await bot.answer_callback_query(callback_query.id, "✅ Категория и все её товары удалены.")
    await admin_categories(callback_query)

@dp.callback_query_handler(lambda c: c.data == 'admin_add_cat')
async def admin_add_category(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Нет прав.")
        return

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Введите название новой категории:")
    await AddCategory.name.set()

@dp.message_handler(state=AddCategory.name)
async def process_category_name(message: types.Message, state: FSMContext):
    cat_name = message.text.strip()
    try:
        cursor.execute('INSERT INTO categories (name) VALUES (?)', (cat_name,))
        conn.commit()
        await message.reply(f"✅ Категория '{cat_name}' создана.")
    except sqlite3.IntegrityError:
        await message.reply("❌ Категория с таким именем уже существует.")
    finally:
        await state.finish()

# ================== ДОБАВЛЕНИЕ ТОВАРА ==================
@dp.callback_query_handler(lambda c: c.data == 'admin_add_product')
async def admin_add_product_start(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Нет прав.")
        return

    await bot.answer_callback_query(callback_query.id)
    cursor.execute('SELECT id, name FROM categories')
    cats = cursor.fetchall()
    if not cats:
        await bot.send_message(callback_query.from_user.id, "❌ Сначала создайте хотя бы одну категорию.")
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    for cat_id, name in cats:
        keyboard.add(InlineKeyboardButton(name, callback_data=f"admin_add_prod_cat_{cat_id}"))
    keyboard.add(InlineKeyboardButton("⬅️ Отмена", callback_data="admin_panel"))
    await bot.send_message(
        callback_query.from_user.id,
        "Выберите категорию для нового товара:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_add_prod_cat_'))
async def admin_add_product_category(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Нет прав.")
        return

    cat_id = int(callback_query.data.split('_')[-1])
    await state.update_data(category_id=cat_id)
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Введите название товара:")
    await AddProduct.name.set()

@dp.message_handler(state=AddProduct.name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.reply("Введите описание товара:")
    await AddProduct.next()

@dp.message_handler(state=AddProduct.description)
async def add_product_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.reply("Введите цену в TON (или 0, если не доступно):")
    await AddProduct.next()

@dp.message_handler(state=AddProduct.price_ton)
async def add_product_price_ton(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        await state.update_data(price_ton=price)
        await message.reply("Введите цену в BTC (или 0):")
        await AddProduct.next()
    except ValueError:
        await message.reply("Пожалуйста, введите число.")

@dp.message_handler(state=AddProduct.price_btc)
async def add_product_price_btc(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        await state.update_data(price_btc=price)
        await message.reply("Введите цену в ETH (или 0):")
        await AddProduct.next()
    except ValueError:
        await message.reply("Пожалуйста, введите число.")

@dp.message_handler(state=AddProduct.price_eth)
async def add_product_price_eth(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        await state.update_data(price_eth=price)
        await message.reply("Введите цену в USDT (или 0):")
        await AddProduct.next()
    except ValueError:
        await message.reply("Пожалуйста, введите число.")

@dp.message_handler(state=AddProduct.price_usdt)
async def add_product_price_usdt(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        await state.update_data(price_usdt=price)
        await message.reply("Введите цену в BNB (или 0):")
        await AddProduct.next()
    except ValueError:
        await message.reply("Пожалуйста, введите число.")

@dp.message_handler(state=AddProduct.price_bnb)
async def add_product_price_bnb(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        await state.update_data(price_bnb=price)
        await message.reply("Введите цену в LTC (или 0):")
        await AddProduct.next()
    except ValueError:
        await message.reply("Пожалуйста, введите число.")

@dp.message_handler(state=AddProduct.price_ltc)
async def add_product_price_ltc(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        await state.update_data(price_ltc=price)
        await message.reply("Введите цену в DOGE (или 0):")
        await AddProduct.next()
    except ValueError:
        await message.reply("Пожалуйста, введите число.")

@dp.message_handler(state=AddProduct.price_doge)
async def add_product_price_doge(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        await state.update_data(price_doge=price)
        await message.reply("Введите цену в TRX (или 0):")
        await AddProduct.next()
    except ValueError:
        await message.reply("Пожалуйста, введите число.")

@dp.message_handler(state=AddProduct.price_trx)
async def add_product_price_trx(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        await state.update_data(price_trx=price)
        await message.reply("Введите цену в NOT (или 0):")
        await AddProduct.next()
    except ValueError:
        await message.reply("Пожалуйста, введите число.")

@dp.message_handler(state=AddProduct.price_not)
async def add_product_price_not(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        await state.update_data(price_not=price)
        await message.reply("Теперь отправьте файл товара (архив, документ и т.п.):")
        await AddProduct.next()
    except ValueError:
        await message.reply("Пожалуйста, введите число.")

@dp.message_handler(content_types=['document'], state=AddProduct.file)
async def add_product_file(message: types.Message, state: FSMContext):
    document = message.document
    file_id = document.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path
    dest = os.path.join(FILES_DIR, document.file_name)
    await bot.download_file(file_path, dest)
    data = await state.get_data()

    cursor.execute('''
        INSERT INTO products (
            category_id, name, description,
            price_ton, price_btc, price_eth, price_usdt,
            price_bnb, price_ltc, price_doge, price_trx, price_not,
            file_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['category_id'], data['name'], data['description'],
        data['price_ton'], data['price_btc'], data['price_eth'], data['price_usdt'],
        data['price_bnb'], data['price_ltc'], data['price_doge'], data['price_trx'], data['price_not'],
        dest
    ))
    conn.commit()
    await message.reply("✅ Товар успешно добавлен!")
    await state.finish()

# ================== СПИСОК ТОВАРОВ (АДМИНКА) С ТЕСТОВОЙ ВЫДАЧЕЙ ==================
@dp.callback_query_handler(lambda c: c.data.startswith('admin_products_page_'))
async def admin_products_list(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Нет прав.")
        return

    page = int(callback_query.data.split('_')[-1])
    cursor.execute('SELECT id, name, category_id FROM products ORDER BY id')
    products = cursor.fetchall()

    if not products:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="📦 Товаров пока нет.",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
        )
        return

    per_page = 5
    total_pages = (len(products) + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    page_prods = products[start:end]

    text = f"📦 Список товаров (страница {page}/{total_pages}):\n\n"
    keyboard = InlineKeyboardMarkup(row_width=2)
    for pid, pname, cat_id in page_prods:
        cursor.execute('SELECT name FROM categories WHERE id = ?', (cat_id,))
        cat_name = cursor.fetchone()
        cat_name = cat_name[0] if cat_name else "Без категории"
        text += f"ID {pid}: {pname} (категория: {cat_name})\n"
        keyboard.add(
            InlineKeyboardButton(f"❌ Удалить", callback_data=f"admin_del_prod_{pid}"),
            InlineKeyboardButton(f"📤 Тест", callback_data=f"admin_test_prod_{pid}")
        )

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"admin_products_page_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"admin_products_page_{page+1}"))
    if nav_buttons:
        keyboard.row(*nav_buttons)
    keyboard.row(InlineKeyboardButton("⬅️ Назад в админку", callback_data="admin_panel"))

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=keyboard
    )

# ================== ТЕСТОВАЯ ВЫДАЧА ТОВАРА ДЛЯ АДМИНА ==================
@dp.callback_query_handler(lambda c: c.data.startswith('admin_test_prod_'))
async def admin_test_product(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Нет прав.")
        return

    prod_id = int(callback_query.data.split('_')[-1])
    cursor.execute('SELECT file_path, name FROM products WHERE id = ?', (prod_id,))
    res = cursor.fetchone()
    if not res:
        await bot.answer_callback_query(callback_query.id, "❌ Товар не найден.")
        return
    file_path, prod_name = res

    if os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            await bot.send_document(
                user_id,
                f,
                caption=f"🧪 Тестовая выдача товара:\n\n{prod_name}"
            )
        await bot.answer_callback_query(callback_query.id, "✅ Тестовый файл отправлен.")
    else:
        await bot.answer_callback_query(callback_query.id, "❌ Файл товара не найден.")

# ================== УДАЛЕНИЕ ТОВАРА (АДМИНКА) ==================
@dp.callback_query_handler(lambda c: c.data.startswith('admin_del_prod_'))
async def admin_delete_product(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not is_admin(user_id):
        await bot.answer_callback_query(callback_query.id, "⛔ Нет прав.")
        return

    prod_id = int(callback_query.data.split('_')[-1])
    cursor.execute('SELECT file_path FROM products WHERE id = ?', (prod_id,))
    res = cursor.fetchone()
    if res:
        file_path = res[0]
        if os.path.exists(file_path):
            os.remove(file_path)
    cursor.execute('DELETE FROM products WHERE id = ?', (prod_id,))
    conn.commit()
    await bot.answer_callback_query(callback_query.id, "✅ Товар удалён.")
    callback_query.data = "admin_products_page_1"
    await admin_products_list(callback_query)

# ================== ЗАПУСК ==================
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)