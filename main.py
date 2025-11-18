import os
import logging
from datetime import datetime
from decouple import config
import asyncio

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import (
    save_insight_to_db,
    get_count_by_field,
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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Константы
MACRO_REGIONS = ["МСК", "ЦФО", "СЗФО", "УФО", "ЮФО", "ПФО", "СДФО", "СНГ"]
INDUSTRIES = ["Оборона", "Промышленность", "Торговля", "Банки", "Нефть и газ", "Энергетика"]

# FSM State Machine
class InsightForm(StatesGroup):
    theme = State()
    description = State()
    macro_region = State()
    industry = State()
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

async def create_industry_keyboard(region=None, for_search=False):
    """Создание клавиатуры выбора отрасли"""
    builder = InlineKeyboardBuilder()
    
    for industry in INDUSTRIES:
        count = await get_count_by_field("industry", industry)
        prefix = "search" if for_search else "new"
        builder.button(
            text=f"{industry} ({count})",
            callback_data=f"{prefix}_industry_{industry}"
        )
    
    builder.button(text="⬅️ Назад", callback_data="back_to_regions" if region else "back_to_main")
    builder.adjust(1)
    return builder.as_markup()

# ==================== Команды ====================

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработка команды /start"""
    logger.info(f"User {message.from_user.id} ({message.from_user.username}) started the bot")
    await message.answer(
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
        "Этот бот помогает управлять инсайдами по макрорегионам и отраслям.",
        reply_markup=await create_main_keyboard()
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Справка по командам"""
    help_text = """
🤖 Доступные команды:

/start - Главное меню
/help - Эта справка
/cancel - Отмена текущей операции

📌 Основные функции:
• ➕ Создать новый инсайт - добавить новую запись
• 🔍 Поиск и просмотр - найти записи по фильтрам
• 📊 Экспорт в Excel - скачать все данные в таблице
"""
    await message.answer(help_text)

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущей операции"""
    await state.clear()
    await message.answer("❌ Операция отменена", reply_markup=await create_main_keyboard())

# ==================== Главное меню ====================

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.edit_text(
        "📌 Главное меню:",
        reply_markup=await create_main_keyboard()
    )
    await callback.answer()

# ==================== СОЗДАНИЕ НОВОЙ ЗАПИСИ ====================

@router.callback_query(F.data == "new_insight")
async def new_insight_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания нового инсайта"""
    logger.info(f"User {callback.from_user.id} started creating new insight")
    await callback.message.edit_text("📝 Введите тему инсайта:")
    await state.set_state(InsightForm.theme)
    await callback.answer()

@router.message(InsightForm.theme)
async def process_theme(message: Message, state: FSMContext):
    """Обработка темы инсайта"""
    if len(message.text) > 255:
        await message.answer("❌ Тема слишком длинная (макс. 255 символов)")
        return
    
    await state.update_data(theme=message.text)
    await message.answer("📄 Введите описание инсайта:")
    await state.set_state(InsightForm.description)

@router.message(InsightForm.description)
async def process_description(message: Message, state: FSMContext):
    """Обработка описания инсайта"""
    await state.update_data(description=message.text)
    
    keyboard = await create_region_keyboard(for_search=False)
    await message.answer("🗺️ Выберите макрорегион:", reply_markup=keyboard)
    await state.set_state(InsightForm.macro_region)

@router.callback_query(InsightForm.macro_region, F.data.startswith("new_region_"))
async def process_region(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора макрорегиона"""
    region = callback.data.replace("new_region_", "")
    await state.update_data(macro_region=region)
    
    keyboard = await create_industry_keyboard(region=region, for_search=False)
    await callback.message.edit_text("🏭 Выберите отрасль:", reply_markup=keyboard)
    await state.set_state(InsightForm.industry)
    await callback.answer()

@router.callback_query(InsightForm.industry, F.data.startswith("new_industry_"))
async def process_industry(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора отрасли"""
    industry = callback.data.replace("new_industry_", "")
    await state.update_data(industry=industry)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📎 Прикрепить файл", callback_data="attach_file")
    builder.button(text="⏭️ Пропустить", callback_data="skip_file")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📎 Хотите прикрепить файл к инсайту?\n\n"
        "Вы можете отправить документ или фотографию.",
        reply_markup=builder.as_markup()
    )
    await state.set_state(InsightForm.file_attachment)
    await callback.answer()

@router.callback_query(InsightForm.file_attachment, F.data == "attach_file")
async def ready_for_file(callback: CallbackQuery):
    """Подготовка к получению файла"""
    await callback.message.edit_text(
        "📤 Отправьте файл (документ или фото).\n"
        "Используйте /skip для пропуска."
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
        logger.info(f"User {message.from_user.id} created insight with document")
        await message.answer("✅ Инсайт успешно создан с документом!", 
                           reply_markup=await create_main_keyboard())
    except Exception as e:
        logger.error(f"Error saving insight: {e}")
        await message.answer("❌ Ошибка при сохранении инсайта")
    
    await state.clear()

@router.message(InsightForm.file_attachment, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка прикрепленной фотографии"""
    file_id = message.photo[-1].file_id
    
    await state.update_data(file_id=file_id, filename=None)
    
    data = await state.get_data()
    try:
        await save_insight_to_db(data, message.from_user.id)
        logger.info(f"User {message.from_user.id} created insight with photo")
        await message.answer("✅ Инсайт успешно создан с фото!", 
                           reply_markup=await create_main_keyboard())
    except Exception as e:
        logger.error(f"Error saving insight: {e}")
        await message.answer("❌ Ошибка при сохранении инсайта")
    
    await state.clear()

@router.callback_query(InsightForm.file_attachment, F.data == "skip_file")
async def skip_file(callback: CallbackQuery, state: FSMContext):
    """Пропуск прикрепления файла"""
    data = await state.get_data()
    try:
        await save_insight_to_db(data, callback.from_user.id)
        logger.info(f"User {callback.from_user.id} created insight without file")
        await callback.message.edit_text(
            "✅ Инсайт успешно создан!",
            reply_markup=await create_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Error saving insight: {e}")
        await callback.message.edit_text("❌ Ошибка при сохранении инсайта")
    
    await state.clear()
    await callback.answer()

# ==================== ПОИСК И ПРОСМОТР ====================

@router.callback_query(F.data == "search_insights")
async def search_start(callback: CallbackQuery, state: FSMContext):
    """Начало поиска"""
    logger.info(f"User {callback.from_user.id} started searching")
    keyboard = await create_region_keyboard(for_search=True)
    await callback.message.edit_text("🗺️ Выберите макрорегион для фильтрации:", 
                                     reply_markup=keyboard)
    await state.set_state(SearchForm.macro_region)
    await callback.answer()

@router.callback_query(SearchForm.macro_region, F.data.startswith("search_region_"))
async def search_region_selected(callback: CallbackQuery, state: FSMContext):
    """Выбор макрорегиона в поиске"""
    region = callback.data.replace("search_region_", "")
    await state.update_data(macro_region=region)
    
    keyboard = await create_industry_keyboard(region=region, for_search=True)
    await callback.message.edit_text("🏭 Выберите отрасль:", reply_markup=keyboard)
    await state.set_state(SearchForm.industry)
    await callback.answer()

@router.callback_query(SearchForm.industry, F.data.startswith("search_industry_"))
async def search_industry_selected(callback: CallbackQuery, state: FSMContext):
    """Выбор отрасли в поиске и вывод результатов"""
    industry = callback.data.replace("search_industry_", "")
    await state.update_data(industry=industry)
    
    data = await state.get_data()
    filters = {
        "macro_region": data.get("macro_region"),
        "industry": industry
    }
    
    try:
        insights = await get_filtered_insights(filters)
        logger.info(f"User {callback.from_user.id} found {len(insights)} insights")
        
        if not insights:
            await callback.message.edit_text(
                "😔 По данным фильтрам записей не найдено.",
                reply_markup=InlineKeyboardBuilder()
                .button(text="⬅️ Назад", callback_data="back_to_main")
                .as_markup()
            )
            await state.clear()
            await callback.answer()
            return
        
        # Показываем первый инсайт
        await show_insight(callback.message, insights[0], insights, 0, state)
        await state.update_data(insights=insights, current_index=0)
        await state.set_state(SearchForm.viewing)
    except Exception as e:
        logger.error(f"Error searching insights: {e}")
        await callback.message.edit_text("❌ Ошибка при поиске инсайтов")
    
    await callback.answer()

async def show_insight(message, insight, insights_list, index, state):
    """Показать один инсайт с навигацией"""
    insight_text = (
        f"📌 Инсайт {index + 1} из {len(insights_list)}\n\n"
        f"📅 Дата: {insight['created_at'][:10]}\n"
        f"📝 Тема: {insight['theme']}\n"
        f"📄 Описание: {insight['description']}\n"
        f"🗺️ Макрорегион: {insight['macro_region']}\n"
        f"🏭 Отрасль: {insight['industry']}"
    )
    
    builder = InlineKeyboardBuilder()
    
    if index > 0:
        builder.button(text="⬅️ Назад", callback_data="prev_insight")
    
    if index < len(insights_list) - 1:
        builder.button(text="Вперед ➡️", callback_data="next_insight")
    
    if insight.get('file_id'):
        builder.button(text="📎 Скачать файл", callback_data="download_file")
    
    builder.button(text="🔙 В меню", callback_data="back_to_main")
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
            logger.error(f"Error downloading file: {e}")
            await callback.answer("❌ Ошибка при скачивании файла", show_alert=True)
    
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
            caption=f"📊 Экспорт инсайтов ({len(insights)} записей)"
        )
        
        logger.info(f"Export completed for user {callback.from_user.id}")
        
        # Удаляем временный файл
        if os.path.exists(filename):
            os.remove(filename)
    
    except Exception as e:
        logger.error(f"Export error for user {callback.from_user.id}: {e}")
        await callback.answer("❌ Ошибка при экспорте данных", show_alert=True)
    
    await callback.answer()

# ==================== MAIN ====================

async def main():
    """Запуск бота в режиме polling"""
    logger.info("🤖 Запуск бота в режиме polling")
    logger.info("✅ Бот слушает сообщения...")
    
    # Регистрация роутера
    dp.include_router(router)
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
