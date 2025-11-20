import os
import logging
from datetime import datetime
from decouple import config
from aiohttp import web

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from database import (
    save_insight_to_db,
    get_count_by_field,
    get_count_by_two_fields,
    get_all_insights,
    get_filtered_insights,
)
from export_excel import export_insights_to_excel

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация
BOT_TOKEN = config('BOT_TOKEN')
WEBHOOK_URL = config('WEBHOOK_URL')
PORT = int(config('PORT', default=8000))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Константы
MACRO_REGIONS = ["МСК", "ЦФО", "СЗФО", "УФО", "ЮФО", "ПФО", "СДФО", "СНГ"]
INDUSTRIES = ["Оборона", "Промышленность", "Торговля", "Банки", "Нефть и газ", "Энергетика"]

# FSM State Machine
class InsightForm(StatesGroup):
    macro_region = State()
    industry = State()
    theme = State()
    description = State()
    file_attachment = State()

class SearchForm(StatesGroup):
    macro_region = State()
    industry = State()
    viewing = State()

# ==================== Создание клавиатур ====================

async def create_main_keyboard():
    """Создание главной клавиатуры"""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать новый инсайт", callback_data="new_insight")
    builder.button(text="🔍 Поиск и просмотр", callback_data="search_insights")
    builder.button(text="📊 Экспорт в Excel", callback_data="export_excel")
    builder.button(text="ℹ️ О боте", callback_data="about_bot")
    builder.adjust(1)
    return builder.as_markup()

async def create_region_keyboard(for_search=False):
    """Создание клавиатуры выбора макрорегиона"""
    builder = InlineKeyboardBuilder()
    
    for region in MACRO_REGIONS:
        count = await get_count_by_field("macro_region", region)
        prefix = "search" if for_search else "new"
        builder.button(
            text=f"{region} ({count})",
            callback_data=f"{prefix}_region_{region}"
        )
    
    builder.button(text="⬅️ Назад", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()

async def create_industry_keyboard(macro_region=None, for_search=False):
    """Создание клавиатуры выбора отрасли - считает по выбранному макро"""
    builder = InlineKeyboardBuilder()
    
    for industry in INDUSTRIES:
        # Если указан макро, считаем только для этого макро
        if macro_region:
            count = await get_count_by_two_fields("macro_region", macro_region, "industry", industry)
        else:
            count = await get_count_by_field("industry", industry)
        
        prefix = "search" if for_search else "new"
        builder.button(
            text=f"{industry} ({count})",
            callback_data=f"{prefix}_industry_{industry}"
        )
    
    builder.button(text="⬅️ Назад", callback_data="back_to_regions" if macro_region else "back_to_main")
    builder.adjust(1)
    return builder.as_markup()

# ==================== Команды ====================

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработка команды /start с красивым приветствием"""
    logger.info(f"User {message.from_user.id} ({message.from_user.username}) started the bot")
    
    welcome_text = f"""
🎉 Добро пожаловать в Insights Bot!

👋 Привет, {message.from_user.first_name}!

Это приложение предназначено для управления деловыми инсайдами по макрорегионам и отраслям экономики.

📌 **Основные возможности:**

✏️ **Создать инсайт** — добавить новое наблюдение, факт или аналитику
   • Выберите макрорегион (МСК, ЦФО, СЗФО и др.)
   • Выберите отрасль (Оборона, Промышленность, Торговля и др.)
   • Опишите суть инсайта
   • Прикрепите документ или фото (опционально)

🔍 **Поиск и просмотр** — найти сохраненные инсайты
   • Фильтруйте по макрорегиону и отрасли
   • Листайте результаты
   • Скачивайте прикрепленные файлы

📊 **Экспорт в Excel** — выгрузить все данные в таблицу
   • Получите красиво отформатированный файл
   • Удобно для анализа и архивирования

💾 **Облачное хранилище** — все данные хранятся безопасно в БД

─────────────────────────────────────

⬇️ Выберите действие ниже, чтобы начать:
"""
    
    await message.answer(welcome_text, reply_markup=await create_main_keyboard())

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Справка по командам"""
    help_text = """
🤖 **Доступные команды:**

/start — Главное меню и приветствие
/help — Эта справка
/cancel — Отмена текущей операции

📌 **Основные функции:**

➕ **Создать новый инсайт**
   Пошаговое заполнение:
   1. Выберите макрорегион
   2. Выберите отрасль
   3. Введите тему
   4. Введите описание
   5. Прикрепите файл или пропустите
   ✅ Инсайт сохранен!

🔍 **Поиск и просмотр**
   1. Выберите макрорегион
   2. Выберите отрасль
   3. Просмотрите найденные инсайты
   4. Листайте результаты, скачивайте файлы

📊 **Экспорт в Excel**
   Выгрузите все сохраненные инсайты в один файл

ℹ️ **О боте**
   Получите подробную информацию о приложении
"""
    await message.answer(help_text)

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущей операции"""
    await state.clear()
    await message.answer("❌ Операция отменена", reply_markup=await create_main_keyboard())

# ==================== Информация о боте ====================

@router.callback_query(F.data == "about_bot")
async def about_bot(callback: CallbackQuery):
    """Информация о боте"""
    about_text = """
ℹ️ **О Insights Bot**

🎯 **Назначение:**
Управление и анализ деловых инсайтов по макрорегионам и отраслям экономики.

🔧 **Технология:**
• Telegram Bot API (aiogram)
• PostgreSQL база данных (Supabase)
• Облачный хостинг (Render)
• Python 3.11+

📊 **Функциональность:**
✅ Создание и сохранение инсайтов
✅ Гибкая фильтрация по регионам и отраслям
✅ Экспорт данных в Excel с форматированием
✅ Прикрепление файлов и документов
✅ 24/7 доступность

🌍 **Поддерживаемые макрорегионы:**
МСК, ЦФО, СЗФО, УФО, ЮФО, ПФО, СДФО, СНГ

🏭 **Поддерживаемые отрасли:**
Оборона, Промышленность, Торговля, Банки, Нефть и газ, Энергетика

💾 **Безопасность:**
Все данные хранятся в защищенной облачной БД с автоматическим резервным копированием.

─────────────────────────────────────
"""
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 В меню", callback_data="back_to_main")
    builder.adjust(1)
    
    await callback.message.edit_text(about_text, reply_markup=builder.as_markup())
    await callback.answer()

# ==================== Главное меню ====================

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.edit_text(
        "📌 Главное меню:\n\nВыберите действие:",
        reply_markup=await create_main_keyboard()
    )
    await callback.answer()

# ==================== СОЗДАНИЕ НОВОЙ ЗАПИСИ ====================

@router.callback_query(F.data == "new_insight")
async def new_insight_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания нового инсайта - сначала выбираем регион"""
    logger.info(f"User {callback.from_user.id} started creating new insight")
    keyboard = await create_region_keyboard(for_search=False)
    await callback.message.edit_text("🗺️ Выберите макрорегион:", reply_markup=keyboard)
    await state.set_state(InsightForm.macro_region)
    await callback.answer()

@router.callback_query(InsightForm.macro_region, F.data.startswith("new_region_"))
async def process_region(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора макрорегиона"""
    region = callback.data.replace("new_region_", "")
    await state.update_data(macro_region=region)
    
    keyboard = await create_industry_keyboard(macro_region=region, for_search=False)
    await callback.message.edit_text("🏭 Выберите отрасль:", reply_markup=keyboard)
    await state.set_state(InsightForm.industry)
    await callback.answer()

@router.callback_query(InsightForm.industry, F.data.startswith("new_industry_"))
async def process_industry(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора отрасли"""
    industry = callback.data.replace("new_industry_", "")
    await state.update_data(industry=industry)
    
    await callback.message.edit_text("📝 Введите тему инсайта (максимум 255 символов):")
    await state.set_state(InsightForm.theme)
    await callback.answer()

@router.message(InsightForm.theme)
async def process_theme(message: Message, state: FSMContext):
    """Обработка темы инсайта"""
    if len(message.text) > 255:
        await message.answer("❌ Тема слишком длинная (максимум 255 символов)")
        return
    
    await state.update_data(theme=message.text)
    await message.answer("📄 Введите подробное описание инсайта:")
    await state.set_state(InsightForm.description)

@router.message(InsightForm.description)
async def process_description(message: Message, state: FSMContext):
    """Обработка описания инсайта"""
    await state.update_data(description=message.text)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📎 Прикрепить файл", callback_data="attach_file")
    builder.button(text="⏭️ Пропустить", callback_data="skip_file")
    builder.adjust(1)
    
    await message.answer(
        "📎 **Финальный шаг**\n\n"
        "Хотите прикрепить файл к инсайту?\n"
        "Вы можете отправить документ или фотографию.",
        reply_markup=builder.as_markup()
    )
    await state.set_state(InsightForm.file_attachment)

@router.callback_query(InsightForm.file_attachment, F.data == "attach_file")
async def ready_for_file(callback: CallbackQuery):
    """Подготовка к получению файла"""
    await callback.message.edit_text(
        "📤 Отправьте файл (документ или фото).\n"
        "Используйте /cancel для отмены."
    )
    await callback.answer()

@router.message(InsightForm.file_attachment, F.document)
async def process_document(message: Message, state: FSMContext):
    """Обработка прикрепленного документа"""
    file_id = message.document.file_id
    filename = message.document.file_name
    
    await state.update_data(file_id=file_id, filename=filename)
    
    data = await state.get_data()
    try:
        await save_insight_to_db(data, message.from_user.id)
        logger.info(f"User {message.from_user.id} created insight with document: {data.get('theme')}")
        
        success_text = (
            f"✅ **Инсайт успешно создан!**\n\n"
            f"📝 Тема: {data['theme']}\n"
            f"🗺️ Макрорегион: {data['macro_region']}\n"
            f"🏭 Отрасль: {data['industry']}\n"
            f"📎 Файл: {filename}"
        )
        
        await message.answer(success_text, reply_markup=await create_main_keyboard())
    except Exception as e:
        logger.error(f"Error saving insight with document: {str(e)}", exc_info=True)
        await message.answer(f"❌ Ошибка при сохранении инсайта: {str(e)}")
    
    await state.clear()

@router.message(InsightForm.file_attachment, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка прикрепленной фотографии"""
    file_id = message.photo[-1].file_id
    
    await state.update_data(file_id=file_id, filename=None)
    
    data = await state.get_data()
    try:
        await save_insight_to_db(data, message.from_user.id)
        logger.info(f"User {message.from_user.id} created insight with photo: {data.get('theme')}")
        
        success_text = (
            f"✅ **Инсайт успешно создан!**\n\n"
            f"📝 Тема: {data['theme']}\n"
            f"🗺️ Макрорегион: {data['macro_region']}\n"
            f"🏭 Отрасль: {data['industry']}\n"
            f"📸 Фото прикреплено"
        )
        
        await message.answer(success_text, reply_markup=await create_main_keyboard())
    except Exception as e:
        logger.error(f"Error saving insight with photo: {str(e)}", exc_info=True)
        await message.answer(f"❌ Ошибка при сохранении инсайта: {str(e)}")
    
    await state.clear()

@router.callback_query(InsightForm.file_attachment, F.data == "skip_file")
async def skip_file(callback: CallbackQuery, state: FSMContext):
    """Пропуск прикрепления файла"""
    data = await state.get_data()
    try:
        if 'file_id' not in data:
            data['file_id'] = None
            data['filename'] = None
        
        logger.info(f"Saving insight for user {callback.from_user.id}: theme={data.get('theme')}, region={data.get('macro_region')}, industry={data.get('industry')}")
        
        await save_insight_to_db(data, callback.from_user.id)
        logger.info(f"User {callback.from_user.id} created insight without file: {data.get('theme')}")
        
        success_text = (
            f"✅ **Инсайт успешно создан!**\n\n"
            f"📝 Тема: {data['theme']}\n"
            f"🗺️ Макрорегион: {data['macro_region']}\n"
            f"🏭 Отрасль: {data['industry']}"
        )
        
        await callback.message.edit_text(success_text, reply_markup=await create_main_keyboard())
    except Exception as e:
        logger.error(f"Error saving insight without file: {str(e)}", exc_info=True)
        await callback.message.edit_text(f"❌ Ошибка при сохранении инсайта:\n{str(e)}")
    
    await state.clear()
    await callback.answer()

# ==================== ПОИСК И ПРОСМОТР ====================

@router.callback_query(F.data == "search_insights")
async def search_start(callback: CallbackQuery, state: FSMContext):
    """Начало поиска"""
    logger.info(f"User {callback.from_user.id} started searching")
    keyboard = await create_region_keyboard(for_search=True)
    await callback.message.edit_text("🗺️ Выберите макрорегион для поиска:", 
                                     reply_markup=keyboard)
    await state.set_state(SearchForm.macro_region)
    await callback.answer()

@router.callback_query(SearchForm.macro_region, F.data.startswith("search_region_"))
async def search_region_selected(callback: CallbackQuery, state: FSMContext):
    """Выбор макрорегиона в поиске"""
    region = callback.data.replace("search_region_", "")
    logger.info(f"User {callback.from_user.id} selected region: {region}")
    await state.update_data(macro_region=region)
    
    keyboard = await create_industry_keyboard(macro_region=region, for_search=True)
    await callback.message.edit_text("🏭 Выберите отрасль:", reply_markup=keyboard)
    await state.set_state(SearchForm.industry)
    await callback.answer()

@router.callback_query(SearchForm.industry, F.data.startswith("search_industry_"))
async def search_industry_selected(callback: CallbackQuery, state: FSMContext):
    """Выбор отрасли в поиске и вывод результатов"""
    industry = callback.data.replace("search_industry_", "")
    logger.info(f"User {callback.from_user.id} selected industry: {industry}")
    await state.update_data(industry=industry)
    
    data = await state.get_data()
    filters = {
        "macro_region": data.get("macro_region"),
        "industry": industry
    }
    
    logger.info(f"🔍 User {callback.from_user.id} searching with filters: {filters}")
    
    try:
        insights = await get_filtered_insights(filters)
        logger.info(f"✅ Found {len(insights)} insights with filters {filters}")
        
        if not insights:
            logger.warning(f"⚠️ No insights found for filters: {filters}")
            await callback.message.edit_text(
                f"😔 Записей не найдено\n\n"
                f"🗺️ Регион: {filters['macro_region']}\n"
                f"🏭 Отрасль: {filters['industry']}\n\n"
                "Создайте первый инсайт!",
                reply_markup=InlineKeyboardBuilder()
                .button(text="⬅️ Назад", callback_data="back_to_main")
                .as_markup()
            )
            await state.clear()
            await callback.answer()
            return
        
        await show_insight(callback.message, insights[0], insights, 0, state)
        await state.update_data(insights=insights, current_index=0)
        await state.set_state(SearchForm.viewing)
        logger.info(f"Showing first insight to user {callback.from_user.id}")
    except Exception as e:
        logger.error(f"❌ Error searching insights: {str(e)}", exc_info=True)
        await callback.message.edit_text(f"❌ Ошибка при поиске:\n{str(e)}")
    
    await callback.answer()

async def show_insight(message, insight, insights_list, index, state):
    """Показать один инсайт с навигацией"""
    insight_text = (
        f"📌 **Инсайт {index + 1} из {len(insights_list)}**\n\n"
        f"📅 Дата: {insight['created_at'][:10]}\n"
        f"📝 Тема: {insight['theme']}\n"
        f"📄 Описание: {insight['description']}\n"
        f"🗺️ Макрорегион: {insight['macro_region']}\n"
        f"🏭 Отрасль: {insight['industry']}"
    )
    
    builder = InlineKeyboardBuilder()
    
    if index > 0:
        builder.button(text="⬅️ Пред.", callback_data="prev_insight")
    
    if index < len(insights_list) - 1:
        builder.button(text="Сл. ➡️", callback_data="next_insight")
    
    if insight.get('file_id'):
        builder.button(text="📎 Файл", callback_data="download_file")
    
    builder.button(text="🔍 К фильтрам", callback_data="back_to_search")
    builder.button(text="🔙 Меню", callback_data="back_to_main")
    builder.adjust(2)
    
    await message.edit_text(insight_text, reply_markup=builder.as_markup())

@router.callback_query(SearchForm.viewing, F.data == "next_insight")
async def next_insight(callback: CallbackQuery, state: FSMContext):
    """Следующий инсайт"""
    data = await state.get_data()
    index = data.get("current_index", 0) + 1
    insights = data.get("insights", [])
    
    if index < len(insights):
        await state.update_data(current_index=index)
        await show_insight(callback.message, insights[index], insights, index, state)
    
    await callback.answer()

@router.callback_query(SearchForm.viewing, F.data == "prev_insight")
async def prev_insight(callback: CallbackQuery, state: FSMContext):
    """Предыдущий инсайт"""
    data = await state.get_data()
    index = max(0, data.get("current_index", 0) - 1)
    insights = data.get("insights", [])
    
    await state.update_data(current_index=index)
    await show_insight(callback.message, insights[index], insights, index, state)
    
    await callback.answer()

@router.callback_query(SearchForm.viewing, F.data == "download_file")
async def download_file(callback: CallbackQuery, state: FSMContext):
    """Скачивание файла из инсайта"""
    data = await state.get_data()
    insights = data.get("insights", [])
    current_index = data.get("current_index", 0)
    insight = insights[current_index]
    
    if insight.get('file_id'):
        try:
            await bot.send_document(
                callback.from_user.id,
                insight['file_id'],
                caption=f"📎 Файл из инсайта: {insight['theme']}"
            )
            logger.info(f"User {callback.from_user.id} downloaded file")
        except Exception as e:
            logger.error(f"Error downloading file: {e}", exc_info=True)
            await callback.answer("❌ Ошибка при скачивании файла", show_alert=True)
    
    await callback.answer()

@router.callback_query(SearchForm.viewing, F.data == "back_to_search")
async def back_to_search(callback: CallbackQuery, state: FSMContext):
    """Возврат к фильтрам поиска"""
    data = await state.get_data()
    region = data.get("macro_region")
    industry = data.get("industry")

    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить фильтры", callback_data="search_insights")
    builder.button(text="🔙 В меню", callback_data="back_to_main")
    builder.adjust(1)

    await callback.message.edit_text(
        f"🔍 **Текущие фильтры:**\n\n"
        f"🗺️ Регион: {region}\n"
        f"🏭 Отрасль: {industry}\n\n"
        f"Хотите изменить фильтры?",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_regions")
async def back_to_regions(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    region = data.get("macro_region")
    
    await state.set_state(InsightForm.industry)  # ← КЛЮЧЕВАЯ СТРОКА!
    
    keyboard = await create_industry_keyboard(macro_region=region, for_search=False)
    await callback.message.edit_text("🏭 Выберите отрасль:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "back_to_search_regions")
async def back_to_search_regions(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору отраслей в режиме поиска"""
    data = await state.get_data()
    region = data.get("macro_region")
    
    await state.set_state(SearchForm.industry)  # ← КЛЮЧЕВАЯ СТРОКА!
    
    keyboard = await create_industry_keyboard(macro_region=region, for_search=True)
    await callback.message.edit_text("🏭 Выберите отрасль:", reply_markup=keyboard)
    await callback.answer()


# ==================== ЭКСПОРТ В EXCEL ====================

@router.callback_query(F.data == "export_excel")
async def export_excel(callback: CallbackQuery):
    """Экспорт всех инсайтов в Excel"""
    logger.info(f"User {callback.from_user.id} requested export")
    
    try:
        insights = await get_all_insights()
        
        if not insights:
            await callback.answer("❌ Нет данных для экспорта", show_alert=True)
            return
        
        filename = await export_insights_to_excel(insights, callback.from_user.id)
        
        file = FSInputFile(filename)
        await callback.message.answer_document(
            file,
            caption=f"📊 Экспорт инсайтов ({len(insights)} записей)\n\n"
                    f"Файл содержит все сохраненные данные с форматированием."
        )
        
        logger.info(f"Export completed for user {callback.from_user.id}")
        
        if os.path.exists(filename):
            os.remove(filename)
    
    except Exception as e:
        logger.error(f"Export error for user {callback.from_user.id}: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при экспорте данных", show_alert=True)
    
    await callback.answer()

# ==================== WEBHOOK SETUP ====================

async def on_startup(bot: Bot, base_url: str):
    """Установка webhook при запуске"""
    await bot.set_webhook(f"{base_url}/webhook")
    logger.info(f"Webhook set to {base_url}/webhook")

async def on_shutdown(bot: Bot):
    """Удаление webhook при остановке"""
    await bot.delete_webhook()
    logger.info("Webhook deleted")

# ==================== MAIN ====================

def main():
    """Запуск бота на webhook"""
    dp.include_router(router)
    
    app = web.Application()
    
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    
    webhook_requests_handler.register(app, path="/webhook")
    
    setup_application(app, dp, bot=bot)
    
    logger.info(f"Starting bot on 0.0.0.0:{PORT}")
    logger.info(f"Webhook URL: {WEBHOOK_URL}/webhook")
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
