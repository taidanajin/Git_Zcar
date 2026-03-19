# Настройка интеграции с Telegram

## Шаг 1: Создание Telegram бота

1. Откройте Telegram и найдите бота [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Следуйте инструкциям: введите имя бота и username
4. Получите токен бота (выглядит как `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Сохраните этот токен

## Шаг 2: Добавление бота в канал

1. Откройте ваш Telegram канал (https://web.telegram.org/k/#-3261646428)
2. Перейдите в настройки канала → Администраторы
3. Добавьте вашего бота как администратора
4. Дайте боту права на чтение сообщений

## Шаг 3: Настройка переменных окружения

### Windows (PowerShell):
```powershell
$env:TELEGRAM_BOT_TOKEN="ваш_токен_бота"
```

### Windows (CMD):
```cmd
set TELEGRAM_BOT_TOKEN=ваш_токен_бота
```

### Linux/Mac:
```bash
export TELEGRAM_BOT_TOKEN="ваш_токен_бота"
```

## Шаг 4: Обновление базы данных

Запустите Python для создания новой таблицы:

```python
from __init__ import app, db
with app.app_context():
    db.create_all()
```

Или просто удалите файл `instance/main.db` и перезапустите приложение.

## Шаг 5: Синхронизация сообщений

### Вариант 1: Ручная синхронизация (для администраторов)

После авторизации как администратор, отправьте POST запрос:

```bash
curl -X POST http://127.0.0.1:5000/sync-telegram \
  -H "Content-Type: application/json" \
  -b "session=ваша_сессия"
```

### Вариант 2: Автоматическая синхронизация

Добавьте в cron (Linux) или Task Scheduler (Windows) команду для периодического запуска:

```bash
# Каждые 5 минут
*/5 * * * * curl http://127.0.0.1:5000/fetch-telegram-messages
```

### Вариант 3: Webhook (рекомендуется для продакшена)

Настройте webhook для получения обновлений в реальном времени:

```python
# Добавьте в main.py
@app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    message = data.get('message') or data.get('channel_post')
    
    if message:
        msg_id = message.get('message_id')
        text = message.get('text', '')
        
        if text and len(text) >= 10:
            existing = Announcement.query.filter_by(telegram_message_id=msg_id).first()
            if not existing:
                lines = text.split('\n')
                title = lines[0][:100] if lines else text[:100]
                
                announcement = Announcement(
                    title=title,
                    content=text,
                    telegram_message_id=msg_id,
                    date=datetime.fromtimestamp(message.get('date', 0))
                )
                db.session.add(announcement)
                db.session.commit()
    
    return jsonify({'ok': True})
```

Затем зарегистрируйте webhook:
```bash
curl -X POST "https://api.telegram.org/bot<ВАШ_ТОКЕН>/setWebhook?url=https://ваш-домен.com/telegram-webhook"
```

## Проверка работы

1. Запустите приложение: `python main.py`
2. Откройте http://127.0.0.1:5000/obj
3. Отправьте сообщение в Telegram канал
4. Выполните синхронизацию
5. Обновите страницу объявлений

## Примечания

- ID канала уже настроен: `-3261646428`
- Бот должен быть администратором канала
- Сообщения короче 10 символов игнорируются
- Первая строка сообщения становится заголовком объявления
