import logging
import random
import sqlite3
import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

from config.settings import settings
from database import get_connection, init_db

# ========== НАСТРОЙКА ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
scheduler = AsyncIOScheduler()

# ========== СОСТОЯНИЯ ==========
class CreatureCreation(StatesGroup):
    material = State()
    behavior = State()
    trait = State()

# ========== КОМАНДЫ (оставляем те же) ==========
@dp.message_handler(commands=['start', 'help'])
async def cmd_start(message: types.Message):
    welcome_text = (
        "🐙 *Добро пожаловать в Заповедник Абсурда!*\n\n"
        "Основные команды:\n"
        "`/create` — создать новое существо\n"
        "`/my` — посмотреть своих существ\n"
        "`/events` — последние события\n"
        "`/stats` — статистика\n\n"
        f"📢 Канал событий: {settings.EVENT_CHANNEL}"
    )
    await message.reply(welcome_text, parse_mode='Markdown')

@dp.message_handler(commands=['create'])
async def cmd_create(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for material in settings.MATERIALS[:6]:  # Первые 6 для мобильных
        keyboard.add(material)
    await message.reply("🎲 ШАГ 1/3: Выбери МАТЕРИАЛ:", reply_markup=keyboard)
    await CreatureCreation.material.set()

@dp.message_handler(state=CreatureCreation.material)
async def process_material(message: types.Message, state: FSMContext):
    material = message.text.strip()
    if material not in settings.MATERIALS:
        await message.reply("❌ Выбери из списка!")
        return
    
    async with state.proxy() as data:
        data['material'] = material
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for behavior in settings.BEHAVIORS[:6]:
        keyboard.add(behavior)
    await message.reply("🎲 ШАГ 2/3: Выбери ПОВЕДЕНИЕ:", reply_markup=keyboard)
    await CreatureCreation.behavior.set()

@dp.message_handler(state=CreatureCreation.behavior)
async def process_behavior(message: types.Message, state: FSMContext):
    behavior = message.text.strip()
    if behavior not in settings.BEHAVIORS:
        await message.reply("❌ Выбери из списка!")
        return
    
    async with state.proxy() as data:
        data['behavior'] = behavior
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for trait in settings.TRAITS[:6]:
        keyboard.add(trait)
    await message.reply("🎲 ШАГ 3/3: Выбери ПРИЗНАК:", reply_markup=keyboard)
    await CreatureCreation.trait.set()

@dp.message_handler(state=CreatureCreation.trait)
async def process_trait(message: types.Message, state: FSMContext):
    trait = message.text.strip()
    if trait not in settings.TRAITS:
        await message.reply("❌ Выбери из списка!")
        return
    
    async with state.proxy() as data:
        user_id = message.from_user.id
        username = message.from_user.username or f"user_{user_id}"
        
        # Сохраняем в базу
        conn = get_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO creatures 
                    (user_id, username, material, behavior, trait) 
                    VALUES (?, ?, ?, ?, ?)''',
                 (user_id, username, data['material'], data['behavior'], trait))
        creature_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Ответ
        response = (
            f"✅ *Существо #{creature_id} создано!*\n\n"
            f"🔮 {data['material']} {data['behavior'].lower()}\n"
            f"⚡ Признак: {trait}\n"
            f"👤 Автор: @{username}\n\n"
            f"Скоро появится в событиях!"
        )
        await message.reply(response, parse_mode='Markdown', reply_markup=types.ReplyKeyboardRemove())
    
    await state.finish()

@dp.message_handler(commands=['my'])
async def cmd_my(message: types.Message):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT id, material, behavior, trait FROM creatures 
                 WHERE user_id = ? ORDER BY id DESC LIMIT 5''',
              (message.from_user.id,))
    creatures = c.fetchall()
    conn.close()
    
    if not creatures:
        await message.reply("У тебя пока нет существ. `/create`", parse_mode='Markdown')
        return
    
    response = "🦠 Твои существа:\n\n"
    for c in creatures:
        response += f"*#{c[0]}*: {c[1]} {c[2]}\n   ({c[3]})\n\n"
    await message.reply(response, parse_mode='Markdown')

@dp.message_handler(commands=['events'])
async def cmd_events(message: types.Message):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT event_text, created_at FROM events 
                 ORDER BY id DESC LIMIT 3''')
    events = c.fetchall()
    conn.close()
    
    if not events:
        await message.reply("Событий пока нет")
        return
    
    response = "📜 Последние события:\n\n"
    for e in events:
        time = e[1].split()[1][:5] if ' ' in str(e[1]) else '??:??'
        response += f"• {e[0]} ({time})\n\n"
    await message.reply(response)

@dp.message_handler(commands=['stats'])
async def cmd_stats(message: types.Message):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM creatures")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT user_id) FROM creatures")
    users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM events")
    events = c.fetchone()[0]
    conn.close()
    
    stats = (
        f"📊 Статистика:\n\n"
        f"👥 Пользователи: {users}\n"
        f"🦠 Существ: {total}\n"
        f"📜 Событий: {events}\n"
        f"📢 Канал: {settings.EVENT_CHANNEL}"
    )
    await message.reply(stats)

# ========== АВТО-СОБЫТИЯ ==========
async def generate_event():
    """Создать случайное событие"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''SELECT id, material, behavior, trait, username 
                     FROM creatures ORDER BY RANDOM() LIMIT 2''')
        creatures = c.fetchall()
        
        if len(creatures) < 2:
            return None
        
        c1, c2 = creatures
        templates = [
            f"🔄 {c1[1]} {c1[2]} встретил {c2[1]} {c2[2]}...",
            f"💥 '{c1[3]}' vs '{c2[3]}' — конфликт!",
            f"🌀 Под влиянием {c2[2]} у {c1[1]} новый признак",
            f"📈 {c1[4]} и {c2[4]} создали гибрид абсурда",
        ]
        
        event = random.choice(templates)
        c.execute('''INSERT INTO events (creature1_id, creature2_id, event_text)
                     VALUES (?, ?, ?)''', (c1[0], c2[0], event))
        conn.commit()
        conn.close()
        
        # Отправляем в канал
        await bot.send_message(settings.EVENT_CHANNEL, event)
        logger.info(f"Событие создано: {event[:50]}...")
        return event
        
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        return None

# ========== ЗАПУСК НА РЕНДЕРЕ ==========
def start_scheduler():
    """Запуск планировщика событий"""
    scheduler.add_job(
        generate_event,
        trigger=IntervalTrigger(seconds=settings.EVENT_INTERVAL),
        id='event_generator',
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Планировщик запущен (интервал: {settings.EVENT_INTERVAL}с)")

async def on_startup(dp):
    """Действия при старте"""
    logger.info("=== Заповедник Абсурда запускается ===")
    
    # Инициализация БД
    init_db()
    
    # Запуск планировщика
    start_scheduler()
    
    logger.info("✅ Бот готов к работе")
    logger.info(f"🤖 Бот: @{(await bot.get_me()).username}")
    logger.info(f"📢 Канал: {settings.EVENT_CHANNEL}")

if __name__ == '__main__':
    # Запуск
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup
    )
