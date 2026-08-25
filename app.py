from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import sqlite3
import hashlib
import re
import smtplib
import random
from datetime import datetime, timedelta
import time
from functools import wraps
import json
from email.mime.text import MIMEText
import requests

app = Flask(__name__)
app.secret_key = 'MRX_ULTRA_SECRET_2026'
CORS(app)

# ===== إعدادات البريد =====
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "your_email@gmail.com"  # غيّر لبريدك
SMTP_PASS = "your_app_password"     # غيّر لكلمة مرور التطبيق

def send_verification_email(to_email, code):
    try:
        msg = MIMEText(f"رمز التحقق: {code}\nصلاحية 5 دقائق.")
        msg['Subject'] = 'رمز تحقق MRX'
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except:
        return False

# ===== قاعدة البيانات =====
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        username TEXT,
        password TEXT,
        profile_pic TEXT,
        verified BOOLEAN DEFAULT 0,
        banned BOOLEAN DEFAULT 0,
        ban_until TEXT,
        messages INTEGER DEFAULT 0,
        uploads INTEGER DEFAULT 0,
        online BOOLEAN DEFAULT 0,
        bio TEXT DEFAULT '',
        theme TEXT DEFAULT 'dark',
        lang TEXT DEFAULT 'ar',
        bubble_style TEXT DEFAULT 'normal'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS scripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        map TEXT,
        code TEXT,
        hash TEXT UNIQUE,
        is_malicious BOOLEAN DEFAULT 0,
        upload_time TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        timestamp TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS verification_codes (
        email TEXT PRIMARY KEY,
        code TEXT,
        expiry TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS news_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        content TEXT,
        image_url TEXT,
        timestamp TEXT,
        FOREIGN KEY(admin_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS reactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user_id INTEGER,
        emoji TEXT,
        UNIQUE(post_id, user_id),
        FOREIGN KEY(post_id) REFERENCES news_posts(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    # إضافة المسؤول
    c.execute("SELECT * FROM users WHERE email = 'ryadsadq806@gmail.com'")
    if not c.fetchone():
        c.execute("INSERT INTO users (email, username, profile_pic, verified, bio) VALUES (?, ?, ?, ?, ?)",
                  ('ryadsadq806@gmail.com', 'MRX', '/static/default.png', 1, 'المالك والمطور'))
    conn.commit()
    conn.close()

init_db()

# ===== دوال مساعدة =====
def get_user_by_email(email):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def update_user_field(user_id, field, value):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute(f"UPDATE users SET {field} = ? WHERE id = ?", (value, user_id))
    conn.commit()
    conn.close()

def is_script_safe(code):
    suspicious = [
        r'requests\.(get|post|put|delete)',
        r'urllib\.request',
        r'socket\.',
        r'os\.system',
        r'subprocess\.',
        r'eval\(',
        r'exec\(',
        r'__import__',
        r'base64\.b64decode',
        r'cryptography',
        r'pynput',
        r'smtplib'
    ]
    for pattern in suspicious:
        if re.search(pattern, code, re.IGNORECASE):
            return False
    return True

def get_script_hash(code):
    return hashlib.sha256(code.encode()).hexdigest()

# ===== الجدار الناري وحماية DDoS (معدل طلبات + فلتر) =====
request_counts = {}
BLOCKED_IPS = {}

def firewall_check():
    """فلترة الطلبات المشبوهة (DDoS)"""
    ip = request.remote_addr
    # حماية من الطلبات المتكررة جداً
    now = time.time()
    if ip in BLOCKED_IPS and BLOCKED_IPS[ip] > now:
        return True
    return False

def rate_limit(limit=5, per=10):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if firewall_check():
                return jsonify({'error': 'Blocked by firewall'}), 403
            ip = request.remote_addr
            now = time.time()
            if ip not in request_counts:
                request_counts[ip] = []
            request_counts[ip] = [t for t in request_counts[ip] if now - t < per]
            if len(request_counts[ip]) >= limit:
                # حظر مؤقت 60 ثانية
                BLOCKED_IPS[ip] = now + 60
                return jsonify({'error': 'Too many requests. Blocked.'}), 429
            request_counts[ip].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator

# بروكسي مدمج (VPN داخلي) لتصفح المواقع بشكل مجهول
@app.route('/api/proxy', methods=['GET'])
@rate_limit(limit=15, per=30)
def proxy_request():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Missing URL'}), 400
    try:
        resp = requests.get(url, timeout=5, headers={'User-Agent': 'MRX-Proxy/1.0'})
        return resp.content, resp.status_code
    except:
        return jsonify({'error': 'Proxy failed'}), 500

# ===== API =====

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

# طلب رمز التحقق
@app.route('/api/send_verification', methods=['POST'])
@rate_limit(limit=3, per=60)
def send_verification():
    data = request.json
    email = data.get('email', '').strip()
    if not re.match(r'^[a-zA-Z0-9._%+-]+@gmail\.com$', email):
        return jsonify({'error': 'بريد Gmail صحيح مطلوب'}), 400
    code = str(random.randint(100000, 999999))
    expiry = (datetime.now() + timedelta(minutes=5)).isoformat()
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("REPLACE INTO verification_codes (email, code, expiry) VALUES (?, ?, ?)", (email, code, expiry))
    conn.commit()
    conn.close()
    if send_verification_email(email, code):
        return jsonify({'success': True})
    return jsonify({'error': 'فشل إرسال البريد'}), 500

@app.route('/api/verify_login', methods=['POST'])
@rate_limit(limit=5, per=30)
def verify_login():
    data = request.json
    email = data.get('email', '').strip()
    code = data.get('code', '').strip()
    username = data.get('username', '').strip()
    if not email or not code or not username:
        return jsonify({'error': 'املأ الحقول'}), 400
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT code, expiry FROM verification_codes WHERE email = ?", (email,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'لم يتم طلب رمز'}), 400
    stored_code, expiry = row
    if datetime.fromisoformat(expiry) < datetime.now():
        conn.close()
        return jsonify({'error': 'انتهت الصلاحية'}), 400
    if code != stored_code:
        conn.close()
        return jsonify({'error': 'رمز خاطئ'}), 400
    c.execute("DELETE FROM verification_codes WHERE email = ?", (email,))
    conn.commit()
    user = get_user_by_email(email)
    if user:
        update_user_field(user[0], 'username', username)
        update_user_field(user[0], 'online', 1)
        session['user_id'] = user[0]
        conn.close()
        return jsonify({'success': True, 'user': {'id': user[0], 'email': user[1], 'username': user[2], 'profile_pic': user[4], 'verified': user[5], 'banned': user[6], 'ban_until': user[7], 'bio': user[11], 'theme': user[12], 'lang': user[13], 'bubble_style': user[14]}})
    else:
        c.execute("INSERT INTO users (email, username, profile_pic, online) VALUES (?, ?, ?, ?)",
                  (email, username, '/static/default.png', 1))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        session['user_id'] = user_id
        return jsonify({'success': True, 'user': {'id': user_id, 'email': email, 'username': username, 'profile_pic': '/static/default.png', 'verified': 0, 'banned': 0, 'ban_until': None, 'bio': '', 'theme': 'dark', 'lang': 'ar', 'bubble_style': 'normal'}})

# رفع الصورة
@app.route('/api/upload_profile', methods=['POST'])
@rate_limit(limit=5, per=60)
def upload_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'غير مسجل'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'لا يوجد ملف'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'اختر ملف'}), 400
    if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in {'png','jpg','jpeg','gif'}:
        ext = file.filename.rsplit('.', 1)[1]
        new_filename = f"{session['user_id']}.{ext}"
        os.makedirs('profiles', exist_ok=True)
        filepath = os.path.join('profiles', new_filename)
        file.save(filepath)
        profile_url = f"/profiles/{new_filename}"
        update_user_field(session['user_id'], 'profile_pic', profile_url)
        return jsonify({'success': True, 'profile_url': profile_url})
    return jsonify({'error': 'صيغة غير مدعومة'}), 400

# ===== إعدادات المستخدم (تحديث) =====
@app.route('/api/user/settings', methods=['PUT'])
@rate_limit(limit=10, per=30)
def update_settings():
    if 'user_id' not in session:
        return jsonify({'error': 'غير مسجل'}), 401
    data = request.json
    username = data.get('username')
    bio = data.get('bio')
    theme = data.get('theme')
    lang = data.get('lang')
    bubble_style = data.get('bubble_style')
    user_id = session['user_id']
    if username:
        update_user_field(user_id, 'username', username)
    if bio is not None:
        update_user_field(user_id, 'bio', bio)
    if theme in ['dark', 'white', 'red']:
        update_user_field(user_id, 'theme', theme)
    if lang in ['ar', 'en']:
        update_user_field(user_id, 'lang', lang)
    if bubble_style in ['normal', 'tiktok', 'hacker', 'red_square']:
        update_user_field(user_id, 'bubble_style', bubble_style)
    return jsonify({'success': True})

# ===== الشات العام =====
@app.route('/api/chat', methods=['GET'])
@rate_limit(limit=20, per=10)
def get_chat():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT chat.id, chat.user_id, users.username, users.profile_pic, users.verified, chat.message, chat.timestamp 
                 FROM chat JOIN users ON chat.user_id = users.id 
                 ORDER BY chat.id DESC LIMIT 50''')
    msgs = c.fetchall()
    conn.close()
    return jsonify(msgs[::-1])

@app.route('/api/chat', methods=['POST'])
@rate_limit(limit=3, per=5)
def send_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'غير مسجل'}), 401
    user = get_user_by_id(session['user_id'])
    if not user or user[6] == 1:
        return jsonify({'error': 'ممنوع'}), 403
    data = request.json
    msg = data.get('message', '').strip()
    if not msg or len(msg) > 500:
        return jsonify({'error': 'رسالة غير صالحة'}), 400
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO chat (user_id, message, timestamp) VALUES (?, ?, ?)",
              (session['user_id'], msg, datetime.now().isoformat()))
    c.execute("UPDATE users SET messages = messages + 1 WHERE id = ?", (session['user_id'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ===== السكربتات =====
@app.route('/api/scripts', methods=['GET'])
def get_scripts():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, title, map, code, is_malicious, user_id, upload_time FROM scripts")
    all_scripts = c.fetchall()
    conn.close()
    return jsonify([{'id': s[0], 'title': s[1], 'map': s[2], 'code': s[3], 'malicious': s[4], 'user_id': s[5], 'time': s[6]} for s in all_scripts])

@app.route('/api/script', methods=['POST'])
@rate_limit(limit=5, per=60)
def add_script():
    if 'user_id' not in session:
        return jsonify({'error': 'غير مسجل'}), 401
    user = get_user_by_id(session['user_id'])
    if user[6] == 1:
        return jsonify({'error': 'ممنوع'}), 403
    data = request.json
    title = data.get('title', '').strip()
    code = data.get('code', '').strip()
    map_name = data.get('map', '').strip()
    if not title or not code or not map_name:
        return jsonify({'error': 'املأ الحقول'}), 400
    code_hash = get_script_hash(code)
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM scripts WHERE hash = ?", (code_hash,))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'مكرر'}), 400
    malicious = 0 if is_script_safe(code) else 1
    c.execute("INSERT INTO scripts (user_id, title, map, code, hash, is_malicious, upload_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (session['user_id'], title, map_name, code, code_hash, malicious, datetime.now().isoformat()))
    c.execute("UPDATE users SET uploads = uploads + 1 WHERE id = ?", (session['user_id'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'malicious': malicious})

@app.route('/api/script/<int:script_id>', methods=['PUT'])
@rate_limit(limit=5, per=60)
def edit_script(script_id):
    if 'user_id' not in session:
        return jsonify({'error': 'غير مسجل'}), 401
    data = request.json
    new_code = data.get('code', '').strip()
    if not new_code:
        return jsonify({'error': 'فارغ'}), 400
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM scripts WHERE id = ?", (script_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'غير موجود'}), 404
    admin = get_user_by_email('ryadsadq806@gmail.com')
    if row[0] != session['user_id'] and (not admin or session['user_id'] != admin[0]):
        conn.close()
        return jsonify({'error': 'لا صلاحية'}), 403
    new_hash = get_script_hash(new_code)
    malicious = 0 if is_script_safe(new_code) else 1
    c.execute("UPDATE scripts SET code = ?, hash = ?, is_malicious = ? WHERE id = ?",
              (new_code, new_hash, malicious, script_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'malicious': malicious})

# ===== أخبار الموقع (تفاعل تيليجرام + إيموجيز) =====
@app.route('/api/news', methods=['GET'])
@rate_limit(limit=20, per=10)
def get_news():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT news_posts.id, news_posts.admin_id, users.username, users.profile_pic, news_posts.content, news_posts.image_url, news_posts.timestamp 
                 FROM news_posts JOIN users ON news_posts.admin_id = users.id 
                 ORDER BY news_posts.id DESC LIMIT 50''')
    posts = c.fetchall()
    result = []
    for p in posts:
        # جلب الريأكشنز
        c.execute("SELECT emoji, COUNT(*) FROM reactions WHERE post_id = ? GROUP BY emoji", (p[0],))
        reactions = {row[0]: row[1] for row in c.fetchall()}
        # هل تفاعل المستخدم الحالي؟
        user_react = None
        if 'user_id' in session:
            c.execute("SELECT emoji FROM reactions WHERE post_id = ? AND user_id = ?", (p[0], session['user_id']))
            row = c.fetchone()
            if row:
                user_react = row[0]
        result.append({
            'id': p[0],
            'admin_id': p[1],
            'username': p[2],
            'profile_pic': p[3],
            'content': p[4],
            'image_url': p[5],
            'timestamp': p[6],
            'reactions': reactions,
            'user_reaction': user_react
        })
    conn.close()
    return jsonify(result)

@app.route('/api/news', methods=['POST'])
@rate_limit(limit=5, per=60)
def create_news():
    if 'user_id' not in session:
        return jsonify({'error': 'غير مسجل'}), 401
    user = get_user_by_id(session['user_id'])
    if user[1] != 'ryadsadq806@gmail.com':
        return jsonify({'error': 'المسؤول فقط'}), 403
    data = request.json
    content = data.get('content', '').strip()
    image_url = data.get('image_url', '').strip()
    if not content and not image_url:
        return jsonify({'error': 'محتوى أو صورة مطلوب'}), 400
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO news_posts (admin_id, content, image_url, timestamp) VALUES (?, ?, ?, ?)",
              (session['user_id'], content, image_url, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/reaction', methods=['POST'])
@rate_limit(limit=10, per=30)
def toggle_reaction():
    if 'user_id' not in session:
        return jsonify({'error': 'غير مسجل'}), 401
    data = request.json
    post_id = data.get('post_id')
    emoji = data.get('emoji')
    if not post_id or not emoji:
        return jsonify({'error': 'بيانات ناقصة'}), 400
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # إذا كان المستخدم قد تفاعل بالفعل بنفس الإيموجي -> إزالة
    c.execute("SELECT id FROM reactions WHERE post_id = ? AND user_id = ? AND emoji = ?", (post_id, user_id, emoji))
    existing = c.fetchone()
    if existing:
        c.execute("DELETE FROM reactions WHERE post_id = ? AND user_id = ? AND emoji = ?", (post_id, user_id, emoji))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'action': 'removed'})
    # إذا كان تفاعل مختلف -> استبدال
    c.execute("SELECT id FROM reactions WHERE post_id = ? AND user_id = ?", (post_id, user_id))
    old = c.fetchone()
    if old:
        c.execute("DELETE FROM reactions WHERE post_id = ? AND user_id = ?", (post_id, user_id))
    c.execute("INSERT INTO reactions (post_id, user_id, emoji) VALUES (?, ?, ?)", (post_id, user_id, emoji))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'action': 'added'})

# ===== لوحة التحكم (للمسؤول) =====
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل'}), 401
        user = get_user_by_id(session['user_id'])
        if user[1] != 'ryadsadq806@gmail.com':
            return jsonify({'error': 'صلاحية المسؤول'}), 403
        return f(*args, **kwargs)
    return decorated

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_users():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, email, username, profile_pic, verified, banned, ban_until, messages, uploads, online, bio, theme, lang, bubble_style FROM users")
    users = c.fetchall()
    conn.close()
    return jsonify([{
        'id': u[0], 'email': u[1], 'username': u[2], 'profile_pic': u[3],
        'verified': u[4], 'banned': u[5], 'ban_until': u[6],
        'messages': u[7], 'uploads': u[8], 'online': u[9],
        'bio': u[10], 'theme': u[11], 'lang': u[12], 'bubble_style': u[13]
    } for u in users])

@app.route('/api/admin/verify', methods=['POST'])
@admin_required
def admin_verify():
    data = request.json
    user_id = data.get('user_id')
    action = data.get('action')
    if not user_id:
        return jsonify({'error': 'مطلوب'}), 400
    if action == 'add':
        update_user_field(user_id, 'verified', 1)
    elif action == 'remove':
        update_user_field(user_id, 'verified', 0)
    else:
        return jsonify({'error': 'إجراء خاطئ'}), 400
    return jsonify({'success': True})

@app.route('/api/admin/ban', methods=['POST'])
@admin_required
def admin_ban():
    data = request.json
    user_id = data.get('user_id')
    duration = data.get('duration')
    if not user_id:
        return jsonify({'error': 'مطلوب'}), 400
    if duration == 'permanent':
        update_user_field(user_id, 'banned', 1)
        update_user_field(user_id, 'ban_until', None)
    elif duration == 'temp':
        until = (datetime.now() + timedelta(days=7)).isoformat()
        update_user_field(user_id, 'banned', 1)
        update_user_field(user_id, 'ban_until', until)
    else:
        return jsonify({'error': 'مدة خاطئة'}), 400
    return jsonify({'success': True})

@app.route('/api/admin/unban', methods=['POST'])
@admin_required
def admin_unban():
    data = request.json
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'مطلوب'}), 400
    update_user_field(user_id, 'banned', 0)
    update_user_field(user_id, 'ban_until', None)
    return jsonify({'success': True})

@app.route('/api/top_users', methods=['GET'])
@rate_limit(limit=10, per=30)
def top_users():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, username, profile_pic, verified, messages, uploads, online FROM users ORDER BY (messages + uploads) DESC LIMIT 10")
    top = c.fetchall()
    conn.close()
    return jsonify([{'id': t[0], 'username': t[1], 'profile_pic': t[2], 'verified': t[3], 'messages': t[4], 'uploads': t[5], 'online': t[6]} for t in top])

# ===== أداة التشفير (30 لغة) =====
LANGUAGES = {
    'Lua': 'lua', 'Python': 'py', 'JavaScript': 'js', 'HTML': 'html',
    'CSS': 'css', 'Java': 'java', 'C++': 'cpp', 'C#': 'cs', 'PHP': 'php',
    'Ruby': 'rb', 'Go': 'go', 'Rust': 'rs', 'Swift': 'swift', 'Kotlin': 'kt',
    'TypeScript': 'ts', 'SQL': 'sql', 'Shell': 'sh', 'Perl': 'pl', 'R': 'r',
    'Scala': 'scala', 'Haskell': 'hs', 'Elixir': 'ex', 'Dart': 'dart',
    'Objective-C': 'm', 'VBA': 'vba', 'Groovy': 'groovy', 'PowerShell': 'ps1',
    'Julia': 'jl', 'Clojure': 'clj', 'Erlang': 'erl'
}

@app.route('/api/encode', methods=['POST'])
@rate_limit(limit=10, per=60)
def encode_script():
    data = request.json
    language = data.get('language', '').strip()
    raw = data.get('code', '').strip()
    if not language or not raw:
        return jsonify({'error': 'اللغة والكود مطلوبان'}), 400
    if language not in LANGUAGES:
        return jsonify({'error': 'لغة غير مدعومة'}), 400
    b64 = hashlib.sha256(raw.encode()).hexdigest()[:16]
    fake_url = f"https://mrx-store.net/scripts/{b64}.{LANGUAGES[language]}"
    encoded = f"// تشفير MRX - {language}\n// {fake_url}\n{raw}"
    return jsonify({'encoded': encoded, 'url': fake_url})

if __name__ == '__main__':
    os.makedirs('profiles', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
