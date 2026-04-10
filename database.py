import sqlite3
import hashlib
import random
import string
from datetime import datetime, timedelta
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'launcher.db')

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Получение соединения с БД"""
        return sqlite3.connect(self.db_path)
    
    def generate_user_id(self):
        """Генерация случайного 5-значного ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        while True:
            user_id = random.randint(10000, 99999)
            cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
            if not cursor.fetchone():
                conn.close()
                return user_id
        conn.close()
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                hwid TEXT,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица подписок пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product TEXT NOT NULL,
                subscription_end DATE,
                UNIQUE(user_id, product)
            )
        ''')
        
        # Таблица ключей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS license_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                product TEXT NOT NULL,
                days INTEGER NOT NULL,
                used_by INTEGER,
                used_at TIMESTAMP,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создание админа (ID = 1) если нет
        admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute('SELECT id FROM users WHERE id = 1')
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO users (id, username, password, is_admin)
                VALUES (?, ?, ?, ?)
            ''', (1, "admin", admin_pass, 1))
            print("✅ Админ создан: admin / admin123")
            
            # Выдаем админу подписки на все продукты
            for product in ['gboost', 'ghelper', 'gtrigger']:
                cursor.execute('''
                    INSERT INTO user_subscriptions (user_id, product, subscription_end)
                    VALUES (?, ?, ?)
                ''', (1, product, (datetime.now() + timedelta(days=365)).date()))
            print("✅ Админу выданы подписки на все продукты")
        
        # Создание тестового пользователя (ID = 2) если нет
        test_pass = hashlib.sha256("test123".encode()).hexdigest()
        cursor.execute('SELECT id FROM users WHERE id = 2')
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO users (id, username, password, is_admin)
                VALUES (?, ?, ?, ?)
            ''', (2, "test", test_pass, 0))
            print("✅ Тестовый пользователь создан: test / test123")
            
            # Выдаем тестовому пользователю подписку на G BOOST
            cursor.execute('''
                INSERT INTO user_subscriptions (user_id, product, subscription_end)
                VALUES (?, ?, ?)
            ''', (2, 'gboost', (datetime.now() + timedelta(days=30)).date()))
            print("✅ Тестовому пользователю выдана подписка на G BOOST")
        
        conn.commit()
        conn.close()
    
    def register_user(self, username: str, password: str, hwid: str) -> bool:
        """Регистрация нового пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            user_id = self.generate_user_id()
            hashed_pass = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (id, username, password, hwid)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, hashed_pass, hwid))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Registration error: {e}")
            return False
    
    def login_user(self, username: str, password: str, hwid: str):
        """Авторизация пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        hashed_pass = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute('''
            SELECT id, username, hwid, is_admin 
            FROM users 
            WHERE username = ? AND password = ?
        ''', (username, hashed_pass))
        
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return None
        
        # Проверка HWID
        if user[2] and user[2] != hwid:
            return None
        
        # Обновляем HWID если не привязан
        if not user[2]:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET hwid = ? WHERE id = ?', (hwid, user[0]))
            conn.commit()
            conn.close()
        
        return {
            'id': user[0],
            'username': user[1],
            'is_admin': bool(user[3])
        }
    
    def get_user_by_id(self, user_id: int):
        """Получение пользователя по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, hwid, is_admin, created_at FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                'id': user[0],
                'username': user[1],
                'hwid': user[2],
                'is_admin': bool(user[3]),
                'created_at': user[4]
            }
        return None
    
    def get_user_by_username(self, username: str):
        """Получение пользователя по никнейму"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, hwid, is_admin, created_at FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                'id': user[0],
                'username': user[1],
                'hwid': user[2],
                'is_admin': bool(user[3]),
                'created_at': user[4]
            }
        return None
    
    def activate_key(self, key: str, user_id: int, days: int) -> bool:
        """Активация лицензионного ключа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Проверяем ключ
        cursor.execute('SELECT id, product, days, used_by FROM license_keys WHERE key = ?', (key,))
        key_data = cursor.fetchone()
        
        if not key_data or key_data[3] is not None:
            conn.close()
            return False
        
        # Активируем ключ
        cursor.execute('''
            UPDATE license_keys 
            SET used_by = ?, used_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (user_id, key_data[0]))
        
        # Обновляем подписку пользователя
        cursor.execute('''
            SELECT subscription_end FROM user_subscriptions 
            WHERE user_id = ? AND product = ?
        ''', (user_id, key_data[1]))
        
        current = cursor.fetchone()
        
        if current and current[0]:
            new_end = datetime.strptime(current[0], '%Y-%m-%d') + timedelta(days=key_data[2])
            cursor.execute('''
                UPDATE user_subscriptions 
                SET subscription_end = ? 
                WHERE user_id = ? AND product = ?
            ''', (new_end.date(), user_id, key_data[1]))
        else:
            new_end = datetime.now() + timedelta(days=key_data[2])
            cursor.execute('''
                INSERT INTO user_subscriptions (user_id, product, subscription_end)
                VALUES (?, ?, ?)
            ''', (user_id, key_data[1], new_end.date()))
        
        conn.commit()
        conn.close()
        return True
    
    def create_key(self, days: int, product: str, created_by: str) -> str:
        """Создание нового ключа"""
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        key_formatted = f"{key[:4]}-{key[4:8]}-{key[8:12]}-{key[12:]}"
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO license_keys (key, product, days, created_by)
            VALUES (?, ?, ?, ?)
        ''', (key_formatted, product, days, created_by))
        conn.commit()
        conn.close()
        
        return key_formatted
    
    def get_all_keys(self):
        """Получение всех ключей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, key, product, days, used_by, used_at, created_by, created_at 
            FROM license_keys 
            ORDER BY created_at DESC
        ''')
        keys = cursor.fetchall()
        conn.close()
        
        result = []
        for key in keys:
            result.append({
                'id': key[0],
                'key': key[1],
                'product': key[2],
                'days': key[3],
                'used_by': key[4],
                'used_at': key[5],
                'created_by': key[6],
                'created_at': key[7]
            })
        return result
    
    def extend_subscription(self, user_id: int, product: str, days: int) -> bool:
        """Продление подписки"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT subscription_end FROM user_subscriptions 
            WHERE user_id = ? AND product = ?
        ''', (user_id, product))
        
        current = cursor.fetchone()
        
        if current and current[0]:
            new_end = datetime.strptime(current[0], '%Y-%m-%d') + timedelta(days=days)
            cursor.execute('''
                UPDATE user_subscriptions 
                SET subscription_end = ? 
                WHERE user_id = ? AND product = ?
            ''', (new_end.date(), user_id, product))
        else:
            new_end = datetime.now() + timedelta(days=days)
            cursor.execute('''
                INSERT INTO user_subscriptions (user_id, product, subscription_end)
                VALUES (?, ?, ?)
            ''', (user_id, product, new_end.date()))
        
        conn.commit()
        conn.close()
        return True
    
    def get_all_users(self):
        """Получение всех пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username FROM users ORDER BY id')
        users = cursor.fetchall()
        conn.close()
        
        return [{'id': u[0], 'username': u[1]} for u in users]