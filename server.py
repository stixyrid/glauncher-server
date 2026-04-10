import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from database import Database
from datetime import datetime
import hashlib

app = Flask(__name__)
CORS(app)

db = Database()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_subscription(user_id, product):
    """Проверка активной подписки"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT subscription_end FROM user_subscriptions 
        WHERE user_id = ? AND product = ?
    ''', (user_id, product))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0]:
        from datetime import datetime
        sub_end = datetime.strptime(result[0], '%Y-%m-%d')
        return sub_end > datetime.now()
    return False

def get_subscription_days(user_id, product):
    """Получение дней подписки"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT subscription_end FROM user_subscriptions 
        WHERE user_id = ? AND product = ?
    ''', (user_id, product))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0]:
        from datetime import datetime
        sub_end = datetime.strptime(result[0], '%Y-%m-%d')
        days_left = (sub_end - datetime.now()).days
        return max(0, days_left)
    return 0

def get_user_subscriptions(user_id):
    """Получение всех подписок пользователя"""
    products = ['gboost', 'ghelper', 'gtrigger']
    subs = {}
    for product in products:
        subs[product] = {
            'active': check_subscription(user_id, product),
            'days': get_subscription_days(user_id, product)
        }
    return subs

# ==================== ПУБЛИЧНЫЕ ЭНДПОИНТЫ ====================

@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'message': 'GLauncher API Server is running',
        'version': '1.0.0',
        'time': datetime.now().isoformat()
    })

@app.route('/api/check', methods=['GET'])
def check():
    return jsonify({
        'status': 'ok',
        'time': datetime.now().isoformat(),
        'products': {
            'gboost': {'name': 'G BOOST', 'exe': 'G_BOOST.exe', 'color': '#00ff00'},
            'ghelper': {'name': 'G HELPER', 'exe': 'G_Helper.exe', 'color': '#ffaa00'},
            'gtrigger': {'name': 'G TRIGGER', 'exe': 'G_Trigger.exe', 'color': '#ff4444'}
        }
    })

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
        
        success = db.register_user(username, password, hwid)
        
        if success:
            return jsonify({'success': True, 'message': 'Регистрация успешна'})
        else:
            return jsonify({'success': False, 'error': 'Пользователь уже существует'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        hwid = data.get('hwid', '').strip()
        
        # Получаем пользователя из БД
        conn = db.get_connection()
        cursor = conn.cursor()
        
        hashed_pass = hash_password(password)
        cursor.execute('''
            SELECT id, username, hwid, is_admin 
            FROM users 
            WHERE username = ? AND password = ?
        ''', (username, hashed_pass))
        
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'Неверное имя пользователя или пароль'})
        
        # Проверка HWID
        if user[2] and user[2] != hwid:
            return jsonify({'success': False, 'error': 'HWID не совпадает'})
        
        # Обновляем HWID если не привязан
        if not user[2]:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET hwid = ? WHERE id = ?', (hwid, user[0]))
            conn.commit()
            conn.close()
        
        # Получаем подписки
        subscriptions = get_user_subscriptions(user[0])
        
        return jsonify({
            'success': True,
            'user': {
                'id': user[0],
                'username': user[1],
                'is_admin': bool(user[3]),
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
        
        success = db.activate_key(key, user_id, 30)
        
        if success:
            subscriptions = get_user_subscriptions(user_id)
            return jsonify({
                'success': True,
                'message': 'Ключ активирован!',
                'subscriptions': subscriptions
            })
        else:
            return jsonify({'success': False, 'error': 'Неверный или уже использованный ключ'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_user', methods=['POST'])
def get_user():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, is_admin FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'Пользователь не найден'})
        
        subscriptions = get_user_subscriptions(user_id)
        
        return jsonify({
            'success': True,
            'user': {
                'id': user[0],
                'username': user[1],
                'is_admin': bool(user[2]),
                'subscriptions': subscriptions
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== АДМИН ЭНДПОИНТЫ ====================

@app.route('/api/get_all_users', methods=['POST'])
def get_all_users():
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username FROM users ORDER BY id')
        users = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'users': [{'id': u[0], 'username': u[1]} for u in users]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_all_keys', methods=['POST'])
def get_all_keys():
    try:
        keys = db.get_all_keys()
        return jsonify({'success': True, 'keys': keys})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/search_user', methods=['POST'])
def search_user():
    try:
        data = request.json
        search = data.get('search', '').strip()
        
        if search.isdigit():
            user = db.get_user_by_id(int(search))
        else:
            user = db.get_user_by_username(search)
        
        if user:
            return jsonify({'success': True, 'user': user})
        return jsonify({'success': False, 'error': 'Пользователь не найден'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/create_key', methods=['POST'])
def create_key():
    try:
        data = request.json
        days = data.get('days', 30)
        product = data.get('product', 'gboost')
        created_by = data.get('created_by', 'admin')
        
        key = db.create_key(days, product, created_by)
        
        return jsonify({'success': True, 'key': key, 'days': days, 'product': product})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/give_subscription', methods=['POST'])
def give_subscription():
    try:
        data = request.json
        user_id = data.get('user_id')
        product = data.get('product', 'gboost')
        days = data.get('days', 30)
        
        success = db.extend_subscription(user_id, product, days)
        
        if success:
            return jsonify({'success': True, 'message': f'Подписка выдана на {days} дней'})
        return jsonify({'success': False, 'error': 'Ошибка выдачи подписки'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reset_hwid', methods=['POST'])
def reset_hwid():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        conn = db.get_connection()
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
        
        import random
        import string
        new_password = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        hashed_pass = hash_password(new_password)
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_pass, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'new_password': new_password})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/make_admin', methods=['POST'])
def make_admin():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remove_admin', methods=['POST'])
def remove_admin():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if user_id == 1:
            return jsonify({'success': False, 'error': 'Нельзя снять права с главного администратора'})
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = 0 WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== ЗАПУСК СЕРВЕРА ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 50)
    print("🚀 GLauncher Server запущен!")
    print("=" * 50)
    print(f"🌐 Порт: {port}")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=port, debug=False)