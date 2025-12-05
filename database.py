import sqlite3
from config.settings import settings

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(settings.DATABASE_PATH)
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
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (creature1_id) REFERENCES creatures (id),
                  FOREIGN KEY (creature2_id) REFERENCES creatures (id))''')
    
    conn.commit()
    conn.close()
    print(f"✅ База данных инициализирована: {settings.DATABASE_PATH}")

def get_connection():
    """Получить соединение с базой"""
    return sqlite3.connect(settings.DATABASE_PATH)

if __name__ == '__main__':
    init_db()
