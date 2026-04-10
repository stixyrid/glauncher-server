"""
База данных для лаунчера
Хранение пользователей, подписок, ключей
"""

import sqlite3
import hashlib
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List

class Database:
    def __init__(self, db_path="launcher.db"):
        self.db_path = db_path
        self.init_db()
        self.upgrade_db()  # Добавляем обновление структуры
    
    def upgrade_db(self):
        """Обновление структуры базы данных если нужно"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Проверяем и добавляем колонку created_by если её нет
        try:
            cursor.execute("SELECT created_by FROM license_keys LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE license_keys ADD COLUMN created_by TEXT")
        
        conn.commit()
        conn.close()
    
    def generate_user_id(self) -> int:
        """Генерация случайного 5-значного ID"""
        while True:
            user_id = random.randint(10000, 99999)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
            exists = cursor.fetchone()
            conn.close()
            if not exists:
                return user_id
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                hwid TEXT,
                subscription_end DATE,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица ключей активации
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS license_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                days INTEGER NOT NULL,
                used_by INTEGER,
                used_at TIMESTAMP,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создание админа с фиксированным ID 1
        admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
        try:
            cursor.execute('''
                INSERT INTO users (id, username, password, is_admin, subscription_end)
                VALUES (?, ?, ?, ?, ?)
            ''', (1, "admin", admin_pass, 1, (datetime.now() + timedelta(days=365)).date()))
        except:
            pass
        
        # Создание тестового пользователя с фиксированным ID 2
        test_pass = hashlib.sha256("test123".encode()).hexdigest()
        try:
            cursor.execute('''
                INSERT INTO users (id, username, password, is_admin, subscription_end)
                VALUES (?, ?, ?, ?, ?)
            ''', (2, "test", test_pass, 0, (datetime.now() + timedelta(days=30)).date()))
        except:
            pass
        
        conn.commit()
        conn.close()
    
    def register_user(self, username: str, password: str, hwid: str) -> bool:
        """Регистрация нового пользователя с рандомным ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            user_id = self.generate_user_id()
            hashed_pass = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (id, username, password, hwid, subscription_end)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, hashed_pass, hwid, None))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Registration error: {e}")
            return False
    
    def login_user(self, username: str, password: str, hwid: str) -> Optional[Dict]:
        """Авторизация пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        hashed_pass = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute('''
            SELECT id, username, hwid, subscription_end, is_admin 
            FROM users 
            WHERE username = ? AND password = ?
        ''', (username, hashed_pass))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            # Проверка HWID
            if user[2] and user[2] != hwid:
                return None
            
            # Проверка подписки
            sub_end = datetime.strptime(user[3], '%Y-%m-%d') if user[3] else None
            has_subscription = sub_end and sub_end > datetime.now()
            
            return {
                'id': user[0],
                'username': user[1],
                'has_subscription': has_subscription,
                'subscription_days': (sub_end - datetime.now()).days if has_subscription else 0,
                'is_admin': bool(user[4])
            }
        return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Поиск пользователя по ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, subscription_end, is_admin 
            FROM users 
            WHERE id = ?
        ''', (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                'id': user[0],
                'username': user[1],
                'subscription_end': user[2],
                'is_admin': bool(user[3])
            }
        return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Поиск пользователя по никнейму"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, subscription_end, is_admin 
            FROM users 
            WHERE username = ?
        ''', (username,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                'id': user[0],
                'username': user[1],
                'subscription_end': user[2] if user[2] else "Нет",
                'is_admin': bool(user[3])
            }
        return None
    
    def activate_key(self, key: str, user_id: int, days: int) -> bool:
        """Активация лицензионного ключа"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Проверяем ключ
        cursor.execute('SELECT id, days, used_by FROM license_keys WHERE key = ?', (key,))
        key_data = cursor.fetchone()
        
        if not key_data or key_data[2] is not None:
            conn.close()
            return False
        
        # Активируем ключ
        cursor.execute('''
            UPDATE license_keys 
            SET used_by = ?, used_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (user_id, key_data[0]))
        
        # Обновляем подписку пользователя
        cursor.execute('SELECT subscription_end FROM users WHERE id = ?', (user_id,))
        current_end = cursor.fetchone()
        
        if current_end and current_end[0]:
            new_end = datetime.strptime(current_end[0], '%Y-%m-%d') + timedelta(days=key_data[1])
        else:
            new_end = datetime.now() + timedelta(days=key_data[1])
        
        cursor.execute('''
            UPDATE users SET subscription_end = ? WHERE id = ?
        ''', (new_end.date(), user_id))
        
        conn.commit()
        conn.close()
        return True
    
    def create_key(self, days: int, created_by: str) -> str:
        """Создание нового ключа (только для админа)"""
        import random
        import string
        
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        key_formatted = f"{key[:4]}-{key[4:8]}-{key[8:12]}-{key[12:]}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO license_keys (key, days, created_by)
            VALUES (?, ?, ?)
        ''', (key_formatted, days, created_by))
        
        conn.commit()
        conn.close()
        return key_formatted
    
    def get_all_keys(self) -> List[Dict]:
        """Получение всех ключей (для админа)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, key, days, used_by, used_at, created_by, created_at 
            FROM license_keys 
            ORDER BY created_at DESC
        ''')
        keys = cursor.fetchall()
        conn.close()
        
        result = []
        for key in keys:
            # Получаем имя использовавшего пользователя
            used_by_name = None
            if key[3]:
                user = self.get_user_by_id(key[3])
                used_by_name = user['username'] if user else str(key[3])
            
            result.append({
                'id': key[0],
                'key': key[1],
                'days': key[2],
                'used_by': used_by_name,
                'used_at': key[4],
                'created_by': key[5] if key[5] else "admin",
                'created_at': key[6]
            })
        
        return result
    
    def extend_subscription(self, user_id: int, days: int) -> bool:
        """Продление подписки (для админа)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT subscription_end FROM users WHERE id = ?', (user_id,))
        current_end = cursor.fetchone()
        
        if current_end and current_end[0]:
            new_end = datetime.strptime(current_end[0], '%Y-%m-%d') + timedelta(days=days)
        else:
            new_end = datetime.now() + timedelta(days=days)
        
        cursor.execute('''
            UPDATE users SET subscription_end = ? WHERE id = ?
        ''', (new_end.date(), user_id))
        
        conn.commit()
        conn.close()
        return True
    
    def get_all_users(self) -> List[Dict]:
        """Получение всех пользователей (для админа)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, username, subscription_end, is_admin FROM users ORDER BY id')
        users = cursor.fetchall()
        conn.close()
        
        return [{'id': u[0], 'username': u[1], 'subscription_end': u[2] or "Нет", 'is_admin': u[3]} for u in users]