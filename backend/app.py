import os
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import jwt
import datetime
from functools import wraps

app = Flask(__name__, static_folder='..', static_url_path='')
CORS(app)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'CHANGE_ME_TO_RANDOM_SECRET')

# Папка для загруженных изображений
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'img', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'jewelry_db',
    'user': 'jewelry_app',
    'password': 'jewelry_pass'
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            price NUMERIC(10,2) NOT NULL,
            description TEXT,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        );
    ''')
    # Миграция: добавляем колонку role, если таблица уже существовала без неё
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='admins' AND column_name='role'
    """)
    if not cur.fetchone():
        cur.execute("ALTER TABLE admins ADD COLUMN role TEXT DEFAULT 'user'")
    # Создаём админа по умолчанию, только если его ещё нет
    cur.execute("SELECT id FROM admins WHERE username = %s", ('admin',))
    if not cur.fetchone():
        pw = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode('utf-8')
        cur.execute(
            "INSERT INTO admins (username, password_hash, role) VALUES (%s, %s, 'admin')",
            ('admin', pw)
        )
        print("Создан админ по умолчанию: логин admin, пароль admin123 — СМЕНИТЕ ПАРОЛЬ!")
    else:
        # Гарантированно выставим роль admin существующему админу
        cur.execute("UPDATE admins SET role = 'admin' WHERE username = %s", ('admin',))
    conn.commit()

    # Заполняем товары из главной страницы, если таблица пуста
    cur.execute("SELECT COUNT(*) FROM products")
    product_count = cur.fetchone()[0]
    if product_count == 0:
        seed_products = [
            ('Кольцо «Тень»', 18000, 'Элегантное кольцо с чёрным камнем огранки «кабошон»', 'img/item1.jpg'),
            ('Серьги «Ольха»', 24000, 'Серьги с текстурой коры ольхи и жемчугом', 'img/item2.jpg'),
            ('Подвеска «Ноль»', 0, 'Минималистичная подвеска-кольцо с серпом в центре', 'img/item3.jpg'),
            ('Кольцо «Линия»', 16500, 'Гладкое кольцо с тонкой гравировкой по ободку', 'img/item4.jpg'),
            ('Серьги «Капля»', 21000, 'Серьги в форме капли из белого золота', 'img/item5.jpg'),
            ('Цепь «Тишина»', 32000, 'Длинная тонкая цепь на шею, элегантная и изящная', 'img/item6.jpg'),
        ]
        for name, price, description, image_url in seed_products:
            cur.execute(
                "INSERT INTO products (name, price, description, image_url) VALUES (%s, %s, %s, %s)",
                (name, price, description, image_url)
            )
        print(f"Загружено {len(seed_products)} товаров из главной страницы")
    conn.commit()
    cur.close()
    conn.close()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]
        if not token:
            return jsonify({'error': 'Токен не предоставлен'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.current_user = data['username']
            request.current_user_role = data.get('role', 'user')
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Токен истёк'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Неверный токен'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]
        if not token:
            return jsonify({'error': 'Токен не предоставлен'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.current_user = data['username']
            request.current_user_role = data.get('role', 'user')
            if data.get('role') != 'admin':
                return jsonify({'error': 'Доступ запрещен: нужны права администратора'}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Токен истёк'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Неверный токен'}), 401
        return f(*args, **kwargs)
    return decorated

# ==================== СТАТИКА (фронтенд) ====================

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('..', 'favicon.svg'), 200, {'Content-Type': 'image/svg+xml'}

# Раздача загруженных изображений
@app.route('/img/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'brilliant-jewelry-api'})

@app.route('/')
def index():
    return send_from_directory('..', 'index.html')

@app.route('/admin.html')
def admin_page():
    return send_from_directory('..', 'admin.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('..', filename)

# ==================== API: ПУБЛИЧНЫЕ ТОВАРЫ (каталог) ====================

@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, name, price, description, image_url, created_at FROM products ORDER BY created_at DESC")
    products = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(products)

# ==================== API: АДМИНКА ====================

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '')
    password = data.get('password', '')

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, username, password_hash, role FROM admins WHERE username = %s", (username,))
    admin = cur.fetchone()
    cur.close()
    conn.close()

    if admin and bcrypt.checkpw(password.encode('utf-8'), admin['password_hash'].encode('utf-8')):
        token = jwt.encode({
            'username': admin['username'],
            'role': admin.get('role', 'admin'),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({'token': token, 'username': admin['username'], 'role': admin.get('role', 'admin')})
    return jsonify({'error': 'Неверный логин или пароль'}), 401

@app.route('/api/admin/register', methods=['POST'])
def admin_register():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not username:
        return jsonify({'error': 'Логин обязателен'}), 400
    if not password:
        return jsonify({'error': 'Пароль обязателен'}), 400
    if password != confirm_password:
        return jsonify({'error': 'Пароли не совпадают'}), 400

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id FROM admins WHERE username = %s", (username,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({'error': 'Пользователь с таким логином уже существует'}), 400

    pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cur.execute(
        "INSERT INTO admins (username, password_hash, role) VALUES (%s, %s, 'user') RETURNING id",
        (username, pw)
    )
    row = cur.fetchone()
    new_id = row['id'] if isinstance(row, dict) else row[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'id': new_id, 'message': 'Аккаунт успешно создан'}), 201

@app.route('/api/admin/products', methods=['GET'])
@admin_required
def admin_get_products():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, name, price, description, image_url, created_at FROM products ORDER BY created_at DESC")
    products = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(products)

@app.route('/api/admin/products/<int:product_id>', methods=['GET'])
@admin_required
def admin_get_product(product_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, name, price, description, image_url, created_at FROM products WHERE id = %s", (product_id,))
    product = cur.fetchone()
    cur.close()
    conn.close()
    if not product:
        return jsonify({'error': 'Товар не найден'}), 404
    return jsonify(product)

@app.route('/api/admin/products', methods=['POST'])
@admin_required
def admin_add_product():
    name = request.form.get('name', '').strip()
    price = request.form.get('price')
    description = request.form.get('description', '').strip()

    if not name:
        return jsonify({'error': 'Название обязательно'}), 400
    try:
        price = float(price)
    except (TypeError, ValueError):
        return jsonify({'error': 'Некорректная цена'}), 400

    image_url = ''
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Добавляем уникальность к имени файла
            name_part, ext = os.path.splitext(filename)
            filename = f"{name_part}_{int(time.time())}{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_url = '/img/uploads/' + filename

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO products (name, price, description, image_url) VALUES (%s, %s, %s, %s) RETURNING id",
        (name, price, description, image_url)
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'id': new_id, 'message': 'Товар добавлен', 'image_url': image_url}), 201

@app.route('/api/admin/products/<int:product_id>', methods=['PUT'])
@admin_required
def admin_update_product(product_id):
    name = request.form.get('name', '').strip()
    price = request.form.get('price')
    description = request.form.get('description', '').strip()

    if not name:
        return jsonify({'error': 'Название обязательно'}), 400
    try:
        price = float(price)
    except (TypeError, ValueError):
        return jsonify({'error': 'Некорректная цена'}), 400

    conn = get_db()
    # Получаем текущий URL изображения, если не загружено новое
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT image_url FROM products WHERE id = %s", (product_id,))
    existing = cur.fetchone()
    if not existing:
        cur.close()
        conn.close()
        return jsonify({'error': 'Товар не найден'}), 404
    image_url = existing['image_url'] or ''

    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            name_part, ext = os.path.splitext(filename)
            filename = f"{name_part}_{int(time.time())}{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_url = '/img/uploads/' + filename

    cur = conn.cursor()
    cur.execute(
        "UPDATE products SET name = %s, price = %s, description = %s, image_url = %s WHERE id = %s",
        (name, price, description, image_url, product_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'message': 'Товар обновлён', 'image_url': image_url})

@app.route('/api/admin/products/<int:product_id>', methods=['DELETE'])
@admin_required
def admin_delete_product(product_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
    if cur.rowcount == 0:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({'error': 'Товар не найден'}), 404
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'message': 'Товар удалён'})

if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=True)