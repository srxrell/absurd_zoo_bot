import sqlite3
import os
from config.settings import settings

def get_db_path():
    """Определяем путь к БД для разных окружений"""
    # На Render используем /opt/render/project/src
    if 'RENDER' in os.environ:
        return '/opt/render/project/src/absurd.db'
    # Локально используем настройки
    return settings.DATABASE_PATH

def init_db():
    """Инициализация базы данных"""
    db_path = get_db_path()
    print(f"📦 Инициализация БД по пути: {db_path}")
    
    # Создаем директорию если нужно
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Таблица существ
    c.execute('''CREATE TABLE IF NOT EXISTS creatures
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  username TEXT,
                  material TEXT NOT NULL,
                  behavior TEXT NOT NULL,
                  trait TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Таблица событий
    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  creature1_id INTEGER,
                  creature2_id INTEGER,
                  event_text TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()
    print(f"✅ База данных инициализирована: {db_path}")
    print(f"   Место: {os.path.abspath(db_path)}")

def get_connection():
    """Получить соединение с базой"""
    db_path = get_db_path()
    return sqlite3.connect(db_path)

if __name__ == '__main__':
    init_db()
