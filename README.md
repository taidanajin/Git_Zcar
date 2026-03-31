# ♔ Клуб "Царь" — Сайт мафия-клуба

Веб-сайт для клуба настольной игры "Мафия" с автоматической публикацией объявлений из Telegram-канала.
https://bluverk.pythonanywhere.com/

https://docs.google.com/presentation/d/1AwqtwztBo9svFZsOnvFhLmuW4j-A-ADNXJJw_CliRtg/edit?usp=sharing

---

## Стек

- **Backend:** Python, Flask, Flask-SQLAlchemy, Flask-Login
- **База данных:** SQLite
- **Деплой:** Gunicorn
- **Интеграция:** Telegram Bot API (polling + webhook)

---

## Страницы

| Маршрут | Описание |
|---------|----------|
| `/` | Главная с картой и описанием клуба |
| `/obj` | Объявления из Telegram-канала |
| `/rating` | Рейтинг игроков (Google Sheets) |
| `/prices` | Цены |
| `/rule` | Правила игры |
| `/join` | Вход для администраторов |

---

## Быстрый старт

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Задать переменные окружения
export TELEGRAM_BOT_TOKEN="ваш_токен"
export SECRET_KEY="ваш_секретный_ключ"

# 3. Запустить
python main.py
```

Сайт будет доступен на `http://127.0.0.1:5000`

---

## Telegram-бот

Бот запускается автоматически вместе с `main.py` в фоновом потоке.  
Все новые сообщения из канала `-3261646428` автоматически появляются в разделе `/obj`.

**Требования:**
- Бот должен быть добавлен в канал как **администратор**
- Право "Просмотр сообщений" — обязательно

**Отдельный запуск бота:**
```bash
# Polling (локально)
python telegram_bot.py

# Webhook (продакшен)
python telegram_bot.py webhook
```

**Регистрация webhook после деплоя:**
```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://ваш-домен.com/telegram-webhook
```

---

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather | захардкожен в коде |
| `TELEGRAM_CHAT_ID` | ID Telegram-канала | `-3261646428` |
| `SECRET_KEY` | Секретный ключ Flask | `change-this-in-production` |
| `DATABASE_URL` | URL базы данных | `sqlite:///main.db` |
| `DATABASE_PATH` | Путь к SQLite файлу (для бота) | `instance/main.db` |

---

## Деплой

Проект готов к деплою на любой хостинг с поддержкой Python (Render, Railway, VPS).

```bash
gunicorn run:app
```

`Procfile` уже настроен для автоматического запуска.

---

## Структура проекта

```
├── main.py                  # Flask-приложение + запуск бота
├── telegram_bot.py          # Telegram-бот (отдельный модуль)
├── run.py                   # Точка входа для gunicorn
├── requirements.txt
├── Procfile
├── instance/
│   └── main.db              # SQLite база данных
├── static/
│   └── image/
└── templates/
    ├── base.html
    ├── index.html
    ├── obj.html
    ├── rating.html
    ├── prices.html
    ├── rule.html
    └── join.html
```
