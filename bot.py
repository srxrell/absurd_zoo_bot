import logging
import random
import sqlite3
import os
import asyncio
from datetime import datetime
from threading import Thread
from flask import Flask

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

from config.settings import settings
from database import get_connection, init_db

# ========== FLASK СЕРВЕР ДЛЯ RENDER ==========
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🐙 Заповедник Абсурда</title>
        <style>
            body {
                font-family: 'Courier New', monospace;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: #0f0f23;
                color: #00ff00;
            }
            .container {
                border: 2px dashed #00ff00;
                padding: 30px;
                border-radius: 10px;
                background: rgba(0, 255, 0, 0.05);
            }
            h1 {
                color: #00ff00;
                text-shadow: 0 0 10px #00ff00;
            }
            .status {
                color: #00ff00;
                font-weight: bold;
                animation: blink 1s infinite;
            }
            @keyframes blink {
                50% { opacity: 0.5; }
            }
            .telegram-link {
                display: inline-block;
                background: #0088cc;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                text-decoration: none;
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🐙 Заповедник Абсурда</h1>
            <p><span class="status">●</span> Бот работает</p>
            <p>Telegram бот для коллективной симуляции абсурдной экосистемы.</p>
            <p>Пользователи создают виртуальных существ, которые взаимодействуют в реальном времени.</p>
            
            <h3>📊 Статистика:</h3>
            <p>• Пользователей: {{ users }}</p>
            <p>• Существ: {{ creatures }}</p>
            <p>• Событий: {{ events }}</p>
            
            <h3>🔗 Ссылки:</h3>
            <a href="https://t.me/{{ bot_username }}" class="telegram-link" target="_blank">
                📱 Открыть в Telegram
            </a>
            <br>
            <a href="{{ event_channel }}" class="telegram-link" style="background: #ff6b6b; margin-top: 10px;" target="_blank">
                📢 Канал событий
            </a>
            
            <p style="margin-top: 30px; font-size: 12px; color: #666;">
                Заповедник работает на Render • Обновляется каждые {{ interval//60 }} минут
            </p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return "OK", 200

@app.route('/stats')
def stats_api():
    """JSON API для статистики"""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM creatures")
    total_creatures = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT user_id) FROM creatures")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM events")
    total_events = c.fetchone()[0]
    
    # Последние события
    c.execute("SELECT event_text, created_at FROM events ORDER BY id DESC LIMIT 5")
    recent_events = c.fetchall()
    
    conn.close()
    
    return {
        "status": "operational",
        "data": {
            "users": total_users,
            "creatures": total_creatures,
            "events": total_events,
            "recent_events": [
                {"text": e[0], "time": e[1]} for e in recent_events
            ],
            "bot_username": bot_username if 'bot_username' in globals() else "Unknown",
            "event_channel": settings.EVENT_CHANNEL,
            "event_interval": settings.EVENT_INTERVAL
        }
    }

def run_flask():
    """Запускаем Flask сервер"""
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# ========== НАСТРОЙКА ЛОГГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
bot = Bot(token=settings.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Глобальная переменная для имени бота
bot_username = None

# ========== СОСТОЯНИЯ ДЛЯ СОЗДАНИЯ СУЩЕСТВА ==========
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
        "*Как это работает:*\n"
        "1. Создаёшь существо из трёх компонентов\n"
        "2. Оно попадает в общую экосистему\n"
        "3. Бот автоматически генерирует события взаимодействия\n"
        "4. Следи за развитием безумия!\n\n"
        "*Основные команды:*\n"
        "`/create` — создать новое существо\n"
        "`/my` — посмотреть своих существ (до 5)\n"
        "`/events` — последние события в заповеднике\n"
        "`/stats` — статистика заповедника\n"
        "`/materials` — список доступных материалов\n"
        "`/behaviors` — список доступных поведений\n"
        "`/traits` — список доступных признаков\n\n"
        f"📢 *Канал событий:* {settings.EVENT_CHANNEL}\n"
        f"🕐 *Интервал событий:* {settings.EVENT_INTERVAL//60} минут\n\n"
        "💡 *Совет:* Чем абсурднее комбинация, тем интереснее события!"
    )
    await message.reply(welcome_text, parse_mode='Markdown')

@dp.message_handler(commands=['create'])
async def cmd_create(message: types.Message):
    """Начать создание существа"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Показываем только первые 8 элементов для удобства
    for material in settings.MATERIALS[:8]:
        keyboard.add(material)
    
    # Добавляем кнопку "Показать все"
    keyboard.add("📋 Показать все материалы")
    
    await message.reply(
        "🎲 *ШАГ 1 из 3*\nВыбери *МАТЕРИАЛ* существа:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await CreatureCreation.material.set()

@dp.message_handler(state=CreatureCreation.material)
async def process_material(message: types.Message, state: FSMContext):
    """Обработка выбора материала"""
    material = message.text.strip()
    
    # Обработка кнопки "Показать все"
    if material == "📋 Показать все материалы":
        all_materials = "\n".join([f"• {m}" for m in settings.MATERIALS])
        await message.reply(
            f"📋 *Все материалы:*\n{all_materials}\n\n"
            "Введи название материала:",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    
    if material not in settings.MATERIALS:
        await message.reply(
            "❌ Такого материала нет в списке!\n"
            "Используй команду `/materials` чтобы увидеть все варианты.",
            parse_mode='Markdown'
        )
        return
    
    async with state.proxy() as data:
        data['material'] = material
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    for behavior in settings.BEHAVIORS[:8]:
        keyboard.add(behavior)
    
    keyboard.add("📋 Показать все поведения")
    
    await message.reply(
        "🎲 *ШАГ 2 из 3*\nВыбери *ПОВЕДЕНИЕ* существа:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await CreatureCreation.behavior.set()

@dp.message_handler(state=CreatureCreation.behavior)
async def process_behavior(message: types.Message, state: FSMContext):
    """Обработка выбора поведения"""
    behavior = message.text.strip()
    
    if behavior == "📋 Показать все поведения":
        all_behaviors = "\n".join([f"• {b}" for b in settings.BEHAVIORS])
        await message.reply(
            f"📋 *Все поведения:*\n{all_behaviors}\n\n"
            "Введи название поведения:",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    
    if behavior not in settings.BEHAVIORS:
        await message.reply(
            "❌ Такого поведения нет в списке!\n"
            "Используй команду `/behaviors` чтобы увидеть все варианты.",
            parse_mode='Markdown'
        )
        return
    
    async with state.proxy() as data:
        data['behavior'] = behavior
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    for trait in settings.TRAITS[:8]:
        keyboard.add(trait)
    
    keyboard.add("📋 Показать все признаки")
    
    await message.reply(
        "🎲 *ШАГ 3 из 3*\nВыбери *ОСОБЫЙ ПРИЗНАК*:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await CreatureCreation.trait.set()

@dp.message_handler(state=CreatureCreation.trait)
async def process_trait(message: types.Message, state: FSMContext):
    """Финальный шаг создания существа"""
    trait = message.text.strip()
    
    if trait == "📋 Показать все признаки":
        all_traits = "\n".join([f"• {t}" for t in settings.TRAITS])
        await message.reply(
            f"📋 *Все признаки:*\n{all_traits}\n\n"
            "Введи название признака:",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    
    if trait not in settings.TRAITS:
        await message.reply(
            "❌ Такого признака нет в списке!\n"
            "Используй команду `/traits` чтобы увидеть все варианты.",
            parse_mode='Markdown'
        )
        return
    
    async with state.proxy() as data:
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name or f"User_{user_id}"
        
        try:
            # Сохраняем в базу
            conn = get_connection()
            c = conn.cursor()
            c.execute('''INSERT INTO creatures 
                        (user_id, username, material, behavior, trait) 
                        VALUES (?, ?, ?, ?, ?)''',
                     (user_id, username, data['material'], data['behavior'], trait))
            creature_id = c.lastrowid
            conn.commit()
            
            # Получаем статистику пользователя
            c.execute('''SELECT COUNT(*) FROM creatures WHERE user_id = ?''', (user_id,))
            user_creature_count = c.fetchone()[0]
            
            conn.close()
            
            # Формируем креативное описание
            creature_name = f"{data['material']} {data['behavior'].lower()}"
            descriptions = [
                f"✨ Существо обладает невероятными способностями!",
                f"🌀 Новая форма жизни обнаружена!",
                f"🌟 Зафиксирован аномальный уровень абсурда!",
                f"💫 Это может изменить экосистему навсегда!",
            ]
            
            response = (
                f"✅ *Существо #{creature_id} успешно создано!*\n\n"
                f"🔮 *{creature_name}*\n"
                f"⚡ *Признак:* {trait}\n"
                f"👤 *Создатель:* {username}\n"
                f"📅 *Заселено:* {datetime.now().strftime('%H:%M %d.%m')}\n\n"
                f"{random.choice(descriptions)}\n\n"
                f"📊 *Ваша коллекция:* {user_creature_count} существ\n"
                f"🔜 Скоро появится в событиях заповедника!"
            )
            
            await message.reply(
                response, 
                parse_mode='Markdown',
                reply_markup=types.ReplyKeyboardRemove()
            )
            
            logger.info(f"Создано существо #{creature_id} пользователем {username}")
            
        except Exception as e:
            logger.error(f"Ошибка при создании существа: {e}")
            await message.reply(
                "❌ Произошла ошибка при создании существа. Попробуйте позже.",
                reply_markup=types.ReplyKeyboardRemove()
            )
    
    await state.finish()

@dp.message_handler(commands=['my'])
async def cmd_my(message: types.Message):
    """Показать существ пользователя"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''SELECT id, material, behavior, trait, created_at 
                     FROM creatures 
                     WHERE user_id = ? 
                     ORDER BY id DESC LIMIT 5''',
                  (message.from_user.id,))
        creatures = c.fetchall()
        
        # Общее количество существ пользователя
        c.execute('''SELECT COUNT(*) FROM creatures WHERE user_id = ?''',
                  (message.from_user.id,))
        total_count = c.fetchone()[0]
        
        conn.close()
        
        if not creatures:
            await message.reply(
                "📭 У тебя пока нет существ.\n"
                "Создай первое командой `/create`",
                parse_mode='Markdown'
            )
            return
        
        response = f"🦠 *Твои существа* ({total_count} всего):\n\n"
        
        for i, creature in enumerate(creatures, 1):
            creature_id, material, behavior, trait, created_at = creature
            created_time = created_at.split()[1][:5] if ' ' in str(created_at) else '??:??'
            created_date = created_at.split()[0] if ' ' in str(created_at) else created_at
            
            response += (
                f"{i}. *#{creature_id}: {material} {behavior.lower()}*\n"
                f"   🏷️ `{trait}`\n"
                f"   📅 {created_date} {created_time}\n\n"
            )
        
        if total_count > 5:
            response += f"*Показано 5 из {total_count} существ. Создай больше!*"
        
        await message.reply(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка существ: {e}")
        await message.reply("❌ Ошибка при получении списка существ.")

@dp.message_handler(commands=['events'])
async def cmd_events(message: types.Message):
    """Показать последние события"""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''SELECT event_text, created_at 
                     FROM events 
                     ORDER BY id DESC LIMIT 5''')
        events = c.fetchall()
        conn.close()
        
        if not events:
            await message.reply(
                "📭 В заповеднике пока тихо...\n"
                "Создай первое существо командой `/create` чтобы запустить экосистему!"
            )
            return
        
        response = "📜 *Последние события в Заповеднике:*\n\n"
        
        for i, event in enumerate(events, 1):
            event_text, created_at = event
            time = created_at.split()[1][:5] if ' ' in str(created_at) else '??:??'
            date = created_at.split()[0] if ' ' in str(created_at) else created_at
            
            # Украшаем разные типы событий
            if "💥" in event_text:
                emoji = "💥"
            elif "🌀" in event_text:
                emoji = "🌀"
            elif "✨" in event_text:
                emoji = "✨"
            elif "🤝" in event_text:
                emoji = "🤝"
            else:
                emoji = "🔸"
            
            response += f"{emoji} *{event_text}*\n   🕐 {date} {time}\n\n"
        
        response += f"📢 *Канал событий:* {settings.EVENT_CHANNEL}"
        
        await message.reply(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка при получении событий: {e}")
        await message.reply("❌ Ошибка при получении событий.")

@dp.message_handler(commands=['stats'])
async def cmd_stats(message: types.Message):
    """Статистика заповедника"""
    try:
        conn = get_connection()
        c = conn.cursor()
        
        # Общая статистика
        c.execute("SELECT COUNT(*) FROM creatures")
        total_creatures = c.fetchone()[0]
        
        c.execute("SELECT COUNT(DISTINCT user_id) FROM creatures")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM events")
        total_events = c.fetchone()[0]
        
        # Самый активный пользователь
        c.execute('''SELECT username, COUNT(*) as cnt 
                     FROM creatures 
                     GROUP BY user_id 
                     ORDER BY cnt DESC 
                     LIMIT 1''')
        top_user = c.fetchone() or ("Нет данных", 0)
        
        # Самый популярный материал
        c.execute('''SELECT material, COUNT(*) as cnt 
                     FROM creatures 
                     GROUP BY material 
                     ORDER BY cnt DESC 
                     LIMIT 1''')
        popular_material = c.fetchone() or ("Нет данных", 0)
        
        # Последнее существо
        c.execute('''SELECT username, material, behavior 
                     FROM creatures 
                     ORDER BY id DESC 
                     LIMIT 1''')
        last_creature = c.fetchone() or ("Нет данных", "Нет данных", "Нет данных")
        
        conn.close()
        
        stats_text = (
            "📊 *Статистика Заповедника Абсурда*\n\n"
            f"👥 *Пользователей:* {total_users}\n"
            f"🦠 *Существ создано:* {total_creatures}\n"
            f"📜 *Событий сгенерировано:* {total_events}\n"
            f"🏆 *Самый активный:* {top_user[0]} ({top_user[1]} существ)\n"
            f"🔮 *Популярный материал:* {popular_material[0]}\n\n"
            f"🆕 *Последнее существо:*\n"
            f"   {last_creature[1]} {last_creature[2]}\n"
            f"   👤 от {last_creature[0]}\n\n"
            f"📢 *Канал событий:* {settings.EVENT_CHANNEL}\n"
            f"⏱️ *Интервал:* {settings.EVENT_INTERVAL//60} минут\n\n"
            f"🌐 *Веб-панель:* https://{os.environ.get('RENDER_SERVICE_NAME', 'ваш-сервис')}.onrender.com"
        )
        
        await message.reply(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        await message.reply("❌ Ошибка при получении статистики.")

@dp.message_handler(commands=['materials'])
async def cmd_materials(message: types.Message):
    """Показать все материалы"""
    materials_list = "\n".join([f"• {mat}" for mat in settings.MATERIALS])
    await message.reply(
        f"📋 *Доступные материалы ({len(settings.MATERIALS)}):*\n\n{materials_list}",
        parse_mode='Markdown'
    )

@dp.message_handler(commands=['behaviors'])
async def cmd_behaviors(message: types.Message):
    """Показать все поведения"""
    behaviors_list = "\n".join([f"• {beh}" for beh in settings.BEHAVIORS])
    await message.reply(
        f"📋 *Доступные поведения ({len(settings.BEHAVIORS)}):*\n\n{behaviors_list}",
        parse_mode='Markdown'
    )

@dp.message_handler(commands=['traits'])
async def cmd_traits(message: types.Message):
    """Показать все признаки"""
    traits_list = "\n".join([f"• {trait}" for trait in settings.TRAITS])
    await message.reply(
        f"📋 *Доступные признаки ({len(settings.TRAITS)}):*\n\n{traits_list}",
        parse_mode='Markdown'
    )

# ========== ГЕНЕРАЦИЯ СОБЫТИЙ ==========

async def generate_random_event():
    """Создать случайное событие в экосистеме"""
    try:
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
        
        # Шаблоны событий с разными типами
        event_templates = [
            # Встречи
            f"🔄 *Встреча*: {creature1[1]} {creature1[2]} пересекся с {creature2[1]} {creature2[2]}...",
            f"👀 *Наблюдение*: {creature1[4]} заметил необычное поведение у {creature2[1]}",
            
            # Конфликты
            f"💥 *Конфликт*: '{creature1[3]}' вступил в противоречие с '{creature2[3]}'!",
            f"⚡ *Столкновение*: {creature1[1]} vs {creature2[1]} — битва абсурда!",
            
            # Симбиоз
            f"🤝 *Симбиоз*: {creature1[1]} и {creature2[1]} образовали нестабильный альянс.",
            f"🌀 *Слияние*: Под влиянием {creature2[2]} у {creature1[1]} проявился новый признак.",
            
            # Развитие
            f"📈 *Эволюция*: {creature1[4]} и {creature2[4]} создали гибрид абсурда.",
            f"🌟 *Прозрение*: {creature1[1]} осознал свою природу благодаря {creature2[3]}",
            
            # Абсурдные ситуации
            f"🎭 *Инцидент*: {creature1[1]} {creature1[2]} нарушил правила заповедника.",
            f"📜 *Документация*: Зафиксировано взаимодействие между {creature1[3]} и {creature2[3]}",
        ]
        
        # Выбираем случайный шаблон
        event_text = random.choice(event_templates)
        
        # Сохраняем событие в базу
        c.execute('''INSERT INTO events (creature1_id, creature2_id, event_text)
                     VALUES (?, ?, ?)''', (creature1[0], creature2[0], event_text))
        conn.commit()
        conn.close()
        
        return event_text
        
    except Exception as e:
        logger.error(f"Ошибка при генерации события: {e}")
        return None

async def event_scheduler():
    """Планировщик для автоматической генерации событий"""
    logger.info(f"🎬 Планировщик событий запущен (интервал: {settings.EVENT_INTERVAL} секунд)")
    
    while True:
        try:
            await asyncio.sleep(settings.EVENT_INTERVAL)
            
            # Генерируем событие
            event = await generate_random_event()
            if event:
                # Отправляем в канал
                await bot.send_message(settings.EVENT_CHANNEL, event, parse_mode='Markdown')
                logger.info(f"📨 Отправлено событие в канал: {event[:50]}...")
            else:
                logger.info("📭 Недостаточно существ для генерации события")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике событий: {e}")
            await asyncio.sleep(60)  # Ждем минуту при ошибке

# ========== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ==========

@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle_text(message: types.Message):
    """Обработка обычных текстовых сообщений"""
    text = message.text.lower()
    
    # Ответы на ключевые слова
    responses = {
        'привет': '🐙 Приветствую в Заповеднике Абсурда! Используй /help для списка команд.',
        'бот': '🤖 Да, я бот Заповедника Абсурда! Создавай существ и наблюдай за хаосом.',
        'существо': '🦠 Чтобы создать существо, используй команду /create',
        'абсурд': '🌀 Абсурд — наша валюта, наш бог, наше всё!',
        'помощь': '📚 Используй /help для получения справки',
    }
    
    for keyword, response in responses.items():
        if keyword in text:
            await message.reply(response)
            return
    
    # Если не нашли ключевое слово
    if len(text) < 50:  # Не реагируем на длинные сообщения
        await message.reply(
            "🤔 Не понимаю...\n"
            "Используй /create чтобы создать существо\n"
            "или /help для списка команд."
        )

# ========== ЗАПУСК ==========

async def on_startup(dp):
    """Действия при запуске бота"""
    global bot_username
    
    logger.info("=" * 50)
    logger.info("🐙 ЗАПУСК ЗАПОВЕДНИКА АБСУРДА")
    logger.info("=" * 50)
    
    # Инициализация базы данных
    init_db()
    
    # Получаем информацию о боте
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    logger.info(f"🤖 Бот: @{bot_username}")
    logger.info(f"📢 Канал событий: {settings.EVENT_CHANNEL}")
    logger.info(f"⏱️ Интервал событий: {settings.EVENT_INTERVAL} сек ({settings.EVENT_INTERVAL//60} мин)")
    
    # Запускаем планировщик событий
    asyncio.create_task(event_scheduler())
    
    # Обновляем HTML шаблон Flask
    @app.context_processor
    def inject_stats():
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM creatures")
        creatures = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT user_id) FROM creatures")
        users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM events")
        events = c.fetchone()[0]
        conn.close()
        
        return {
            'users': users,
            'creatures': creatures,
            'events': events,
            'bot_username': bot_username,
            'event_channel': settings.EVENT_CHANNEL,
            'interval': settings.EVENT_INTERVAL
        }
    
    logger.info("✅ Заповедник Абсурда готов к работе!")
    logger.info("🌐 Веб-панель будет доступна на порту 8080")

def run_bot():
    """Запуск бота в отдельном потоке"""
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup
    )

if __name__ == '__main__':
    # Запускаем Flask сервер для Render
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🚀 Flask сервер запущен")
    
    # Запускаем бота
    run_bot()
