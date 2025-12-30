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
ADMIN_ID = 5761885649
CHANNEL_LINK = "https://t.me/interandhelpfull"
CRYPTO_PROVIDER_TOKEN = "401643678:TEST:12345"  # ТЕСТОВЫЙ ТОКЕН TELEGRAM — ОТКРОЕТ ОКНО ОПЛАТЫ

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
                superlikes INTEGER DEFAULT 0
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rebus_used (
                user_id INTEGER PRIMARY KEY,
                used INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def add_user(user_id: int, gender: str, pref_gender: str, age: int, pref_min: int, pref_max: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users
            (user_id, gender, pref_gender, age, pref_age_min, pref_age_max, is_vip, vip_until, boost_until, superlikes)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0)
        """, (user_id, gender, pref_gender, age, pref_min, pref_max))
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
            SELECT u.user_id, u.gender, u.age FROM users u
            LEFT JOIN blocks b1 ON b1.blocker_id = ? AND b1.blocked_id = u.user_id
            LEFT JOIN blocks b2 ON b2.blocker_id = u.user_id AND b2.blocked_id = ?
            WHERE u.user_id != ?
            AND u.age BETWEEN ? AND ?
            AND b1.blocked_id IS NULL
            AND b2.blocked_id IS NULL
            ORDER BY u.boost_until > ? DESC, RANDOM()
        """, (user_id, user_id, user_id, pref_min, pref_max, now))

        candidates = []
        for row in rows:
            cand_id, cand_gender, cand_age = row
            cand_pref = (await get_user(cand_id))[2]
            if (cand_pref == "all" or cand_pref == my_gender) and (pref_gender == "all" or pref_gender == cand_gender):
                candidates.append((cand_id, cand_gender, cand_age))

        if candidates:
            return choice(candidates)
    return None

# === КОМАНДЫ ===
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    
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
        "/premium — премиум-фичи (тест)\n"
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

@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "📖 <b>Руководство</b>\n\n"
        "/search — искать анкеты\n"
        "/stop — завершить чат (потом отзыв)\n"
        "/reset — начать заново\n"
        "/like — взаимные симпатии после чата\n"
        "/premium — купить VIP/буст/суперлайк (тест)\n"
        "/help — это меню\n\n"
        "После взаимного лайка — сразу чат 💕",
        parse_mode="HTML"
    )

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

@dp.message(Command("search"))
async def search(message: types.Message):
    match = await find_match(message.from_user.id)
    if not match:
        await message.answer("Пока никого нет по твоим критериям 😔\nПопробуй позже или измени настройки (/reset)")
        return
    match_id, gender, age = match
    gender_text = "Парень" if gender == "m" else "Девушка"
    await message.answer(
        f"Нашёл анкету!\n{gender_text}, {age} лет\n\n❤️ или 👎?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{match_id}")],
            [InlineKeyboardButton(text="👎 Дислайк", callback_data=f"dislike_{match_id}")]
        ])
    )

@dp.callback_query(F.data.startswith("dislike_"))
async def dislike(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    my_id = callback.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO blocks (blocker_id, blocked_id) VALUES (?, ?)", (my_id, target_id))
        await db.commit()
    await callback.message.edit_text("👎 Дислайк. Ищем следующую анкету...")
    await search(callback.message)

@dp.callback_query(F.data.startswith("like_"))
async def like(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    my_id = callback.from_user.id
    target_match = await find_match(target_id)
    if target_match and target_match[0] == my_id:
        active_chats[my_id] = target_id
        active_chats[target_id] = my_id
        await callback.message.edit_text("💕 Взаимный лайк! Чат открыт — пиши сообщение!")
        await bot.send_message(target_id, "💕 Взаимный лайк! Чат открыт — пиши сообщение!")
    else:
        await callback.message.edit_text("❤️ Лайк отправлен. Ждём ответа...")
        await search(callback.message)

@dp.message(Command("stop"))
async def stop_chat(message: types.Message):
    partner = active_chats.get(message.from_user.id)
    if not partner:
        await message.answer("Ты не в чате.")
        return
    my_id = message.from_user.id
    del active_chats[my_id]
    del active_chats[partner]
    await message.answer("Чат завершён.\n\nКак тебе собеседник?",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="❤️ Понравился", callback_data=f"feedback_like_{partner}")],
                             [InlineKeyboardButton(text="👎 Не очень", callback_data=f"feedback_dislike_{partner}")]
                         ]))
    await bot.send_message(partner, "Собеседник завершил чат.")

@dp.callback_query(F.data.startswith("feedback_like_"))
async def feedback_like(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[2])
    my_id = callback.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO chat_likes (user1_id, user2_id) VALUES (?, ?)", (my_id, target_id))
        await db.commit()
        async with db.execute("SELECT 1 FROM chat_likes WHERE user1_id = ? AND user2_id = ?", (target_id, my_id)) as cursor:
            mutual = await cursor.fetchone()
    if mutual:
        await callback.message.edit_text("❤️ Вы оба понравились друг другу! Найди в /like")
    else:
        await callback.message.edit_text("❤️ Спасибо! Если он тоже лайкнет — появится в /like")

@dp.callback_query(F.data.startswith("feedback_dislike_"))
async def feedback_dislike(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[2])
    my_id = callback.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO blocks (blocker_id, blocked_id) VALUES (?, ?), (?, ?)", (my_id, target_id, target_id, my_id))
        await db.commit()
    await callback.message.edit_text("👎 Этот человек больше не появится в поиске.")

@dp.message(Command("like"))
async def show_matches(message: types.Message):
    my_id = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT u.user_id, u.gender, u.age FROM chat_likes cl
            JOIN users u ON u.user_id = cl.user2_id
            WHERE cl.user1_id = ?
            AND EXISTS (SELECT 1 FROM chat_likes WHERE user1_id = cl.user2_id AND user2_id = cl.user1_id)
        """, (my_id,)) as cursor:
            matches = await cursor.fetchall()
    if not matches:
        await message.answer("Пока нет взаимных симпатий после чата 😔")
        return
    text = "💕 <b>Взаимные симпатии:</b>\n\n"
    keyboard = []
    for m_id, gender, age in matches:
        g_text = "Парень" if gender == "m" else "Девушка"
        text += f"• {g_text}, {age} лет\n"
        keyboard.append([InlineKeyboardButton(text="Написать снова", callback_data=f"rematch_{m_id}")])
    await message.answer(text + "\nНажми кнопку, чтобы возобновить чат!", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@dp.callback_query(F.data.startswith("rematch_"))
async def rematch(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    my_id = callback.from_user.id
    active_chats[my_id] = target_id
    active_chats[target_id] = my_id
    await callback.message.edit_text("💬 Чат возобновлён!")
    await bot.send_message(target_id, "💬 Твой прошлый собеседник хочет продолжить! Чат возобновлён.")

@dp.message(Command("reset"))
async def reset_profile(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (message.from_user.id,))
        await db.execute("DELETE FROM blocks WHERE blocker_id = ? OR blocked_id = ?", (message.from_user.id, message.from_user.id))
        await db.execute("DELETE FROM chat_likes WHERE user1_id = ? OR user2_id = ?", (message.from_user.id, message.from_user.id))
        await db.commit()
    if message.from_user.id in active_chats:
        partner = active_chats.pop(message.from_user.id)
        active_chats.pop(partner, None)
        await bot.send_message(partner, "Собеседник удалил профиль.")
    await message.answer("Профиль удалён. /start — начать заново")

@dp.message(Command("debug"))
async def debug(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Только для админа.")
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total = (await cursor.fetchone())[0]
    await message.answer(f"Анкет в базе: {total}")

@dp.message(Command("premium"))
async def premium_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 VIP навсегда — 149₽ (тест)", callback_data="buy_vip")],
        [InlineKeyboardButton(text="🚀 Буст анкеты 24ч — 49₽ (тест)", callback_data="buy_boost")],
        [InlineKeyboardButton(text="💌 Суперлайк — 29₽ (тест)", callback_data="buy_superlike")],
        [InlineKeyboardButton(text="🆓 Ребус (VIP на 14 дней)", url=CHANNEL_LINK)]
    ])
    await message.answer(
        "💎 <b>Премиум-фичи</b>\n\n"
        "• <b>VIP навсегда</b> — видишь ник + буст + суперлайки\n"
        "• <b>Буст</b> — анкета №1 в поиске 24ч\n"
        "• <b>Суперлайк</b> — уведомление собеседнику\n\n"
        "Тестовый режим — оплата бесплатная!",
        reply_markup=keyboard, parse_mode="HTML"
    )

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@dp.callback_query(F.data.in_({"buy_vip", "buy_boost", "buy_superlike"}))
async def send_test_invoice(callback: types.CallbackQuery):
    data = callback.data
    if data == "buy_vip":
        title = "VIP навсегда (тест)"
        description = "Тестовая покупка — получишь VIP бесплатно"
        payload = "vip_forever"
        price = 1
    elif data == "buy_boost":
        title = "Буст анкеты 24ч (тест)"
        description = "Тестовая покупка"
        payload = "boost_24h"
        price = 1
    else:
        title = "Суперлайк (тест)"
        description = "Тестовая покупка"
        payload = "superlike"
        price = 1

    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=title,
            description=description,
            payload=payload,
            provider_token=CRYPTO_PROVIDER_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label=title, amount=price)],
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
        await callback.answer()
    except Exception as e:
        await callback.message.edit_text(f"Ошибка: {str(e)}\nПопробуй /reset и /start заново.")

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id
    now = int(time.time())

    if payload == "vip_forever":
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET is_vip = 1, vip_until = 0 WHERE user_id = ?", (user_id,))
            await db.commit()
        await message.answer("🎉 Тестовый VIP навсегда активирован! Всё работает ❤️")

    elif payload == "boost_24h":
        boost_until = now + 86400
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET boost_until = ? WHERE user_id = ?", (boost_until, user_id))
            await db.commit()
        await message.answer("🚀 Тестовый буст активирован!")

    elif payload == "superlike":
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET superlikes = superlikes + 1 WHERE user_id = ?", (user_id,))
            await db.commit()
        await message.answer("💌 Тестовый суперлайк куплен!")

@dp.message(Command("9889"))
async def activate_rebus_vip(message: types.Message):
    user_id = message.from_user.id
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT used FROM rebus_used WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] == 1:
                await message.answer("❌ Ты уже активировал VIP по ребусу! Один раз на аккаунт — навсегда.")
                return
        
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cursor:
            if not await cursor.fetchone():
                await message.answer("Сначала зарегистрируйся: /start")
                return
        
        now = int(time.time())
        vip_until = now + 14 * 86400
        
        await db.execute("UPDATE users SET is_vip = 1, vip_until = ? WHERE user_id = ?", (vip_until, user_id))
        await db.execute("INSERT OR REPLACE INTO rebus_used (user_id, used) VALUES (?, 1)", (user_id,))
        await db.commit()
    
    await message.answer("🎉 VIP по ребусу активирован на 14 дней!\nСпасибо, что решил ребус 🧠")

@dp.message()
async def forward_message(message: types.Message):
    partner = active_chats.get(message.from_user.id)
    if not partner:
        return

    receiver_vip = await is_vip_active(partner)

    sender_prefix = ""
    if message.from_user.id == ADMIN_ID:
        sender_prefix = "От: 👑 Создатель\n\n"
    elif receiver_vip:
        username = message.from_user.username or message.from_user.full_name
        sender_prefix = f"От: @{username}\n\n" if message.from_user.username else f"От: {message.from_user.full_name}\n\n"

    try:
        if message.text:
            await bot.send_message(partner, sender_prefix + message.text)
        elif message.photo:
            await bot.send_photo(partner, message.photo[-1].file_id, caption=sender_prefix + (message.caption or ""))
        elif message.video:
            await bot.send_video(partner, message.video.file_id, caption=sender_prefix + (message.caption or ""))
        elif message.voice:
            await bot.send_voice(partner, message.voice.file_id, caption=sender_prefix)
        elif message.sticker:
            await bot.send_sticker(partner, message.sticker.file_id)
        else:
            await bot.copy_message(partner, message.from_user.id, message.message_id)
    except:
        pass

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
