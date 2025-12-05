import logging
import random
import sqlite3
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

from config.settings import settings
from database import get_connection

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=settings.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Состояния для создания существа
class CreatureCreation(StatesGroup):
    material = State()
    behavior = State()
    trait = State()

# ========== КОМАНДЫ БОТА ==========

@dp.message_handler(commands=['start', 'help'])
async def cmd_start(message: types.Message):
    """Приветственное сообщение"""
    welcome_text = (
        "🐙 *Добро пожаловать в Заповедник Абсурда!*\n\n"
        "Здесь ты создаёшь существ из ничего и наблюдаешь, "
        "как они порождают хаос.\n\n"
        "*Основные команды:*\n"
        "`/create` — создать новое существо\n"
        "`/my` — посмотреть своих существ\n"
        "`/events` — последние события в заповеднике\n"
        "`/stats` — статистика заповедника\n\n"
        "*Как это работает:*\n"
        "1. Создаёшь существо из Материала, Поведения и Признака\n"
        "2. Бот автоматически генерирует события с твоими существами\n"
        "3. Следи за каналом: " + settings.EVENT_CHANNEL
    )
    await message.reply(welcome_text, parse_mode='Markdown')

@dp.message_handler(commands=['create'])
async def cmd_create(message: types.Message):
    """Начать создание существа"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for material in settings.MATERIALS:
        keyboard.add(material)
    
    await message.reply(
        "🎲 *ШАГ 1/3*: Выбери *МАТЕРИАЛ* существа:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await CreatureCreation.material.set()

@dp.message_handler(state=CreatureCreation.material)
async def process_material(message: types.Message, state: FSMContext):
    """Обработка выбора материала"""
    material = message.text.strip()
    
    if material not in settings.MATERIALS:
        await message.reply("❌ Выбери материал из списка!")
        return
    
    async with state.proxy() as data:
        data['material'] = material
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for behavior in settings.BEHAVIORS:
        keyboard.add(behavior)
    
    await message.reply(
        "🎲 *ШАГ 2/3*: Выбери *ПОВЕДЕНИЕ* существа:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await CreatureCreation.behavior.set()

@dp.message_handler(state=CreatureCreation.behavior)
async def process_behavior(message: types.Message, state: FSMContext):
    """Обработка выбора поведения"""
    behavior = message.text.strip()
    
    if behavior not in settings.BEHAVIORS:
        await message.reply("❌ Выбери поведение из списка!")
        return
    
    async with state.proxy() as data:
        data['behavior'] = behavior
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for trait in settings.TRAITS:
        keyboard.add(trait)
    
    await message.reply(
        "🎲 *ШАГ 3/3*: Выбери *ОСОБЫЙ ПРИЗНАК*:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await CreatureCreation.trait.set()

@dp.message_handler(state=CreatureCreation.trait)
async def process_trait(message: types.Message, state: FSMContext):
    """Финальный шаг создания существа"""
    trait = message.text.strip()
    
    if trait not in settings.TRAITS:
        await message.reply("❌ Выбери признак из списка!")
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
        
        # Формируем ответ
        creature_name = f"{data['material']} {data['behavior'].lower()}"
        response = (
            f"✅ *Существо #{creature_id} создано!*\n\n"
            f"🔮 *{creature_name}*\n"
            f"⚡ *Признак:* {trait}\n"
            f"👤 *Автор:* @{username}\n"
            f"🕐 *Создано:* {datetime.now().strftime('%H:%M')}\n\n"
            f"Оно уже заселено в заповедник и скоро появится в событиях!"
        )
        
        await message.reply(
            response, 
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        logger.info(f"Создано существо #{creature_id} пользователем {username}")
    
    await state.finish()

@dp.message_handler(commands=['my'])
async def cmd_my(message: types.Message):
    """Показать существ пользователя"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT id, material, behavior, trait, created_at 
                 FROM creatures 
                 WHERE user_id = ? 
                 ORDER BY id DESC LIMIT 10''',
              (message.from_user.id,))
    creatures = c.fetchall()
    conn.close()
    
    if not creatures:
        await message.reply("У тебя пока нет существ. Создай первое командой `/create`", parse_mode='Markdown')
        return
    
    response = "🦠 *Твои существа:*\n\n"
    for creature in creatures:
        created_time = creature[4].split()[1][:5] if ' ' in str(creature[4]) else '??:??'
        response += f"*#{creature[0]}*: {creature[1]} {creature[2]}\n"
        response += f"   Признак: {creature[3]}\n"
        response += f"   Создано: {created_time}\n\n"
    
    await message.reply(response, parse_mode='Markdown')

@dp.message_handler(commands=['events'])
async def cmd_events(message: types.Message):
    """Показать последние события"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT event_text, created_at 
                 FROM events 
                 ORDER BY id DESC LIMIT 5''')
    events = c.fetchall()
    conn.close()
    
    if not events:
        await message.reply("📭 В заповеднике пока тихо... Слишком тихо.")
        return
    
    response = "📜 *Последние события в Заповеднике:*\n\n"
    for event in events:
        time = event[1].split()[1][:5] if ' ' in str(event[1]) else '??:??'
        response += f"• {event[0]} *({time})*\n\n"
    
    await message.reply(response, parse_mode='Markdown')

@dp.message_handler(commands=['stats'])
async def cmd_stats(message: types.Message):
    """Статистика заповедника"""
    conn = get_connection()
    c = conn.cursor()
    
    # Общая статистика
    c.execute("SELECT COUNT(*) FROM creatures")
    total_creatures = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT user_id) FROM creatures")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM events")
    total_events = c.fetchone()[0]
    
    # Самый популярный материал
    c.execute("SELECT material, COUNT(*) as cnt FROM creatures GROUP BY material ORDER BY cnt DESC LIMIT 1")
    popular_material = c.fetchone() or ("Нет данных", 0)
    
    conn.close()
    
    stats_text = (
        "📊 *Статистика Заповедника Абсурда*\n\n"
        f"👥 *Пользователи:* {total_users}\n"
        f"🦠 *Существ:* {total_creatures}\n"
        f"📜 *Событий:* {total_events}\n"
        f"🏆 *Популярный материал:* {popular_material[0]} ({popular_material[1]})\n\n"
        f"📢 *Канал событий:* {settings.EVENT_CHANNEL}"
    )
    
    await message.reply(stats_text, parse_mode='Markdown')

# ========== АВТОМАТИЧЕСКАЯ ГЕНЕРАЦИЯ СОБЫТИЙ ==========

async def generate_event():
    """Сгенерировать случайное событие"""
    conn = get_connection()
    c = conn.cursor()
    
    # Получаем два случайных существа
    c.execute('''SELECT id, material, behavior, trait, username 
                 FROM creatures 
                 ORDER BY RANDOM() LIMIT 2''')
    creatures = c.fetchall()
    
    if len(creatures) < 2:
        conn.close()
        return None
    
    creature1, creature2 = creatures
    
    # Шаблоны событий
    event_templates = [
        "🔄 *Встреча*: {material1} {behavior1} встретил {material2} {behavior2}...",
        "💥 *Конфликт*: '{trait1}' вступил в противоречие с '{trait2}'!",
        "🤝 *Симбиоз*: {material1} и {material2} образовали нестабильный альянс.",
        "🌀 *Мутация*: Под влиянием {behavior2} у {material1} проявился новый признак.",
        "📈 *Эволюция*: {username1} и {username2} создали гибрид абсурда.",
        "⚠️ *Нарушение*: {material1} {behavior1} нарушил правила заповедника.",
    ]
    
    # Заполняем шаблон
    template = random.choice(event_templates)
    event_text = template.format(
        material1=creature1[1], behavior1=creature1[2], trait1=creature1[3], username1=creature1[4],
        material2=creature2[1], behavior2=creature2[2], trait2=creature2[3], username2=creature2[4]
    )
    
    # Сохраняем в базу
    c.execute('''INSERT INTO events (creature1_id, creature2_id, event_text)
                 VALUES (?, ?, ?)''', (creature1[0], creature2[0], event_text))
    conn.commit()
    conn.close()
    
    return event_text

async def event_scheduler():
    """Планировщик автоматических событий"""
    logger.info(f"Планировщик событий запущен (интервал: {settings.EVENT_INTERVAL}с)")
    
    while True:
        try:
            await asyncio.sleep(settings.EVENT_INTERVAL)
            
            event = await generate_event()
            if event:
                await bot.send_message(settings.EVENT_CHANNEL, event, parse_mode='Markdown')
                logger.info(f"Сгенерировано событие: {event[:50]}...")
            else:
                logger.info("Недостаточно существ для генерации события")
                
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")

# ========== ЗАПУСК БОТА ==========

async def on_startup(dp):
    """Действия при запуске бота"""
    logger.info("Заповедник Абсурда запускается...")
    
    # Проверяем базу данных
    from database import init_db
    init_db()
    
    # Запускаем планировщик событий
    asyncio.create_task(event_scheduler())
    
    logger.info("✅ Бот успешно запущен")

if __name__ == '__main__':
    # Запуск бота
    executor.start_polling(
        dp, 
        skip_updates=True,
        on_startup=on_startup
    )
