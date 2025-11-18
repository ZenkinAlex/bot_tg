import os
import logging
from supabase import create_client, Client
from decouple import config
from datetime import datetime

logger = logging.getLogger(__name__)

# Инициализация Supabase
SUPABASE_URL = config('SUPABASE_URL')
SUPABASE_KEY = config('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def init_database():
    """Инициализация таблицы в БД (выполнить один раз)"""
    try:
        # Таблица уже должна быть создана в Supabase через UI
        # Но вот SQL для создания на случай:
        sql = """
        CREATE TABLE IF NOT EXISTS insights (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            theme VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            macro_region VARCHAR(50) NOT NULL,
            industry VARCHAR(100) NOT NULL,
            file_id VARCHAR(255),
            filename VARCHAR(255),
            user_id BIGINT NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_macro_region ON insights(macro_region);
        CREATE INDEX IF NOT EXISTS idx_industry ON insights(industry);
        CREATE INDEX IF NOT EXISTS idx_user_id ON insights(user_id);
        """
        logger.info("Database schema is ready")
    except Exception as e:
        logger.error(f"Database init error: {e}")

async def save_insight_to_db(data: dict, user_id: int):
    """Сохранение инсайта в базу данных"""
    try:
        response = supabase.table("insights").insert({
            "theme": data.get("theme"),
            "description": data.get("description"),
            "macro_region": data.get("macro_region"),
            "industry": data.get("industry"),
            "file_id": data.get("file_id"),
            "filename": data.get("filename"),
            "user_id": user_id
        }).execute()
        
        logger.info(f"Insight saved: {data.get('theme')} by user {user_id}")
        return response.data
    except Exception as e:
        logger.error(f"Error saving insight: {e}")
        raise

async def get_count_by_field(field: str, value: str):
    """Подсчет количества записей по полю"""
    try:
        response = supabase.table("insights")\
            .select("id", count="exact")\
            .eq(field, value)\
            .execute()
        
        return response.count if response.count else 0
    except Exception as e:
        logger.error(f"Error counting by {field}={value}: {e}")
        return 0

async def get_all_insights():
    """Получение всех записей для экспорта"""
    try:
        response = supabase.table("insights")\
            .select("*")\
            .order("created_at", desc=True)\
            .execute()
        
        logger.info(f"Retrieved {len(response.data)} insights")
        return response.data
    except Exception as e:
        logger.error(f"Error getting all insights: {e}")
        return []

async def get_filtered_insights(filters: dict):
    """Получение отфильтрованных записей"""
    try:
        query = supabase.table("insights").select("*")
        
        if filters.get("macro_region"):
            query = query.eq("macro_region", filters["macro_region"])
        
        if filters.get("industry"):
            query = query.eq("industry", filters["industry"])
        
        response = query.order("created_at", desc=True).execute()
        
        logger.info(f"Retrieved {len(response.data)} filtered insights")
        return response.data
    except Exception as e:
        logger.error(f"Error getting filtered insights: {e}")
        return []

async def get_insight_by_id(insight_id: int):
    """Получение инсайта по ID"""
    try:
        response = supabase.table("insights")\
            .select("*")\
            .eq("id", insight_id)\
            .single()\
            .execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Error getting insight {insight_id}: {e}")
        return None

async def delete_insight(insight_id: int, user_id: int):
    """Удаление инсайта (только владельцем)"""
    try:
        response = supabase.table("insights")\
            .delete()\
            .eq("id", insight_id)\
            .eq("user_id", user_id)\
            .execute()
        
        logger.info(f"Insight {insight_id} deleted by user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting insight: {e}")
        return False

async def get_user_insights(user_id: int):
    """Получение всех инсайтов пользователя"""
    try:
        response = supabase.table("insights")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Error getting user insights: {e}")
        return []

async def get_stats():
    """Получение статистики по БД"""
    try:
        # Общее количество
        total = supabase.table("insights")\
            .select("id", count="exact")\
            .execute()
        
        # По регионам
        regions_response = supabase.rpc('get_region_stats').execute()
        
        # По отраслям
        industries_response = supabase.rpc('get_industry_stats').execute()
        
        return {
            "total": total.count,
            "by_regions": regions_response.data if hasattr(regions_response, 'data') else [],
            "by_industries": industries_response.data if hasattr(industries_response, 'data') else []
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {
            "total": 0,
            "by_regions": [],
            "by_industries": []
        }
