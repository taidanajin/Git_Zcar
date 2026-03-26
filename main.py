from flask import Flask, render_template, request, redirect, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import requests
import os
import threading
import time
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///main.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Telegram Bot Configuration
app.config['TELEGRAM_BOT_TOKEN'] = os.environ.get('TELEGRAM_BOT_TOKEN', '8761314269:AAHhIBVTrOeCFrqjatzt-RhsXzk4SWsCcJQ')
app.config['TELEGRAM_CHAT_ID'] = os.environ.get('TELEGRAM_CHAT_ID', '-3261646428')

db = SQLAlchemy(app)
manager = LoginManager(app)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True)
    password = db.Column(db.String)
    admin = db.Column(db.Boolean, default=False)

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def __str__(self):
        return f"ID: {self.id}, Логин: {self.username}"

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    telegram_message_id = db.Column(db.Integer, unique=True, nullable=True)
    
    def __repr__(self):
        return f"<Announcement {self.title}>"

@manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


@app.route('/')
def index():
    try:
        result = render_template("index.html")
        if not result:
            return "<h1>ERROR: render_template returned empty!</h1>"
        return result
    except Exception as e:
        import traceback
        return f"<h1>Error rendering index.html:</h1><pre>{traceback.format_exc()}</pre>"

@app.route('/direct-check')
def direct_check():
    return "<h1>Direct HTML Works!</h1><p>Flask is working, templates might have issues.</p>"

@app.route('/test-page')
def demo_page():
    return render_template("test_index.html")

@app.route('/simple')
def simple():
    return render_template("index_simple.html")

@app.route('/obj')
@app.route('/obj/<int:page>')
def obj(page=1):
    per_page = 10  # Количество объявлений на странице
    
    # Получаем параметры фильтрации
    search_query = request.args.get('search', '')
    
    # Базовый запрос
    query = Announcement.query
    
    # Применяем поиск если есть
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Announcement.title.ilike(search_pattern),
                Announcement.content.ilike(search_pattern)
            )
        )
    
    # Сортировка и пагинация
    pagination = query.order_by(Announcement.date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    announcements = pagination.items
    
    return render_template("obj.html", 
                         announcements=announcements,
                         pagination=pagination,
                         page=page,
                         search_query=search_query)

@app.route('/sync-telegram', methods=['POST'])
@login_required
def sync_telegram():
    """Синхронизация сообщений из Telegram канала"""
    if not current_user.admin:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    bot_token = app.config['TELEGRAM_BOT_TOKEN']
    chat_id = app.config['TELEGRAM_CHAT_ID']
    
    if not bot_token:
        return jsonify({'error': 'Telegram Bot Token не настроен'}), 400
    
    try:
        # Получаем последние сообщения из канала
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if not data.get('ok'):
            return jsonify({'error': 'Ошибка API Telegram'}), 400
        
        new_count = 0
        for update in data.get('result', []):
            message = update.get('message') or update.get('channel_post')
            if not message:
                continue
            
            msg_chat_id = str(message.get('chat', {}).get('id'))
            if msg_chat_id != chat_id:
                continue
            
            msg_id = message.get('message_id')
            text = message.get('text', '')
            
            if not text or len(text) < 10:
                continue
            
            # Проверяем, есть ли уже это сообщение
            existing = Announcement.query.filter_by(telegram_message_id=msg_id).first()
            if existing:
                continue
            
            # Извлекаем заголовок (первая строка или первые 100 символов)
            lines = text.split('\n')
            title = lines[0][:100] if lines else text[:100]
            content = text
            
            # Создаем объявление
            announcement = Announcement(
                title=title,
                content=content,
                telegram_message_id=msg_id,
                date=datetime.fromtimestamp(message.get('date', 0))
            )
            db.session.add(announcement)
            new_count += 1
        
        db.session.commit()
        return jsonify({'success': True, 'new_announcements': new_count})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    """Webhook для получения сообщений из Telegram в реальном времени."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': False}), 400

    message = (
        data.get('message') or
        data.get('channel_post') or
        data.get('edited_message') or
        data.get('edited_channel_post')
    )

    if message:
        chat_id = str(message.get('chat', {}).get('id', ''))
        if chat_id == app.config['TELEGRAM_CHAT_ID']:
            text = message.get('text') or message.get('caption', '')
            msg_id = message.get('message_id')
            date = message.get('date', 0)

            if text and len(text.strip()) >= 5:
                existing = Announcement.query.filter_by(telegram_message_id=msg_id).first()
                if not existing:
                    lines = text.strip().split('\n')
                    title = lines[0][:200]
                    announcement = Announcement(
                        title=title,
                        content=text.strip(),
                        telegram_message_id=msg_id,
                        date=datetime.fromtimestamp(date)
                    )
                    db.session.add(announcement)
                    db.session.commit()

    return jsonify({'ok': True})


@app.route('/fetch-telegram-messages')
def fetch_telegram_messages():
    """Автоматическая синхронизация через webhook или cron"""
    bot_token = app.config['TELEGRAM_BOT_TOKEN']
    chat_id = app.config['TELEGRAM_CHAT_ID']
    
    if not bot_token:
        return jsonify({'error': 'Bot token not configured'}), 400
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if not data.get('ok'):
            return jsonify({'error': 'Telegram API error'}), 400
        
        messages = []
        for update in data.get('result', []):
            message = update.get('message') or update.get('channel_post')
            if message and str(message.get('chat', {}).get('id')) == chat_id:
                messages.append({
                    'id': message.get('message_id'),
                    'text': message.get('text', ''),
                    'date': message.get('date')
                })
        
        return jsonify({'messages': messages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/rating')
def rating():
    return render_template("rating.html")

@app.route('/prices')
def prices():
    return render_template("prices.html")

@app.route('/rule')
def rule():
    return render_template("rule.html")

@app.route('/join', methods=["POST", "GET"])
def join():
    if request.method == "GET":
        if current_user.is_authenticated:
            flash("Вы уже авторизованы", 'warning')
            return redirect("/")
        return render_template("join.html")
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Такого пользователя не существует', 'danger')
        return redirect("/join")
    if check_password_hash(user.password, password):
        login_user(user)
        return redirect('/')
    flash("Неверный логин или пароль!", 'danger')
    return render_template("join.html")


@app.route('/logout')
def logout():
    logout_user()
    return redirect("/")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    # Запускаем Telegram бота в фоновом потоке
    def run_bot():
        token = app.config['TELEGRAM_BOT_TOKEN']
        chat_id = app.config['TELEGRAM_CHAT_ID']
        offset = None

        logger.info(f'Telegram бот запущен, слушаю канал {chat_id}')

        while True:
            try:
                params = {'timeout': 30, 'allowed_updates': ['message', 'channel_post']}
                if offset:
                    params['offset'] = offset

                resp = requests.get(
                    f'https://api.telegram.org/bot{token}/getUpdates',
                    params=params, timeout=35
                )
                data = resp.json()

                if not data.get('ok'):
                    time.sleep(5)
                    continue

                for update in data.get('result', []):
                    message = (update.get('message') or update.get('channel_post') or
                               update.get('edited_message') or update.get('edited_channel_post'))

                    if message and str(message.get('chat', {}).get('id', '')) == str(chat_id):
                        text = message.get('text') or message.get('caption', '')
                        msg_id = message.get('message_id')
                        date = message.get('date', 0)

                        if text and len(text.strip()) >= 5:
                            with app.app_context():
                                existing = Announcement.query.filter_by(telegram_message_id=msg_id).first()
                                if not existing:
                                    lines = text.strip().split('\n')
                                    ann = Announcement(
                                        title=lines[0][:200],
                                        content=text.strip(),
                                        telegram_message_id=msg_id,
                                        date=datetime.fromtimestamp(date)
                                    )
                                    db.session.add(ann)
                                    db.session.commit()
                                    logger.info(f'Новое объявление: {lines[0][:50]}')

                    offset = update['update_id'] + 1

            except Exception as e:
                logger.error(f'Ошибка бота: {e}')
                time.sleep(5)

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    app.run(debug=True, host='127.0.0.1', port=5000)
