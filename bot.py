import logging
import random
import sqlite3
import asyncio
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
EVENT_CHANNEL = os.getenv("EVENT_CHANNEL", "@absurd_zoo_log")
EVENT_INTERVAL = int(os.getenv("EVENT_INTERVAL", "1800"))  # 30 минут
DATABASE_PATH = os.getenv("DATABASE_PATH", "/tmp/absurd.db")

# Проверка токена
if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не установлен!")
    print("ℹ️ Добавь BOT_TOKEN в Environment Variables на Render")
    exit(1)

# Списки для существ
MATERIALS = ["Стекло", "Бюрократия", "Пыль", "Ностальгия", "Незаконченный код"]
BEHAVIORS = ["Питается делами", "Размножается отчётами", "Мигрирует за опечатками"]
TRAITS = ["Гипнотизирующий узор", "Теряет доверенность", "Пахнет тоской"]

# ========== БАЗА ДАННЫХ ==========
def init_db():
    """Создаем базу данных"""
    print(f"📦 Создаем БД: {DATABASE_PATH}")
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS creatures
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  material TEXT,
                  behavior TEXT,
                  trait TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  event_text TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()
    print("✅ База данных готова")

def get_connection():
    """Подключение к БД"""
    return sqlite3.connect(DATABASE_PATH)

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class CreatureCreation(StatesGroup):
    material = State()
    behavior = State()
    trait = State()

# ========== КОМАНДЫ ==========
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """Начало работы"""
    await message.reply(
        "🐙 Привет! Я бот Заповедника Абсурда.\n"
        "Создавай существ и смотри как они взаимодействуют!\n\n"
        "Команды:\n"
        "/create - создать существо\n"
        "/my - мои существа\n"
        "/events - последние события\n"
        "/stats - статистика\n\n"
        f"📢 Канал событий: {EVENT_CHANNEL}"
    )

@dp.message_handler(commands=['create'])
async def cmd_create(message: types.Message):
    """Создать существо"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for m in MATERIALS:
        keyboard.add(m)
    await message.reply("Выбери материал:", reply_markup=keyboard)
    await CreatureCreation.material.set()

@dp.message_handler(state=CreatureCreation.material)
async def step_material(message: types.Message, state: FSMContext):
    """Шаг 1: материал"""
    if message.text not in MATERIALS:
        await message.reply("Выбери из списка!")
        return
    
    async with state.proxy() as data:
        data['material'] = message.text
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for b in BEHAVIORS:
        keyboard.add(b)
    await message.reply("Выбери поведение:", reply_markup=keyboard)
    await CreatureCreation.behavior.set()

@dp.message_handler(state=CreatureCreation.behavior)
async def step_behavior(message: types.Message, state: FSMContext):
    """Шаг 2: поведение"""
    if message.text not in BEHAVIORS:
        await message.reply("Выбери из списка!")
        return
    
    async with state.proxy() as data:
        data['behavior'] = message.text
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for t in TRAITS:
        keyboard.add(t)
    await message.reply("Выбери признак:", reply_markup=keyboard)
    await CreatureCreation.trait.set()

@dp.message_handler(state=CreatureCreation.trait)
async def step_trait(message: types.Message, state: FSMContext):
    """Шаг 3: признак"""
    if message.text not in TRAITS:
        await message.reply("Выбери из списка!")
        return
    
    async with state.proxy() as data:
        # Сохраняем в БД
        conn = get_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO creatures (user_id, username, material, behavior, trait)
                     VALUES (?, ?, ?, ?, ?)''',
                 (message.from_user.id, message.from_user.username,
                  data['material'], data['behavior'], message.text))
        creature_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Отвечаем
        response = (
            f"✅ Существо #{creature_id} создано!\n"
            f"🔮 {data['material']} {data['behavior']}\n"
            f"⚡ Признак: {message.text}\n"
            f"👤 Создатель: @{message.from_user.username}"
        )
        await message.reply(response, reply_markup=types.ReplyKeyboardRemove())
    
    await state.finish()

@dp.message_handler(commands=['my'])
async def cmd_my(message: types.Message):
    """Мои существа"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT id, material, behavior, trait FROM creatures 
                 WHERE user_id = ? ORDER BY id DESC LIMIT 5''',
              (message.from_user.id,))
    creatures = c.fetchall()
    conn.close()
    
    if not creatures:
        await message.reply("У тебя пока нет существ. /create")
        return
    
    text = "🦠 Твои существа:\n"
    for c in creatures:
        text += f"#{c[0]}: {c[1]} {c[2]} ({c[3]})\n"
    
    await message.reply(text)

@dp.message_handler(commands=['events'])
async def cmd_events(message: types.Message):
    """Последние события"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT event_text FROM events ORDER BY id DESC LIMIT 3''')
    events = c.fetchall()
    conn.close()
    
    if not events:
        await message.reply("Событий пока нет")
        return
    
    text = "📜 Последние события:\n"
    for e in events:
        text += f"• {e[0]}\n"
    
    await message.reply(text)

@dp.message_handler(commands=['stats'])
async def cmd_stats(message: types.Message):
    """Статистика"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM creatures")
    creatures = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(DISTINCT user_id) FROM creatures")
    users = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM events")
    events = c.fetchone()[0] or 0
    conn.close()
    
    text = (
        f"📊 Статистика:\n"
        f"👥 Пользователей: {users}\n"
        f"🦠 Существ: {creatures}\n"
        f"📜 Событий: {events}\n"
        f"📢 Канал: {EVENT_CHANNEL}"
    )
    
    await message.reply(text)

# ========== АВТО-СОБЫТИЯ ==========
async def generate_event():
    """Создать событие"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''SELECT material, behavior, trait, username 
                     FROM creatures ORDER BY RANDOM() LIMIT 2''')
        creatures = c.fetchall()
        
        if len(creatures) < 2:
            return None
        
        c1, c2 = creatures
        templates = [
            f"🔄 {c1[0]} {c1[1]} встретил {c2[0]} {c2[1]}",
            f"💥 {c1[2]} vs {c2[2]} — конфликт!",
            f"🌀 {c1[3]} и {c2[3]} создали хаос",
        ]
        
        event = random.choice(templates)
        c.execute('''INSERT INTO events (event_text) VALUES (?)''', (event,))
        conn.commit()
        conn.close()
        
        return event
    except:
        return None

async def event_scheduler():
    """Планировщик событий"""
    print(f"⏰ Планировщик запущен (каждые {EVENT_INTERVAL//60} минут)")
    
    while True:
        await asyncio.sleep(EVENT_INTERVAL)
        
        event = await generate_event()
        if event:
            try:
                await bot.send_message(EVENT_CHANNEL, event)
                print(f"📨 Отправлено событие: {event[:30]}...")
            except Exception as e:
                print(f"❌ Ошибка отправки: {e}")

# ========== ЗАПУСК ==========
async def on_startup(dp):
    """Запуск бота"""
    print("=" * 50)
    print("🐙 ЗАПУСК ЗАПОВЕДНИКА АБСУРДА")
    print("=" * 50)
    
    # База данных
    init_db()
    
    # Инфо о боте
    bot_info = await bot.get_me()
    print(f"🤖 Бот: @{bot_info.username}")
    print(f"📢 Канал: {EVENT_CHANNEL}")
    
    # Запуск планировщика
    asyncio.create_task(event_scheduler())
    
    print("✅ Бот готов к работе!")

if __name__ == '__main__':
    # Проверка Python версии
    import sys
    if sys.version_info >= (3, 12):
        print("⚠️ Внимание: Python 3.12+ может вызывать проблемы")
        print("💡 На Render выбери Python 3.11 в настройках")
    
    # Запуск
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)