"""
Конфигурация для проекта Telegram Insights Bot

Этот файл можно использовать для централизованного управления конфигурацией
"""

import os
from decouple import config

# ==================== Telegram Bot ====================
BOT_TOKEN = config('BOT_TOKEN')
WEBHOOK_URL = config('WEBHOOK_URL')

# ==================== Supabase ====================
SUPABASE_URL = config('SUPABASE_URL')
SUPABASE_KEY = config('SUPABASE_KEY')

# ==================== Server ====================
PORT = int(config('PORT', default=8000))
DEBUG = config('DEBUG', default=False, cast=bool)

# ==================== Bot Settings ====================
MACRO_REGIONS = [
    "МСК",      # Москва
    "ЦФО",      # Центральный федеральный округ
    "СЗФО",     # Северо-западный федеральный округ
    "УФО",      # Уральский федеральный округ
    "ЮФО",      # Южный федеральный округ
    "ПФО",      # Приволжский федеральный округ
    "СДФО",     # Сибирский федеральный округ
    "СНГ"       # Страны СНГ
]

INDUSTRIES = [
    "Оборона",
    "Промышленность",
    "Торговля",
    "Банки",
    "Нефть и газ",
    "Энергетика"
]

# ==================== Database ====================
DB_TABLE_NAME = "insights"

# Лимиты
MAX_THEME_LENGTH = 255
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Timeout для кэша (в минутах)
CACHE_TIMEOUT_MINUTES = 5

# ==================== Logging ====================
LOG_LEVEL = config('LOG_LEVEL', default='INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# ==================== Export ====================
EXPORT_TEMP_DIR = '/tmp'
EXPORT_BATCH_SIZE = 1000  # Размер батча для экспорта больших данных

# ==================== Rate Limiting ====================
RATE_LIMIT_REQUESTS = 10  # Количество запросов
RATE_LIMIT_PERIOD = 60  # За период (секунды)
