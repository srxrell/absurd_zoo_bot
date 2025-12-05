import os
from dotenv import load_dotenv
import ast

# Загружаем .env файл
load_dotenv()

class Config:
    # Основные настройки
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    EVENT_CHANNEL = os.getenv('EVENT_CHANNEL')
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'absurd.db')
    EVENT_INTERVAL = int(os.getenv('EVENT_INTERVAL', 1800))
    
    # Парсим списки из строк
    MATERIALS = [m.strip() for m in os.getenv('MATERIALS', '').split(',') if m.strip()]
    BEHAVIORS = [b.strip() for b in os.getenv('BEHAVIORS', '').split(',') if b.strip()]
    TRAITS = [t.strip() for t in os.getenv('TRAITS', '').split(',') if t.strip()]
    
    # Проверка обязательных переменных
    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен в .env файле")
        if not cls.EVENT_CHANNEL:
            raise ValueError("EVENT_CHANNEL не установлен в .env файле")
        if not cls.MATERIALS:
            raise ValueError("MATERIALS не установлены в .env файле")
        print("✅ Конфигурация загружена")

# Валидируем при импорте
Config.validate()
