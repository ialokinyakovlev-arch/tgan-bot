import asyncio
import aiosqlite
import os
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from random import choice

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DB_NAME = "dating.db"
active_chats = {}

# === НАСТРОЙКИ ===
ADMIN_ID = 5761885649  # Твой ID — уже правильный
CHANNEL_LINK = "https://t.me/interandhelpfull"  # Твой канал
CRYPTO_PROVIDER_TOKEN = os.getenv("CRYPTO_PROVIDER_TOKEN")  # Токен безопасно через переменную

VIP_PRICE = 14900
BOOST_PRICE = 4900
SUPERLIKE_PRICE = 2900

class Reg(StatesGroup):
    gender = State()
    pref_gender = State()
    age = State()
    pref_age_min = State()
    pref_age_max = State()

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                gender TEXT,
                pref_gender TEXT,
                age INTEGER,
                pref_age_min INTEGER,
                pref_age_max INTEGER,
                is_vip INTEGER DEFAULT 0,
                vip_until INTEGER DEFAULT 0,
                boost_until INTEGER DEFAULT 0,
                superlikes INTEGER DEFAULT 0,
                rebus_vip_used INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                blocker_id INTEGER,
                blocked_id INTEGER,
                PRIMARY KEY (blocker_id, blocked_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_likes (
                user1_id INTEGER,
                user2_id INTEGER,
                PRIMARY KEY (user1_id, user2_id)
            )
        """)
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def add_user(user_id: int, gender: str, pref_gender: str, age: int, pref_min: int, pref_max: int):
    async with aiosqlite.connect(DB_NAME) as db:
        # Сохраняем старое значение rebus_vip_used при перерегистрации
        async with db.execute("SELECT rebus_vip_used FROM users WHERE user_id = ?", (user_id,)) as cursor:
            old = await cursor.fetchone()
            old_rebus = old[0] if old else 0
        
        await db.execute("""
            INSERT OR REPLACE INTO users 
            (user_id, gender, pref_gender, age, pref_age_min, pref_age_max, is_vip, vip_until, boost_until, superlikes, rebus_vip_used)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?)
        """, (user_id, gender, pref_gender, age, pref_min, pref_max, old_rebus))
        await db.commit()

async def is_vip_active(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user:
        return False
    is_vip, vip_until = user[6], user[7]
    return is_vip and (vip_until == 0 or vip_until > int(time.time()))

async def find_match(user_id: int):
    user = await get_user(user_id)
    if not user:
        return None
    _, my_gender, pref_gender, _, pref_min, pref_max, _, _, boost_until, _ = user
    now = int(time.time())

    async with aiosqlite.connect(DB_NAME) as db:
        rows = await db.execute_fetchall("""
            SELECT u.user_id, u.gender, u.pref_gender FROM users u
            LEFT JOIN blocks b1 ON b1.blocker_id = ? AND b1.blocked_id = u.user_id
            LEFT JOIN blocks b2 ON b2.blocker_id = u.user_id AND b2.blocked_id = ?
            WHERE u.user_id != ?
            AND u.age BETWEEN ? AND ?
            AND b1.blocked_id IS NULL
            AND b2.blocked_id IS NULL
            ORDER BY u.boost_until > ? DESC, RANDOM()
            LIMIT 50
        """, (user_id, user_id, user_id, pref_min, pref_max, now))

        candidates = []
        for row in rows:
            cand_id, cand_gender, cand_pref = row
            if (cand_pref == "all" or cand_pref == my_gender) and (pref_gender == "all" or pref_gender == cand_gender):
                candidates.append(cand_id)

        if candidates:
            return choice(candidates)
    return None

# === КОМАНДЫ ===
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    
    # Автоматический VIP навсегда для админа (ты)
    if message.from_user.id == ADMIN_ID:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET is_vip = 1, vip_until = 0 WHERE user_id = ?", (ADMIN_ID,))
            await db.commit()
    
    help_text = (
        "👋 <b>Добро пожаловать в анонимные знакомства!</b>\n\n"
        "<b>Команды:</b>\n"
        "/search — найти анкету\n"
        "/stop — завершить чат\n"
        "/reset — удалить профиль\n"
        "/like — взаимные симпатии\n"
        "/premium — премиум-фичи\n"
        "/help — руководство\n\n"
        "Удачных знакомств ❤️"
    )
    
    if user:
        await message.answer(f"{help_text}\n\nТы зарегистрирован! Жми /search")
    else:
        await message.answer(f"{help_text}\n\nДавай зарегистрируемся! Выбери пол:", 
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="Мужской", callback_data="gender_m")],
                                 [InlineKeyboardButton(text="Женский", callback_data="gender_f")]
                             ]))
        await state.set_state(Reg.gender)

@dp.callback_query(F.data.startswith("gender_"))
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    gender = "m" if callback.data == "gender_m" else "f"
    await state.update_data(gender=gender)
    await callback.message.edit_text("Кого ищешь?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Парней", callback_data="pref_m")],
        [InlineKeyboardButton(text="Девушек", callback_data="pref_f")],
        [InlineKeyboardButton(text="Всех", callback_data="pref_all")]
    ]))
    await state.set_state(Reg.pref_gender)

@dp.callback_query(F.data.startswith("pref_"))
async def process_pref_gender(callback: types.CallbackQuery, state: FSMContext):
    pref = callback.data.split("_")[1]
    await state.update_data(pref_gender=pref)
    await callback.message.edit_text("Сколько тебе лет? (напиши число)")
    await state.set_state(Reg.age)

@dp.message(Reg.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or not 16 <= int(message.text) <= 100:
        await message.answer("Введите реальный возраст (16–100)")
        return
    await state.update_data(age=int(message.text))
    await message.answer("Минимальный возраст собеседника?")
    await state.set_state(Reg.pref_age_min)

@dp.message(Reg.pref_age_min)
async def process_min_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Напиши число!")
        return
    await state.update_data(pref_age_min=int(message.text))
    await message.answer("Максимальный возраст собеседника?")
    await state.set_state(Reg.pref_age_max)

@dp.message(Reg.pref_age_max)
async def process_max_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Напиши число!")
        return
    data = await state.get_data()
    max_age = int(message.text)
    if data["pref_age_min"] > max_age:
        await message.answer("Минимальный возраст не может быть больше максимального!")
        return
    await add_user(message.from_user.id, data["gender"], data["pref_gender"], data["age"], data["pref_age_min"], max_age)
    await message.answer("Регистрация завершена! 🔥\nТеперь используй /search")
    await state.clear()

@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "📖 <b>Руководство</b>\n\n"
        "/search — искать анкеты\n"
        "/stop — завершить чат (потом отзыв)\n"
        "/reset — начать заново\n"
        "/like — взаимные симпатии после чата\n"
        "/premium — премиум-фичи\n"
        "/help — это меню\n\n"
        "После взаимного лайка — сразу чат 💕",
        parse_mode="HTML"
    )

@dp.message(Command("premium"))
async def premium_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 VIP навсегда — 149₽", callback_data="buy_vip")],
        [InlineKeyboardButton(text="🚀 Буст анкеты 24ч — 49₽", callback_data="buy_boost")],
        [InlineKeyboardButton(text="💌 Суперлайк — 29₽", callback_data="buy_superlike")],
        [InlineKeyboardButton(text="🆓 Ребус (VIP на 14 дней)", url=CHANNEL_LINK)]
    ])
    await message.answer(
        "💎 <b>Премиум-фичи</b>\n\n"
        "• <b>VIP навсегда</b> — видишь ник + буст + суперлайки — 149₽\n"
        "• <b>Буст</b> — анкета №1 в поиске 24ч — 49₽\n"
        "• <b>Суперлайк</b> — уведомление собеседнику — 29₽\n\n"
        "Или реши ребус бесплатно — VIP на 14 дней!",
        reply_markup=keyboard, parse_mode="HTML"
    )

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@dp.callback_query(F.data.in_({"buy_vip", "buy_boost", "buy_superlike"}))
async def send_invoice(callback: types.CallbackQuery):
    if not CRYPTO_PROVIDER_TOKEN:
        await callback.message.edit_text("⚠️ Оплата временно недоступна.")
        return

    data = callback.data
    if data == "buy_vip":
        title = "VIP навсегда"
        description = "Видишь ник + буст + суперлайки"
        payload = "vip_forever"
        price = VIP_PRICE
    elif data == "buy_boost":
        title = "Буст анкеты 24ч"
        description = "Твоя анкета №1 в поиске"
        payload = "boost_24h"
        price = BOOST_PRICE
    else:
        title = "Суперлайк"
        description = "Уведомление собеседнику"
        payload = "superlike"
        price = SUPERLIKE_PRICE

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=title,
        description=description,
        payload=payload,
        provider_token=CRYPTO_PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label=title, amount=price)]
    )
    await callback.answer()

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id
    now = int(time.time())

    if payload == "vip_forever":
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET is_vip = 1, vip_until = 0 WHERE user_id = ?", (user_id,))
            await db.commit()
        await message.answer("🎉 VIP навсегда активирован! Спасибо за поддержку ❤️")

    elif payload == "boost_24h":
        boost_until = now + 86400
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET boost_until = ? WHERE user_id = ?", (boost_until, user_id))
            await db.commit()
        await message.answer("🚀 Буст активирован на 24 часа!")

    elif payload == "superlike":
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET superlikes = superlikes + 1 WHERE user_id = ?", (user_id,))
            await db.commit()
        await message.answer("💌 Суперлайк куплен!")

@dp.message(Command("9889"))
async def activate_rebus_vip(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся: /start")
        return
    
    if user[10] == 1:  # rebus_vip_used
        await message.answer("❌ Ты уже активировал VIP по ребусу! Один раз на аккаунт, даже после /reset.")
        return
    
    now = int(time.time())
    vip_until = now + 14 * 86400
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_vip = 1, vip_until = ?, rebus_vip_used = 1 WHERE user_id = ?", (vip_until, message.from_user.id))
        await db.commit()
    
    await message.answer("🎉 VIP по ребусу активирован на 14 дней!\nСпасибо, что решил ребус 🧠")

# Поиск, лайки, чат, /stop, /like, /reset и т.д. — без изменений (оставь как было)

@dp.message(Command("search"))
async def search(message: types.Message):
    match
