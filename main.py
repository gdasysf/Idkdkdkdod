# оставлю немного обозначений чтобы новички могли понять 
import logging
import os
import requests
import time
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

TELEGRAM_BOT_TOKEN = '8107230002:AAEWIQiPbgL4lXJ6eeYwrOA3-jFYDQeuV04'  # токен бота 
CRYPTO_BOT_TOKEN = '509179:AAHycIbTUPLk87WcaOiTFob9mvNQ3FmEZT6'  # api от крипто бота 
ADMIN_ID = '5459547413' # id администратора 

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(level=logging.INFO)

CRYPTO_API_URL = 'https://pay.crypt.bot/api'
# вот цены меняйте сами 
CURRENCY_PRICES = {
    "TON": 1.5,
    "BTC": 0.0001,
    "ETH": 0.001,
    "USDT": 2.0,
    "BNB": 0.01,
    "LTC": 0.02,
    "DOGE": 50,
    "TRX": 10,
    "NOT": 2,
}

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
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Ошибка при создании счета: {response.status_code} - {response.text}")
        return None

def check_invoice_status(invoice_id):
    url = f"{CRYPTO_API_URL}/getInvoices"
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
        "Content-Type": "application/json"
    }
    params = {
        "invoice_ids": invoice_id
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Ошибка при проверке статуса счета: {response.status_code} - {response.text}")
        return None

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    welcome_photo_path = "welcome.jpg"
    if not os.path.exists(welcome_photo_path):
        await message.reply("❌ Фото для приветствия не найдено.")
        return

    with open(welcome_photo_path, 'rb') as photo:
        await bot.send_photo(message.chat.id, photo, caption=f"👋 Привет! Добро пожаловать в наш магазин софтов!\n\n"
                                                            f"📦 Здесь вы можете приобрести нужный софт.\n"
                                                            f"💬 Если у вас есть вопросы, пишите в поддержку.\n"
                                                            f"👇 Выберите действие:"
                                                            
                             ,reply_markup=get_main_menu_keyboard())

def get_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.row(
        InlineKeyboardButton("📁 Софты", callback_data="soft_list_page_1"),
        InlineKeyboardButton("📢 Канал", url="https://t.me/+UbVydJzc_7dhZGUy") # тут ссылка на канал
    )
    keyboard.row(
        InlineKeyboardButton("💬 Поддержка", callback_data="support")
    )
    return keyboard

@dp.callback_query_handler(lambda c: c.data.startswith('soft_list_page_'))
async def process_callback_soft_list(callback_query: types.CallbackQuery):
    page = int(callback_query.data.split('_')[-1])
    await bot.answer_callback_query(callback_query.id)
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"📂 Выберите софт (Страница {page}):",
            reply_markup=get_soft_list_keyboard(page)
        )
    except Exception as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")
        await bot.send_message(callback_query.from_user.id, f"📂 Выберите софт (Страница {page}):",
                               reply_markup=get_soft_list_keyboard(page))

def get_soft_list_keyboard(page):
    soft_folders = [f for f in os.listdir() if os.path.isdir(f)]
    total_pages = (len(soft_folders) + 4) // 5 
    start_index = (page - 1) * 5
    end_index = start_index + 5
    current_folders = soft_folders[start_index:end_index]

    keyboard = InlineKeyboardMarkup(row_width=2)
    for folder in current_folders:
        keyboard.add(InlineKeyboardButton(f"📦 {folder}", callback_data=f"soft_{folder}"))
    if page > 1:
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"soft_list_page_{page - 1}"))
    if page < total_pages:
        keyboard.add(InlineKeyboardButton("Вперёд ➡️", callback_data=f"soft_list_page_{page + 1}"))
    if page == total_pages and total_pages > 1:
        keyboard.add(InlineKeyboardButton("Вернуться на первую страницу 🔄", callback_data="soft_list_page_1"))
    
    return keyboard

@dp.callback_query_handler(lambda c: c.data.startswith('soft_'))
async def process_callback_soft(callback_query: types.CallbackQuery):
    soft_name = callback_query.data.split('_')[1]
    soft_path = soft_name
    
    photo_path = None
    for ext in ('jpg', 'jpeg', 'png'):
        photo_path = next((os.path.join(soft_path, f) for f in os.listdir(soft_path) if f.lower().endswith(ext)), None)
        if photo_path:
            break
    
    description_path = next((os.path.join(soft_path, f) for f in os.listdir(soft_path) if f.lower().endswith('.txt')), None)
    soft_file_path = next((os.path.join(soft_path, f) for f in os.listdir(soft_path) if f.lower().endswith(('.zip', '.rar'))), None)
    
    if not photo_path or not description_path or not soft_file_path:
        await bot.answer_callback_query(callback_query.id, "❌ Файлы не найдены в папке.")
        return
    
    with open(description_path, 'r', encoding='utf-8') as f:
        description = f.read()
    
    with open(photo_path, 'rb') as photo:
        await bot.send_photo(callback_query.from_user.id, photo, caption=description,
                             reply_markup=get_soft_details_keyboard(soft_name))

def get_soft_details_keyboard(soft_name):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("💳 Купить", callback_data=f"buy_{soft_name}"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="soft_list_page_1"))
    return keyboard

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def process_callback_buy(callback_query: types.CallbackQuery):
    soft_name = callback_query.data.split('_')[1]
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, f"💰 Выберите способ оплаты для софта {soft_name}:",
                           reply_markup=get_payment_keyboard(soft_name))

def get_payment_keyboard(soft_name):
    keyboard = InlineKeyboardMarkup(row_width=2)
    for currency, price in CURRENCY_PRICES.items():
        keyboard.add(InlineKeyboardButton(f"💸 {currency} - {price}", callback_data=f"pay_{soft_name}_{currency}"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"soft_{soft_name}"))
    return keyboard

@dp.callback_query_handler(lambda c: c.data.startswith('pay_'))
async def process_callback_pay(callback_query: types.CallbackQuery):
    data = callback_query.data.split('_')
    soft_name = data[1]
    currency = data[2]
    amount = CURRENCY_PRICES[currency]
    
    invoice = create_invoice(asset=currency, amount=amount, description=f"Оплата за {soft_name}")
    if invoice and 'result' in invoice:
        pay_url = invoice['result']['pay_url']
        invoice_id = invoice['result']['invoice_id']
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(callback_query.from_user.id,
                               f"💳 Ссылка для оплаты: {pay_url}")        
        await check_payment_status(callback_query.from_user.id, invoice_id, soft_name)
    else:
        await bot.answer_callback_query(callback_query.id, "❌ Ошибка при создании счета")

async def check_payment_status(user_id, invoice_id, soft_name):
    while True:
        time.sleep(5)  
        invoice_status = check_invoice_status(invoice_id)
        if invoice_status and 'result' in invoice_status:
            status = invoice_status['result']['items'][0]['status']
            if status == 'paid':
                soft_path = soft_name
                description_path = os.path.join(soft_path, 'description.txt')
                soft_file_path = os.path.join(soft_path, 'soft.zip')
                
                with open(description_path, 'r', encoding='utf-8') as f:
                    description = f.read()
                
                with open(soft_file_path, 'rb') as soft_file:
                    await bot.send_document(user_id, soft_file, caption=f"✅ Спасибо за покупку!\n\n{description}")
                break

@dp.callback_query_handler(lambda c: c.data == 'support')
async def process_callback_support(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "📩 Напишите ваше сообщение для поддержки. Можно отправить текст, фото, видео или другой файл.")

@dp.message_handler(content_types=['text', 'photo', 'video', 'document'])
async def handle_support_message(message: types.Message):
    user_id = message.from_user.id
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
    
    await bot.send_message(ADMIN_ID, admin_message)
    if message.photo or message.video or message.document:
        await message.copy_to(ADMIN_ID)
    
    await message.reply("✅ Ваше сообщение отправлено администратору на рассмотрение. Ожидайте ответа.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)