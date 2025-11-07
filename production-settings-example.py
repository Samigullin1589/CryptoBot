# Production Configuration Example
# Скопируйте эти настройки в ваш bot/config/settings.py

import os
from typing import List

class Settings:
    """Production settings for Render deployment"""
    
    # ============== TELEGRAM ==============
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    ADMIN_IDS: List[int] = [
        int(id.strip()) 
        for id in os.getenv('ADMIN_IDS', '').split(',') 
        if id.strip()
    ]
    
    # ============== REDIS ==============
    # Render автоматически предоставляет эту переменную
    REDIS_URL: str = os.getenv('REDIS_URL', 'redis://localhost:6379')
    REDIS_DB: int = int(os.getenv('REDIS_DB', '0'))
    REDIS_POOL_SIZE: int = int(os.getenv('REDIS_POOL_SIZE', '10'))
    
    # ============== DATABASE ==============
    # Опционально, если используете PostgreSQL
    DATABASE_URL: str = os.getenv('DATABASE_URL', '')
    
    # ============== AI SERVICES ==============
    ANTHROPIC_API_KEY: str = os.getenv('ANTHROPIC_API_KEY', '')
    
    # ============== ENVIRONMENT ==============
    ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'production')
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # ============== LOGGING ==============
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # ============== HEALTH CHECK ==============
    HEALTH_CHECK_PORT: int = int(os.getenv('PORT', '10000'))
    
    # ============== WEBHOOK ==============
    # Для production рекомендуется webhook вместо polling
    WEBHOOK_MODE: bool = os.getenv('WEBHOOK_MODE', 'False').lower() == 'true'
    WEBHOOK_URL: str = os.getenv('WEBHOOK_URL', '')  # https://your-app.onrender.com
    WEBHOOK_PATH: str = '/webhook'
    
    # ============== RATE LIMITING ==============
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_MESSAGES: int = int(os.getenv('RATE_LIMIT_MESSAGES', '20'))
    RATE_LIMIT_PERIOD: int = int(os.getenv('RATE_LIMIT_PERIOD', '60'))  # seconds
    
    # ============== CACHING ==============
    CACHE_TTL: int = int(os.getenv('CACHE_TTL', '3600'))  # 1 hour
    CACHE_ENABLED: bool = True
    
    # ============== SECURITY ==============
    ALLOWED_UPDATES: List[str] = ['message', 'callback_query']
    
    @classmethod
    def validate(cls):
        """Проверка обязательных настроек"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required!")
        
        if not cls.ADMIN_IDS:
            raise ValueError("At least one ADMIN_ID is required!")
        
        if cls.WEBHOOK_MODE and not cls.WEBHOOK_URL:
            raise ValueError("WEBHOOK_URL is required when WEBHOOK_MODE is enabled!")
        
        return True

    @classmethod
    def is_production(cls) -> bool:
        """Проверка production режима"""
        return cls.ENVIRONMENT == 'production'
    
    @classmethod
    def is_development(cls) -> bool:
        """Проверка development режима"""
        return cls.ENVIRONMENT == 'development'


# ============== ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ ==============

class RedisKeys:
    """Ключи для Redis"""
    USER_DATA = "user:{user_id}"
    USER_STATE = "state:{user_id}"
    CACHE = "cache:{key}"
    RATE_LIMIT = "ratelimit:{user_id}"
    SESSION = "session:{user_id}"


class Timeouts:
    """Таймауты для различных операций"""
    API_REQUEST = 30  # seconds
    REDIS_OPERATION = 5  # seconds
    DATABASE_QUERY = 10  # seconds


# ============== ИСПОЛЬЗОВАНИЕ ==============

"""
В main.py:

from bot.config.settings import Settings

# Валидация настроек при запуске
Settings.validate()

# Использование
if Settings.is_production():
    logger.info("Running in PRODUCTION mode")
    
bot = Bot(token=Settings.BOT_TOKEN)
redis_client = Redis.from_url(Settings.REDIS_URL)
"""