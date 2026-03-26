"""
Telegram Bot - получает сообщения из группы/канала и сохраняет как объявления на сайте.

Два режима работы:
  1. Webhook (рекомендуется для хостинга) - Telegram сам присылает обновления
  2. Polling (для локальной разработки) - бот сам опрашивает Telegram

Настройка:
  TELEGRAM_BOT_TOKEN - токен от @BotFather
  TELEGRAM_CHAT_ID   - ID группы/канала (например -3261646428)

Для webhook: зарегистрируйте URL после деплоя:
  https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://ваш-домен.com/telegram-webhook
"""

import os
import logging
import sqlite3
import requests
from datetime import datetime
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── Конфигурация ────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get('TELEGRAM_BOT_TOKEN', '8761314269:AAHhIBVTrOeCFrqjatzt-RhsXzk4SWsCcJQ')
CHANNEL_ID  = os.environ.get('TELEGRAM_CHAT_ID', '-3261646428')
DB_PATH     = os.environ.get('DATABASE_PATH', 'instance/main.db')
MIN_LENGTH  = 5  # минимальная длина сообщения
# ─────────────────────────────────────────────────────────────────────────────


def save_announcement(msg_id: int, text: str, date: int) -> bool:
    """Сохраняет сообщение в БД как объявление. Возвращает True если добавлено."""
    if not text or len(text.strip()) < MIN_LENGTH:
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Проверяем дубликат
        cur.execute('SELECT id FROM announcement WHERE telegram_message_id = ?', (msg_id,))
        if cur.fetchone():
            conn.close()
            return False

        lines = text.strip().split('\n')
        title = lines[0][:200]
        pub_date = datetime.fromtimestamp(date).strftime('%Y-%m-%d %H:%M:%S')

        cur.execute(
            'INSERT INTO announcement (title, content, date, telegram_message_id) VALUES (?, ?, ?, ?)',
            (title, text.strip(), pub_date, msg_id)
        )
        conn.commit()
        conn.close()
        logger.info(f'Добавлено объявление: [{msg_id}] {title[:50]}')
        return True

    except sqlite3.OperationalError as e:
        logger.error(f'Ошибка БД: {e}. Убедитесь что main.py запускался хотя бы раз.')
        return False
    except Exception as e:
        logger.error(f'Неожиданная ошибка: {e}')
        return False


def process_update(update: dict) -> bool:
    """Обрабатывает одно обновление от Telegram."""
    # Поддерживаем сообщения из групп, каналов и супергрупп
    message = (
        update.get('message') or
        update.get('channel_post') or
        update.get('edited_message') or
        update.get('edited_channel_post')
    )

    if not message:
        return False

    chat_id = str(message.get('chat', {}).get('id', ''))
    if chat_id != str(CHANNEL_ID):
        logger.debug(f'Пропущено сообщение из чата {chat_id} (ожидается {CHANNEL_ID})')
        return False

    text = message.get('text') or message.get('caption', '')
    msg_id = message.get('message_id')
    date = message.get('date', 0)

    return save_announcement(msg_id, text, date)


# ─── Webhook режим (для хостинга) ────────────────────────────────────────────

bot_app = Flask(__name__)

@bot_app.route('/telegram-webhook', methods=['POST'])
def webhook():
    """Принимает обновления от Telegram через webhook."""
    update = request.get_json(silent=True)
    if not update:
        return jsonify({'ok': False, 'error': 'No JSON'}), 400

    process_update(update)
    return jsonify({'ok': True})


@bot_app.route('/register-webhook', methods=['GET'])
def register_webhook():
    """Регистрирует webhook. Вызовите один раз после деплоя."""
    site_url = request.args.get('url')
    if not site_url:
        return jsonify({'error': 'Укажите параметр ?url=https://ваш-домен.com'}), 400

    webhook_url = f'{site_url.rstrip("/")}/telegram-webhook'
    resp = requests.post(
        f'https://api.telegram.org/bot{BOT_TOKEN}/setWebhook',
        json={'url': webhook_url}
    )
    return jsonify(resp.json())


@bot_app.route('/webhook-info', methods=['GET'])
def webhook_info():
    """Показывает текущий статус webhook."""
    resp = requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo')
    return jsonify(resp.json())


# ─── Polling режим (для локальной разработки) ─────────────────────────────────

def run_polling():
    """Запускает бота в режиме polling (только для локальной разработки)."""
    import time

    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error('Установите TELEGRAM_BOT_TOKEN перед запуском!')
        return

    logger.info(f'Бот запущен в режиме polling. Слушаю канал {CHANNEL_ID}...')

    # Сбрасываем webhook если был установлен
    requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook')

    offset = None
    while True:
        try:
            params = {'timeout': 30, 'allowed_updates': ['message', 'channel_post']}
            if offset:
                params['offset'] = offset

            resp = requests.get(
                f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates',
                params=params,
                timeout=35
            )
            data = resp.json()

            if not data.get('ok'):
                logger.error(f'Ошибка API: {data}')
                time.sleep(5)
                continue

            for update in data.get('result', []):
                process_update(update)
                offset = update['update_id'] + 1

        except requests.exceptions.ConnectionError:
            logger.warning('Нет соединения, повтор через 10 сек...')
            time.sleep(10)
        except KeyboardInterrupt:
            logger.info('Бот остановлен.')
            break
        except Exception as e:
            logger.error(f'Ошибка: {e}')
            time.sleep(5)


if __name__ == '__main__':
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else 'polling'

    if mode == 'webhook':
        # Запуск Flask сервера для webhook
        port = int(os.environ.get('PORT', 5001))
        logger.info(f'Запуск webhook сервера на порту {port}')
        bot_app.run(host='0.0.0.0', port=port)
    else:
        # Запуск polling (по умолчанию)
        run_polling()
