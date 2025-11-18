@echo off
REM Скрипт для быстрой установки и запуска бота на Windows

echo.
echo Telegram Insights Bot - Установка и запуск
echo ================================================
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не установлен. Установите Python 3.9 или выше.
    echo Загрузите Python с https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✓ Python найден
python --version

REM Создание виртуального окружения
if not exist "venv" (
    echo.
    echo 📦 Создание виртуального окружения...
    python -m venv venv
    echo ✓ Виртуальное окружение создано
) else (
    echo.
    echo ✓ Виртуальное окружение уже существует
)

REM Активация виртуального окружения
echo.
echo 🔧 Активация виртуального окружения...
call venv\Scripts\activate.bat

REM Установка зависимостей
echo.
echo 📥 Установка зависимостей...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
echo ✓ Зависимости установлены

REM Проверка .env файла
if not exist ".env" (
    echo.
    echo ⚠️  Файл .env не найден
    echo 📝 Создание .env из .env.example...
    copy .env.example .env
    echo.
    echo ⚠️  Отредактируйте файл .env с вашими данными:
    echo    - BOT_TOKEN - токен от @BotFather
    echo    - SUPABASE_URL - URL вашего Supabase проекта
    echo    - SUPABASE_KEY - API ключ Supabase
    echo    - WEBHOOK_URL - URL вашего приложения
    echo.
    pause
)

echo ✓ Конфигурация готова

REM Запуск бота
echo.
echo 🤖 Запуск бота...
echo ================================================
echo.

python main.py

pause
