# ===============================================================
# Файл: bot/utils/dependencies.py (НОВЫЙ ФАЙЛ, КЛЮЧЕВОЙ)
# Описание: Централизованное управление зависимостями (DI).
# Создает и хранит единственные экземпляры (singletons) всех
# основных компонентов бота для всего приложения.
# ===============================================================

import logging
from typing import Optional
import aiohttp
import redis.asyncio as redis
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from openai import AsyncOpenAI

# Импортируем все наши сервисы и настройки
from bot.config.settings import AppSettings, settings
from bot.services.admin_service import AdminService
from bot.services.ai_content_service import AIContentService
from bot.services.asic_service import AsicService
from bot.services.coin_list_service import CoinListService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.market_data_service import MarketDataService
from bot.services.mining_game_service import MiningGameService
from bot.services.mining_service import MiningService
from bot.services.news_service import NewsService
from bot.services.parser_service import ParserService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.services.security_service import SecurityService
from bot.services.stop_word_service import StopWordService
from bot.services.user_service import UserService

logger = logging.getLogger(__name__)

# --- Контейнер для хранения глобальных экземпляров ---

class DependencyContainer:
    """Хранит синглтон-экземпляры всех зависимостей."""
    def __init__(self):
        self.settings: Optional[AppSettings] = None
        self.bot: Optional[Bot] = None
        self.dispatcher: Optional[Dispatcher] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.redis_client: Optional[redis.Redis] = None
        self.openai_client: Optional[AsyncOpenAI] = None
        
        # Сервисы
        self.admin_service: Optional[AdminService] = None
        self.user_service: Optional[UserService] = None
        self.parser_service: Optional[ParserService] = None
        self.asic_service: Optional[AsicService] = None
        self.market_data_service: Optional[MarketDataService] = None
        self.mining_service: Optional[MiningService] = None
        self.coin_list_service: Optional[CoinListService] = None
        self.price_service: Optional[PriceService] = None
        self.news_service: Optional[NewsService] = None
        self.ai_content_service: Optional[AIContentService] = None
        self.crypto_center_service: Optional[CryptoCenterService] = None
        self.quiz_service: Optional[QuizService] = None
        self.mining_game_service: Optional[MiningGameService] = None
        self.stop_word_service: Optional[StopWordService] = None
        self.security_service: Optional[SecurityService] = None

    def build(self):
        """Создает и настраивает все зависимости."""
        self.settings = settings
        
        self.bot = Bot(token=self.settings.api_keys.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
        self.redis_client = redis.from_url(self.settings.database.redis_url, decode_responses=True)
        self.http_session = aiohttp.ClientSession()
        
        if self.settings.api_keys.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.settings.api_keys.openai_api_key)

        # --- Инициализация сервисов в правильном порядке ---
        self.admin_service = AdminService(self.redis_client)
        self.user_service = UserService(self.redis_client, self.settings)
        self.parser_service = ParserService(self.http_session, self.settings.parser)
        self.asic_service = AsicService(self.redis_client, self.parser_service)
        self.market_data_service = MarketDataService(self.http_session, self.redis_client, self.settings.api_keys, self.settings.parser)
        self.mining_service = MiningService(self.market_data_service)
        self.coin_list_service = CoinListService(self.redis_client, self.http_session, self.settings.parser)
        self.price_service = PriceService(self.coin_list_service, self.redis_client, self.http_session)
        self.news_service = NewsService(self.http_session, self.settings.news)
        
        self.ai_content_service = AIContentService(
            self.settings.api_keys, 
            self.http_session, 
            self.openai_client
        )
        self.crypto_center_service = CryptoCenterService(
            self.redis_client, 
            self.news_service, 
            self.ai_content_service
        )
        self.quiz_service = QuizService(self.ai_content_service)
        self.mining_game_service = MiningGameService(self.redis_client, self.settings, self.admin_service)
        self.stop_word_service = StopWordService(self.redis_client)
        self.security_service = SecurityService(self.ai_content_service, self.settings.security)

        logger.info("Контейнер зависимостей успешно построен.")

    async def close(self):
        """Корректно закрывает все соединения."""
        if self.http_session:
            await self.http_session.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.bot:
            await self.bot.session.close()
        logger.info("Все соединения в контейнере зависимостей закрыты.")

# --- Создаем глобальный экземпляр контейнера ---
dependencies = DependencyContainer()

# --- Геттеры для доступа к зависимостям из любой точки приложения ---
# Это позволяет фоновым задачам получать актуальные экземпляры

def get_bot() -> Bot:
    return dependencies.bot

def get_dispatcher() -> Dispatcher:
    return dependencies.dispatcher

def get_redis_client() -> redis.Redis:
    return dependencies.redis_client

def get_settings() -> AppSettings:
    return dependencies.settings

def get_admin_service() -> AdminService:
    return dependencies.admin_service
    
def get_asic_service() -> AsicService:
    return dependencies.asic_service

def get_news_service() -> NewsService:
    return dependencies.news_service

def get_market_data_service() -> MarketDataService:
    return dependencies.market_data_service
