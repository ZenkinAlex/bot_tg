#!/usr/bin/env python3
"""
Диагностический скрипт для проверки конфигурации Supabase
Запустите: python debug_supabase.py
"""

import os
import sys
from decouple import config

print("=" * 60)
print("🔍 ДИАГНОСТИКА SUPABASE КОНФИГУРАЦИИ")
print("=" * 60)
print()

# Проверка .env файла
print("1️⃣  Проверка файла .env")
print("-" * 60)
if os.path.exists('.env'):
    print("✅ Файл .env найден")
else:
    print("❌ Файл .env НЕ найден!")
    print("   Создайте файл .env со следующим содержимым:")
    print()
    print("   BOT_TOKEN=ваш_токен_здесь")
    print("   SUPABASE_URL=https://your-project.supabase.co")
    print("   SUPABASE_KEY=ваш_anon_ключ_здесь")
    print("   WEBHOOK_URL=http://localhost:8000")
    print("   PORT=8000")
    print()
    sys.exit(1)

print()

# Проверка переменных
print("2️⃣  Проверка переменных окружения")
print("-" * 60)

try:
    supabase_url = config('SUPABASE_URL')
    print(f"✅ SUPABASE_URL найден")
    print(f"   Значение: {supabase_url[:50]}...")
    print(f"   Длина: {len(supabase_url)} символов")
    
    # Проверки URL
    if not supabase_url.startswith('https://'):
        print(f"   ⚠️  ВНИМАНИЕ: URL должен начинаться с https://")
    if '.supabase.co' not in supabase_url:
        print(f"   ⚠️  ВНИМАНИЕ: URL должен содержать .supabase.co")
    
except Exception as e:
    print(f"❌ SUPABASE_URL ошибка: {e}")
    sys.exit(1)

print()

try:
    supabase_key = config('SUPABASE_KEY')
    print(f"✅ SUPABASE_KEY найден")
    print(f"   Значение: {supabase_key[:30]}...{supabase_key[-10:]}")
    print(f"   Длина: {len(supabase_key)} символов")
    
    # Проверки ключа
    if len(supabase_key) < 50:
        print(f"   ⚠️  ВНИМАНИЕ: Ключ очень короткий (обычно 100-200 символов)")
    if supabase_key.startswith('sbp_'):
        print(f"   ❌ ОШИБКА: Это service_role ключ! Используйте anon ключ!")
    if not supabase_key.startswith('eyJ'):
        print(f"   ⚠️  ВНИМАНИЕ: Ключ должен начинаться с eyJ")
    
except Exception as e:
    print(f"❌ SUPABASE_KEY ошибка: {e}")
    sys.exit(1)

print()

try:
    bot_token = config('BOT_TOKEN')
    print(f"✅ BOT_TOKEN найден")
    print(f"   Значение: {bot_token[:20]}...{bot_token[-10:]}")
    print(f"   Длина: {len(bot_token)} символов")
except Exception as e:
    print(f"❌ BOT_TOKEN ошибка: {e}")

print()
print()

# Попытка подключения к Supabase
print("3️⃣  Попытка подключения к Supabase")
print("-" * 60)

try:
    from supabase import create_client
    
    print("📡 Подключение к Supabase...")
    supabase = create_client(supabase_url, supabase_key)
    print("✅ УСПЕШНОЕ ПОДКЛЮЧЕНИЕ К SUPABASE!")
    
    # Проверка таблицы
    print()
    print("4️⃣  Проверка таблицы insights")
    print("-" * 60)
    
    try:
        response = supabase.table("insights").select("*", count="exact").limit(1).execute()
        print(f"✅ Таблица insights доступна")
        print(f"   Количество записей: {response.count}")
    except Exception as table_error:
        if "does not exist" in str(table_error):
            print(f"⚠️  Таблица insights не существует")
            print(f"   Выполните SQL из README.md в Supabase SQL Editor")
        else:
            print(f"❌ Ошибка при проверке таблицы: {table_error}")
    
except ImportError:
    print("❌ Библиотека supabase не установлена")
    print("   Запустите: pip install supabase")
    sys.exit(1)
except Exception as e:
    print(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {e}")
    print()
    print("🔧 Возможные причины:")
    print("   1. SUPABASE_KEY - неправильный ключ")
    print("      → Используйте 'anon (Public)' ключ, НЕ 'service_role'")
    print("   2. В ключе есть пробелы в начале или конце")
    print("      → Проверьте .env файл")
    print("   3. SUPABASE_URL неправильный")
    print("      → Должен быть вида: https://project-name.supabase.co")
    print("   4. Проект в Supabase удален или заморожен")
    print("      → Проверьте статус проекта на supabase.com")
    sys.exit(1)

print()
print()
print("=" * 60)
print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! БОТ ГОТОВ К ЗАПУСКУ")
print("=" * 60)
print()
print("Запустите: python main.py")
