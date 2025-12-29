import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from random import choice

BOT_TOKEN = "7799770441:AAH4NCtFlJOcK4li26kuYReGXVwciuVN3Pg"  # Замени на свой токен

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DB_NAME = "dating.db"

# Состояния для регистрации
class Reg(StatesGroup):
    gender = State()
    pref_gender = State()
    age = State()
    pref_age_min = State()
    pref_age_max = State()

# Состояния для чата
class Chat(StatesGroup):
    chatting = State()

# Пары для анонимного чата (user_id1: user_id2)
active_chats = {}

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                gender TEXT,
                pref_gender TEXT,
                age INTEGER,
                pref_age_min INTEGER,
                pref_age_max INTEGER
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
            INSERT OR REPLACE INTO users (user_id, gender, pref_gender, age, pref_age_min, pref_age_max)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, gender, pref_gender, age, pref_min, pref_max))
        await db.commit()

async def find_match(user_id: int):
    user = await get_user(user_id)
    if not user:
        return None
    _, gender, pref_gender, age, pref_min, pref_max = user
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT user_id FROM users 
            WHERE user_id != ? 
            AND gender = ? 
            AND age BETWEEN ? AND ?
            AND pref_gender = ?
        """, (user_id, pref_gender, pref_min, pref_max, gender)) as cursor:
            rows = await cursor.fetchall()
            if rows:
                return choice(rows)[0]
    return None

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if user:
        await message.answer("Привет! Ты уже зарегистрирован. Используй /search для поиска анкеты или /stop для остановки чата.")
    else:
        await message.answer("Привет! Давай зарегистрируемся для анонимных знакомств.\nВыбери свой пол:", 
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
    if pref == "all": pref = "all"
    await state.update_data(pref_gender=pref)
    await callback.message.edit_text("Сколько тебе лет? (напиши число)")
    await state.set_state(Reg.age)

@dp.message(Reg.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or not 16 <= int(message.text) <= 100:
        await message.answer("Введите реальный возраст (16-100)")
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
    min_age = int(message.text)
    if data["pref_age_min"] > min_age:
        await message.answer("Мин > макс? Исправь.")
        return
    await add_user(message.from_user.id, data["gender"], data["pref_gender"], data["age"], data["pref_age_min"], min_age)
    await message.answer("Регистрация завершена! Используй /search для поиска анкет.")
    await state.clear()

@dp.message(Command("search"))
async def search(message: types.Message):
    match_id = await find_match(message.from_user.id)
    if not match_id:
        await message.answer("Пока никого нет по твоим критериям 😔 Попробуй позже.")
        return
    match_user = await get_user(match_id)
    gender_text = "Парень" if match_user[1] == "m" else "Девушка"
    await message.answer(f"Нашёл анкету!\n{gender_text}, {match_user[3]} лет\n\nЛайк или дислайк?",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{match_id}")],
                             [InlineKeyboardButton(text="👎 Дислайк", callback_data="dislike")]
                         ]))

@dp.callback_query(F.data == "dislike")
async def dislike(callback: types.CallbackQuery):
    await callback.message.edit_text("Ок, ищем дальше...")
    await search(callback.message)  # рекурсия для следующего

@dp.callback_query(F.data.startswith("like_"))
async def like(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    # Проверим, лайкнул ли target нас
    target_match = await find_match(target_id)
    if target_match == callback.from_user.id:
        # Mutual like! Соединяем в чат
        active_chats[callback.from_user.id] = target_id
        active_chats[target_id] = callback.from_user.id
        await callback.message.edit_text("Взаимный лайк! 💕 Теперь можете анонимно чатиться. Пиши сообщение.")
        await bot.send_message(target_id, "Взаимный лайк! 💕 Теперь можете анонимно чатиться. Пиши сообщение.")
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

@dp.message()
async def forward_message(message: types.Message):
    partner = active_chats.get(message.from_user.id)
    if partner:
        await bot.forward_message(partner, message.from_user.id, message.message_id)
    else:
        await message.answer("Используй /search для поиска или /start для регистрации.")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
