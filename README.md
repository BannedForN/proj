# 🎲 TabletopStoreUP — Интернет-магазин настольных игр  

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0-green?logo=django)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql)](https://www.postgresql.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5-purple?logo=bootstrap)](https://getbootstrap.com/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#)

Полноценный учебный проект интернет-магазина с **Django + REST API (DRF)**.  
Поддерживает регистрацию, корзину, заказы, оплату (имитация), фильтры, ролевую модель, отчёты и пользовательские настройки.

---

## 🚀 Возможности

- 🔐 Регистрация / вход / сброс пароля (SMTP Gmail)
- 👤 Роли пользователей: `admin`, `manager`, `client`, `guest`
- 🛒 Корзина, оформление и история заказов
- 💳 Методы оплаты (наличные, карта, СБП)
- 🚚 Отслеживание доставки и статусы
- 💬 Отзывы и рейтинг товаров
- 🌗 Переключение темы (светлая / тёмная)
- 📊 Админская аналитика с графиками и CSV-экспортом
- ⚙️ Пользовательские настройки (форматы, фильтры, тема)
- 🧾 REST API (JWT, OpenAPI)
- 🧰 Автоматическое наполнение тестовыми данными при миграции

---

## 🗂️ Технологии

| Компонент | Используется |
|------------|--------------|
| **Backend** | Django 5.x, Django REST Framework |
| **Frontend** | Bootstrap 5, кастомная тема (light/dark) |
| **Database** | PostgreSQL |
| **Auth** | JWT (SimpleJWT), Django sessions |
| **Mail** | Gmail SMTP (App Password) |
| **Reports** | Django Admin + аналитика + CSV |

---

## ⚙️ Установка и запуск

### 1️⃣ Клонировать репозиторий
```bash
git clone https://github.com/USERNAME/TabletopStoreUP.git
cd TabletopStoreUP
```

### 2️⃣ Создать виртуальное окружение
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

### 3️⃣ Установить зависимости
```bash
pip install -r requirements.txt
```

---

## 🧾 Конфигурация `.env`

Создай в корне проекта файл `.env` и заполни его:

```ini
# --- SECURITY ---
SECRET_KEY=django-insecure-your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# --- DATABASE ---
DB_ENGINE=django.db.backends.postgresql
DB_NAME=TabletopStoreUP
DB_USER=postgres
DB_PASSWORD=1
DB_HOST=127.0.0.1
DB_PORT=5432

# --- EMAIL ---
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_HOST_USER=youremail@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=youremail@gmail.com

# --- DEMO DATA ---
SEED_DEMO=1
```

> ⚙️ **EMAIL_HOST_PASSWORD** — это *пароль приложения* из [Google App Passwords](https://myaccount.google.com/apppasswords).

---

## 🧱 Миграции и демо-данные

```bash
python manage.py makemigrations
python manage.py migrate
```

При первом запуске создаются:
- Роли (`guest`, `client`, `manager`, `admin`)
- Статусы заказов, оплат и доставок
- Методы оплаты (`Оплата при получении`, `Карта`, `СБП`)
- Жанры, диапазоны игроков
- Пользователи:
  - `manager / manager123`
  - `client / client123`
- Несколько тестовых товаров (`Warhammer`, `Catan`, `Pandemic`, `Ticket to Ride`)

---

## 👑 Создание суперпользователя

```bash
python manage.py createsuperuser
```

Далее войди в [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)  
и управляй товарами, заказами, пользователями и аналитикой.

---

## ▶️ Запуск проекта

```bash
python manage.py runserver
```

После запуска открой:
```
http://127.0.0.1:8000/
```

---

## 🌐 REST API

Документация и эндпоинты:
```
http://127.0.0.1:8000/api/
```

Примеры:
```bash
POST /api/auth/token/          # Получить JWT токен
POST /api/auth/token/refresh/  # Обновить токен
GET  /api/products/            # Список товаров
GET  /api/orders/              # Список заказов пользователя
POST /api/orders/              # Создание нового заказа
GET  /api/user/settings/       # Настройки пользователя
POST /api/user/settings/       # Изменение темы/форматов
```

---

## 💾 Резервное копирование

| Действие | URL / Команда |
|-----------|----------------|
| Просмотр аналитики | `/admin/analytics/` |
| Экспорт CSV | `/admin/analytics/export/` |
| Скачивание резервной копии | `/download-backup/<filename>` |
| Команда создания резервной копии | `python manage.py dumpdata > backup.json` |
| Восстановление из копии | `python manage.py loaddata backup.json` |

---

## 🎨 Интерфейс и темы

- 🎨 Полностью адаптивный Bootstrap 5 UI  
- 🌗 Переключение темы через кнопку (🌙 / 🌞)
- 🧾 Светлая и тёмная темы на едином `theme.css`
- 💬 Всплывающие уведомления (toast)
- 🛒 FAB-кнопка быстрого доступа к корзине

---

## 🧪 Проверка SMTP

```bash
python manage.py shell
```

```python
from django.core.mail import send_mail
send_mail("Тест SMTP", "Если это письмо дошло — SMTP работает.", None, ["youremail@gmail.com"])
```

---

## 📊 Админская аналитика

`/admin/analytics/` — сводные отчёты:
- Количество заказов  
- Общая выручка  
- Средний чек  
- Топ-5 товаров  
- Активность пользователей  
- Экспорт CSV отчёта  

---

## 🧰 Полезные команды

| Команда | Назначение |
|----------|------------|
| `python manage.py runserver` | Запуск сервера |
| `python manage.py createsuperuser` | Создать администратора |
| `python manage.py seed_demo` | Принудительно загрузить демо-данные |
| `python manage.py dumpdata > backup.json` | Резерв БД |
| `python manage.py loaddata backup.json` | Восстановление БД |

---

## 🧱 Структура проекта

```
TabletopStoreUP/
├── manage.py
├── .env
├── requirements.txt
├── README.md
├── TabletopStoreUP/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── store/
│   ├── models.py
│   ├── views.py
│   ├── api.py
│   ├── serializers.py
│   ├── signals.py
│   ├── admin.py
│   ├── templates/store/
│   ├── static/css/theme.css
│   ├── management/commands/seed_demo.py
│   └── apps.py
└── media/
```

---

🧩 *TabletopStoreUP — удобная платформа для любителей настольных игр.*
