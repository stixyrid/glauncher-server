"""
Сервер для GLauncher
Поддержка нескольких продуктов: G BOOST, G HELPER, G TRIGGER
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib
import random
import string
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(__file__), 'launcher.db')

# Список продуктов
PRODUCTS = {
    'gboost': {'name': 'G BOOST', 'exe': 'G_BOOST.exe', 'color': '#00ff00'},
    'ghelper': {'name': 'G HELPER', 'exe': 'G_Helper.exe', 'color': '#ffaa00'},
    'gtrigger': {'name': 'G TRIGGER', 'exe': 'G_Trigger.exe', 'color': '#ff4444'}
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных"""
    conn = get_db()
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
    
    # Таблица подписок пользователей (по продуктам)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product TEXT NOT NULL,
            subscription_end DATE,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, product)
        )
    ''')
    
    # Таблица ключей (с привязкой к продукту)
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
    
    # Проверяем и создаем админа (ID = 1)
    cursor.execute('SELECT id FROM users WHERE id = 1')
    if not cursor.fetchone():
        admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute('''
            INSERT INTO users (id, username, password, is_admin)
            VALUES (?, ?, ?, ?)
        ''', (1, "admin", admin_pass, 1))
        print("✅ Админ создан: admin / admin123")
        
        # Выдаем админу подписки на все продукты на 365 дней
        for product in PRODUCTS.keys():
            cursor.execute('''
                INSERT INTO user_subscriptions (user_id, product, subscription_end)
                VALUES (?, ?, ?)
            ''', (1, product, (datetime.now() + timedelta(days=365)).date()))
        print("✅ Админу выданы подписки на все продукты")
    
    # Проверяем и создаем тестового пользователя (ID = 2)
    cursor.execute('SELECT id FROM users WHERE id = 2')
    if not cursor.fetchone():
        test_pass = hashlib.sha256("test123".encode()).hexdigest()
        cursor.execute('''
            INSERT INTO users (id, username, password, is_admin)
            VALUES (?, ?, ?, ?)
        ''', (2, "test", test_pass, 0))
        print("✅ Тестовый пользователь создан: test / test123")
        
        # Выдаем тестовому пользователю подписку на G BOOST на 30 дней
        cursor.execute('''
            INSERT INTO user_subscriptions (user_id, product, subscription_end)
            VALUES (?, ?, ?)
        ''', (2, 'gboost', (datetime.now() + timedelta(days=30)).date()))
        print("✅ Тестовому пользователю выдана подписка на G BOOST")
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

# Запускаем инициализацию БД
init_db()

def generate_user_id():
    """Генерация случайного ID (от 10000 до 99999)"""
    conn = get_db()
    cursor = conn.cursor()
    while True:
        user_id = random.randint(10000, 99999)
        cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
        if not cursor.fetchone():
            conn.close()
            return user_id
    conn.close()

def check_subscription(user_id, product):
    """Проверка активной подписки на продукт"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT subscription_end FROM user_subscriptions 
        WHERE user_id = ? AND product = ?
    ''', (user_id, product))
    result = cursor.fetchone()
    conn.close()
    
    if result and result['subscription_end']:
        sub_end = datetime.strptime(result['subscription_end'], '%Y-%m-%d')
        return sub_end > datetime.now()
    return False

def get_subscription_days(user_id, product):
    """Получение количества дней подписки"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT subscription_end FROM user_subscriptions 
        WHERE user_id = ? AND product = ?
    ''', (user_id, product))
    result = cursor.fetchone()
    conn.close()
    
    if result and result['subscription_end']:
        sub_end = datetime.strptime(result['subscription_end'], '%Y-%m-%d')
        days_left = (sub_end - datetime.now()).days
        return max(0, days_left)
    return 0

# ==================== API ENDPOINTS ====================

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        hwid = data.get('hwid', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Заполните все поля'})
        
        if len(username) < 3:
            return jsonify({'success': False, 'error': 'Имя пользователя не менее 3 символов'})
        
        if len(password) < 4:
            return jsonify({'success': False, 'error': 'Пароль не менее 4 символов'})
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Пользователь уже существует'})
        
        user_id = generate_user_id()
        hashed_pass = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute('''
            INSERT INTO users (id, username, password, hwid)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, hashed_pass, hwid))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Регистрация успешна'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        hwid = data.get('hwid', '').strip()
        
        conn = get_db()
        cursor = conn.cursor()
        
        hashed_pass = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute('''
            SELECT id, username, hwid, is_admin 
            FROM users 
            WHERE username = ? AND password = ?
        ''', (username, hashed_pass))
        
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'Неверное имя пользователя или пароль'})
        
        # Проверка HWID
        if user['hwid'] and user['hwid'] != hwid:
            conn.close()
            return jsonify({'success': False, 'error': 'HWID не совпадает. Доступ только с этого ПК'})
        
        if not user['hwid']:
            cursor.execute('UPDATE users SET hwid = ? WHERE id = ?', (hwid, user['id']))
            conn.commit()
        
        # Получаем подписки на все продукты
        subscriptions = {}
        for product in PRODUCTS.keys():
            has_sub = check_subscription(user['id'], product)
            days = get_subscription_days(user['id'], product)
            subscriptions[product] = {'active': has_sub, 'days': days}
        
        conn.close()
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'is_admin': bool(user['is_admin']),
                'subscriptions': subscriptions
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/activate_key', methods=['POST'])
def activate_key():
    try:
        data = request.json
        key = data.get('key', '').strip().upper()
        user_id = data.get('user_id')
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, product, days, used_by FROM license_keys WHERE key = ?', (key,))
        key_data = cursor.fetchone()
        
        if not key_data:
            conn.close()
            return jsonify({'success': False, 'error': 'Неверный ключ'})
        
        if key_data['used_by']:
            conn.close()
            return jsonify({'success': False, 'error': 'Ключ уже использован'})
        
        # Активация ключа
        cursor.execute('''
            UPDATE license_keys 
            SET used_by = ?, used_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (user_id, key_data['id']))
        
        # Обновление подписки на продукт
        cursor.execute('''
            SELECT subscription_end FROM user_subscriptions 
            WHERE user_id = ? AND product = ?
        ''', (user_id, key_data['product']))
        
        current = cursor.fetchone()
        
        if current and current['subscription_end']:
            new_end = datetime.strptime(current['subscription_end'], '%Y-%m-%d') + timedelta(days=key_data['days'])
            cursor.execute('''
                UPDATE user_subscriptions 
                SET subscription_end = ? 
                WHERE user_id = ? AND product = ?
            ''', (new_end.date(), user_id, key_data['product']))
        else:
            new_end = datetime.now() + timedelta(days=key_data['days'])
            cursor.execute('''
                INSERT INTO user_subscriptions (user_id, product, subscription_end)
                VALUES (?, ?, ?)
            ''', (user_id, key_data['product'], new_end.date()))
        
        conn.commit()
        
        # Получаем обновленные подписки
        subscriptions = {}
        for product in PRODUCTS.keys():
            has_sub = check_subscription(user_id, product)
            days = get_subscription_days(user_id, product)
            subscriptions[product] = {'active': has_sub, 'days': days}
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Ключ активирован на {key_data["days"]} дней для {PRODUCTS[key_data["product"]]["name"]}',
            'subscriptions': subscriptions
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/create_key', methods=['POST'])
def create_key():
    try:
        data = request.json
        days = data.get('days', 30)
        product = data.get('product', 'gboost')
        created_by = data.get('created_by', 'admin')
        
        if product not in PRODUCTS:
            return jsonify({'success': False, 'error': 'Неверный продукт'})
        
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        key_formatted = f"{key[:4]}-{key[4:8]}-{key[8:12]}-{key[12:]}"
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO license_keys (key, product, days, created_by)
            VALUES (?, ?, ?, ?)
        ''', (key_formatted, product, days, created_by))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'key': key_formatted, 'days': days, 'product': product})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/give_subscription', methods=['POST'])
def give_subscription():
    try:
        data = request.json
        user_id = data.get('user_id')
        product = data.get('product', 'gboost')
        days = data.get('days', 30)
        
        if product not in PRODUCTS:
            return jsonify({'success': False, 'error': 'Неверный продукт'})
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT subscription_end FROM user_subscriptions 
            WHERE user_id = ? AND product = ?
        ''', (user_id, product))
        
        current = cursor.fetchone()
        
        if current and current['subscription_end']:
            new_end = datetime.strptime(current['subscription_end'], '%Y-%m-%d') + timedelta(days=days)
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
        
        return jsonify({'success': True, 'message': f'Подписка на {PRODUCTS[product]["name"]} выдана на {days} дней'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_user', methods=['POST'])
def get_user():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, is_admin FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'Пользователь не найден'})
        
        subscriptions = {}
        for product in PRODUCTS.keys():
            has_sub = check_subscription(user_id, product)
            days = get_subscription_days(user_id, product)
            subscriptions[product] = {'active': has_sub, 'days': days}
        
        conn.close()
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'is_admin': bool(user['is_admin']),
                'subscriptions': subscriptions
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/search_user', methods=['POST'])
def search_user():
    try:
        data = request.json
        search = data.get('search', '').strip()
        
        conn = get_db()
        cursor = conn.cursor()
        
        if search.isdigit():
            cursor.execute('SELECT id, username, hwid, created_at, is_admin FROM users WHERE id = ?', (int(search),))
        else:
            cursor.execute('SELECT id, username, hwid, created_at, is_admin FROM users WHERE username = ?', (search,))
        
        user = cursor.fetchone()
        
        if user:
            # Получаем подписки пользователя
            subscriptions = {}
            for product in PRODUCTS.keys():
                cursor.execute('SELECT subscription_end FROM user_subscriptions WHERE user_id = ? AND product = ?', (user['id'], product))
                sub = cursor.fetchone()
                subscriptions[product] = sub['subscription_end'] if sub else 'Нет'
            
            conn.close()
            return jsonify({
                'success': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'hwid': user['hwid'] or 'Не привязан',
                    'is_admin': bool(user['is_admin']),
                    'created_at': user['created_at'],
                    'subscriptions': subscriptions
                }
            })
        
        conn.close()
        return jsonify({'success': False, 'error': 'Пользователь не найден'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_all_users', methods=['POST'])
def get_all_users():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username FROM users ORDER BY id')
        users = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'users': [{'id': u['id'], 'username': u['username']} for u in users]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_all_keys', methods=['POST'])
def get_all_keys():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, key, product, days, used_by, used_at, created_by, created_at 
            FROM license_keys 
            ORDER BY created_at DESC
        ''')
        keys = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'keys': [{
                'id': k['id'],
                'key': k['key'],
                'product': k['product'],
                'product_name': PRODUCTS[k['product']]['name'],
                'days': k['days'],
                'used_by': k['used_by'],
                'used_at': k['used_at'],
                'created_by': k['created_by'],
                'created_at': k['created_at']
            } for k in keys]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reset_hwid', methods=['POST'])
def reset_hwid():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET hwid = NULL WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reset_password', methods=['POST'])
def reset_password():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        new_password = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        hashed_pass = hashlib.sha256(new_password.encode()).hexdigest()
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_pass, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'new_password': new_password})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
@app.route('/api/remove_admin', methods=['POST'])
def remove_admin():
    """Снятие прав администратора (только для супер админа)"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        # Нельзя снять права с главного админа (ID=1)
        if user_id == 1:
            return jsonify({'success': False, 'error': 'Нельзя снять права с главного администратора'})
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = 0 WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
@app.route('/api/make_admin', methods=['POST'])
def make_admin():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/check', methods=['GET'])
def check():
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat(), 'products': PRODUCTS})

if __name__ == '__main__':
    # Render задает порт через переменную окружения PORT
    # Если переменной нет (локально), используем 5000
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 50)
    print("🚀 GLauncher Server запущен!")
    print("=" * 50)
    print(f"📁 База данных: {DB_PATH}")
    print(f"👑 Админ: admin / admin123")
    print(f"🧪 Тест: test / test123")
    print(f"🌐 Порт: {port}")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=port, debug=False)