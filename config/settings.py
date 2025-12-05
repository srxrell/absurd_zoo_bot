import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

class Settings:
    # Обязательные настройки
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    EVENT_CHANNEL = os.getenv("EVENT_CHANNEL")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "absurd.db")
    EVENT_INTERVAL = int(os.getenv("EVENT_INTERVAL", 1800))
    
    # Списки для генерации существ (можно расширять)
    MATERIALS = [
        "Стекло", "Бюрократия", "Пыль", "Ностальгия",
        "Незаконченный код", "Канцелярская резина",
        "Упущенная выгода", "Криптовалюта"
    ]
    
    BEHAVIORS = [
        "Питается отложенными делами",
        "Размножается заполнением актов",
        "Мигрирует вслед за опечатками",
        "Зимует в кэше браузера",
        "Охотится на неотвеченные письма"
    ]
    
    TRAITS = [
        "Гипнотизирующий узор из ошибок 404",
        "Постоянно теряет доверенность",
        "Пахнет упущенной выгодой",
        "Имеет встроенный сарказм",
        "При попытке удалить множится",
        "Требует одобрения в трёх инстанциях"
    ]
    
    # Валидация обязательных полей
    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN не установлен в .env файле")
        if not cls.EVENT_CHANNEL:
            raise ValueError("❌ EVENT_CHANNEL не установлен в .env файле")
        print("✅ Конфигурация загружена успешно")

# Создаем экземпляр настроек
settings = Settings()
settings.validate()
