import asyncio
import aiosqlite
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from random import choice

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DB_NAME = "dating.db"
active_chats = {}  # {user_id: partner_id}

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
                is_vip INTEGER DEFAULT 0
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
            INSERT OR REPLACE INTO users (user_id, gender, pref_gender, age, pref_age_min, pref_age_max, is_vip)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (user_id, gender, pref_gender, age, pref_min, pref_max))
        await db.commit()

async def find_match(user_id: int):
    user = await get_user(user_id)
    if not user:
        return None
    _, my_gender, pref_gender, my_age, pref_min, pref_max, _ = user
    
    async with aiosqlite.connect(DB_NAME) as db:
        rows = await db.execute_fetchall("""
            SELECT user_id, gender, pref_gender FROM users 
            WHERE user_id != ? AND age BETWEEN ? AND ?
        """, (user_id, pref_min, pref_max))
        
        candidates = []
        for row in rows:
            cand_id, cand_gender, cand_pref = row
            if (cand_pref == "all" or cand_pref == my_gender) and (pref_gender == "all" or pref_gender == cand_gender):
                candidates.append(cand_id)
        
        if candidates:
            return choice(candidates)
    return None

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    help_text = (
        "👋 <b>Добро пожаловать в анонимные знакомства!</b>\n\n"
        "<b>Доступные команды:</b>\n\n"
        "/search — найти новую анкету\n"
        "/stop — завершить текущий чат\n"
        "/reset — удалить свой профиль и начать заново\n"
        "/vip — информация, как получить VIP (видеть, от кого сообщение)\n"
        "/help — показать это руководство снова\n\n"
        "🔥 Анонимность гарантирована: собеседник не видит твой ник и профиль, пока не будет взаимного лайка."
    )
    
    if user:
        await message.answer(f"{help_text}\n\nТы уже зарегистрирован! Используй /search, чтобы найти собеседника ❤️")
    else:
        await message.answer(f"{help_text}\n\nДавай зарегистрируемся! Выбери свой пол:", 
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
        await message.answer("Число!")
        return
    await state.update_data(pref_age_min=int(message.text))
    await message.answer("Максимальный возраст собеседника?")
    await state.set_state(Reg.pref_age_max)

@dp.message(Reg.pref_age_max)
async def process_max_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Число!")
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
    match_id = await find_match(message.from_user.id)
    if not match_id:
        await message.answer("Пока никого нет по твоим критериям 😔 Попробуй позже или измени настройки (/reset)")
        return
    match_user = await get_user(match_id)
    gender_text = "Парень" if match_user[1] == "m" else "Девушка"
    await message.answer(f"Нашёл анкету!\n{gender_text}, {match_user[3]} лет\n\n❤️ или 👎?",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{match_id}")],
                             [InlineKeyboardButton(text="👎 Дислайк", callback_data="dislike")]
                         ]))

@dp.callback_query(F.data == "dislike")
async def dislike(callback: types.CallbackQuery):
    await callback.message.edit_text("Ок, ищем дальше...")
    await search(callback.message)

@dp.callback_query(F.data.startswith("like_"))
async def like(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    if await find_match(target_id) == callback.from_user.id:
        active_chats[callback.from_user.id] = target_id
        active_chats[target_id] = callback.from_user.id
        await callback.message.edit_text("Взаимный лайк! 💕 Теперь вы в анонимном чате.")
        await bot.send_message(target_id, "Взаимный лайк! 💕 Теперь вы в анонимном чате. Пиши сообщение.")
    else:
        await callback.message.edit_text("Лайк отправлен ❤️ Ищем дальше...")
        await search(callback.message)

@dp.message(Command("stop"))
async def stop_chat(message: types.Message):
    partner = active_chats.get(message.from_user.id)
    if partner:
        del active_chats[message.from_user.id]
        del active_chats[partner]
        await message.answer("Чат завершён.")
        await bot.send_message(partner, "Собеседник завершил чат.")
    else:
        await message.answer("Ты не в чате.")

@dp.message(Command("reset"))
async def reset_profile(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (message.from_user.id,))
        await db.commit()
    if message.from_user.id in active_chats:
        partner = active_chats.pop(message.from_user.id)
        active_chats.pop(partner, None)
        await bot.send_message(partner, "Собеседник удалил профиль и вышел.")
    await message.answer("Профиль удалён. Начни заново: /start")

@dp.message(Command("vip"))
async def vip_info(message: types.Message):
    await message.answer(
        "🔥 Хочешь видеть, от кого приходят сообщения в анонимном чате?\n\n"
        "Это доступно только по VIP!\n"
        "Подпишись на мой канал — там опубликован ребус. Реши его и получи секретный код для активации VIP 😉\n\n"
        "👉 <a href='https://t.me/+YXtqxNKDONdkMzU6'>Перейти в канал с ребусом</a>\n\n"
        "Удачи! 🧠",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@dp.message(Command("9889"))
async def activate_vip(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала пройди регистрацию: /start")
        return
    
    # Проверяем, не VIP ли уже
    if user[6] == 1:  # is_vip
        await message.answer("✅ У тебя уже есть VIP!")
        return
    
    # Выдаём VIP
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_vip = 1 WHERE user_id = ?", (message.from_user.id,))
        await db.commit()
    
    await message.answer(
        "🎉 Поздравляю! Ты правильно решил ребус!\n\n"
        "🔥 VIP активирован навсегда!\n"
        "Теперь в анонимном чате ты видишь, от кого приходят сообщения (префикс «От: @ник» или «От: Имя»)."
    )

@dp.message(Command("debug"))
async def debug(message: types.Message):
    # Замени 123456789 на СВОЙ реальный user_id в Telegram
    MY_USER_ID = 5761885649
    
    if message.from_user.id != MY_USER_ID:
        await message.answer("❌ Эта команда доступна только администратору бота.")
        return
    
    user = await get_user(message.from_user.id)
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total = (await cursor.fetchone())[0]
        async with db.execute("SELECT user_id FROM users") as cursor:
            all_ids = [row[0] for row in await cursor.fetchall()]
    
    if user:
        _, g, pg, a, mina, maxa, vip = user
        gender_text = "Парень" if g == "m" else "Девушка"
        pref_text = "парней" if pg == "m" else "девушек" if pg == "f" else "всех"
        vip_text = "VIP" if vip else "обычный"
        text = f"🔧 <b>Debug (админ)</b>\n\nТвой профиль: {gender_text}, {a} лет, ищешь {pref_text} ({mina}–{maxa}), {vip_text}\n\nВсего анкет в базе: {total}\nID пользователей: {all_ids}"
    else:
        text = f"🔧 <b>Debug (админ)</b>\n\nТы не зарегистрирован.\nВсего анкет: {total}"

    @dp.message(Command("help", "menu"))
async def help_command(message: types.Message):
    help_text = (
        "📖 <b>Руководство по боту</b>\n\n"
        "<b>Основные команды:</b>\n\n"
        "/search — искать анкету и лайкать\n"
        "/stop — выйти из текущего чата\n"
        "/reset — полностью удалить профиль и начать сначала\n"
        "/vip — как получить VIP (видеть ник отправителя в чате)\n"
        "/help — показать это меню снова\n\n"
        "После взаимного лайка открывается анонимный чат 💕\n"
        "Пиши сообщения — они пересылаются собеседнику.\n\n"
        "Удачных знакомств! ❤️"
    )
    await message.answer(help_text, parse_mode="HTML")
    
    await message.answer(text, parse_mode="HTML")
@dp.message(Command("help", "menu"))
async def help_command(message: types.Message):
    help_text = (
        "📖 <b>Руководство по боту</b>\n\n"
        "<b>Основные команды:</b>\n\n"
        "/search — искать анкету и лайкать\n"
        "/stop — выйти из текущего чата\n"
        "/reset — полностью удалить профиль и начать сначала\n"
        "/vip — как получить VIP (видеть ник отправителя в чате)\n"
        "/help — показать это меню снова\n\n"
        "После взаимного лайка открывается анонимный чат 💕\n"
        "Пиши сообщения — они пересылаются собеседнику.\n\n"
        "Удачных знакомств! ❤️"
    )
    await message.answer(help_text, parse_mode="HTML")

# АНОНИМНАЯ ПЕРЕСЫЛКА С ПРЕФИКСОМ "Создатель" ДЛЯ АДМИНА
@dp.message()
async def forward_message(message: types.Message):
    partner = active_chats.get(message.from_user.id)
    if not partner:
        return  # Ничего не отвечаем, если не в чате
    
    # === ТВОЙ USER_ID (замени на свой реальный!) ===
    ADMIN_ID = 5761885649  # <-- ВСТАВЬ СВОЙ ID ЗДЕСЬ!
    
    # VIP ли получатель?
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT is_vip FROM users WHERE user_id = ?", (partner,)) as cursor:
            row = await cursor.fetchone()
            receiver_vip = row[0] if row else 0
    
    sender_prefix = ""
    
    # Специальный префикс для создателя (виден ВСЕМ)
    if message.from_user.id == ADMIN_ID:
        sender_prefix = "От: 👑 Создатель\n\n"
    # Обычная логика для остальных
    elif receiver_vip:
        username = message.from_user.username
        full_name = message.from_user.full_name
        sender_name = f"@{username}" if username else full_name
        sender_prefix = f"От: {sender_name}\n\n"
    
    try:
        if message.text:
            await bot.send_message(partner, sender_prefix + message.text)
        elif message.photo:
            await bot.send_photo(partner, message.photo[-1].file_id, caption=sender_prefix + (message.caption or ""))
        elif message.video:
            await bot.send_video(partner, message.video.file_id, caption=sender_prefix + (message.caption or ""))
        elif message.voice:
            await bot.send_voice(partner, message.voice.file_id, caption=sender_prefix)
        elif message.audio:
            await bot.send_audio(partner, message.audio.file_id, caption=sender_prefix + (message.caption or ""))
        elif message.document:
            await bot.send_document(partner, message.document.file_id, caption=sender_prefix + (message.caption or ""))
        elif message.sticker:
            await bot.send_sticker(partner, message.sticker.file_id)
        elif message.animation:
            await bot.send_animation(partner, message.animation.file_id, caption=sender_prefix + (message.caption or ""))
        else:
            await bot.copy_message(partner, message.from_user.id, message.message_id)
    except Exception:
        await bot.send_message(message.from_user.id, "Не удалось отправить сообщение (возможно, файл слишком большой)")
    
    # VIP ли получатель?
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT is_vip FROM users WHERE user_id = ?", (partner,)) as cursor:
            row = await cursor.fetchone()
            receiver_vip = row[0] if row else 0
    
    sender_prefix = ""
    if receiver_vip:
        username = message.from_user.username
        full_name = message.from_user.full_name
        sender_name = f"@{username}" if username else full_name
        sender_prefix = f"От: {sender_name}\n\n"
    
    try:
        if message.text:
            await bot.send_message(partner, sender_prefix + message.text)
        elif message.photo:
            await bot.send_photo(partner, message.photo[-1].file_id, caption=sender_prefix + (message.caption or ""))
        elif message.video:
            await bot.send_video(partner, message.video.file_id, caption=sender_prefix + (message.caption or ""))
        elif message.voice:
            await bot.send_voice(partner, message.voice.file_id, caption=sender_prefix)
        elif message.audio:
            await bot.send_audio(partner, message.audio.file_id, caption=sender_prefix + (message.caption or ""))
        elif message.document:
            await bot.send_document(partner, message.document.file_id, caption=sender_prefix + (message.caption or ""))
        elif message.sticker:
            await bot.send_sticker(partner, message.sticker.file_id)
        elif message.animation:
            await bot.send_animation(partner, message.animation.file_id, caption=sender_prefix + (message.caption or ""))
        else:
            await bot.copy_message(partner, message.from_user.id, message.message_id)
    except Exception:
        await bot.send_message(message.from_user.id, "Не удалось отправить сообщение (возможно, файл слишком большой)")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
