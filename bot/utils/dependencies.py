# =================================================================================
# Файл: bot/utils/dependencies.py (ВЕРСИЯ "ГЕНИЙ 3.0" - АВГУСТ 2025)
# Описание: DI-контейнер. Исправлена инициализация AsicService и ParserService.
# =================================================================================

import json
import logging
from pathlib import Path

import aiohttp
import redis.asyncio as redis
import google.generativeai as genai
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

# Импортируем глобальные настройки, но внутри класса будем использовать self.settings
from bot.config.settings import settings 
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.middlewares.action_tracking_middleware import ActionTrackingMiddleware

# Импортируем абсолютно все сервисы
from bot.services.user_service import UserService
from bot.services.asic_service import AsicService

# >>>>> ИСПРАВЛЕНИЕ 1: Добавляем импорт ParserService (необходим для AsicService)
# Убедитесь, что этот импорт существует в вашей структуре проекта!
from bot.services.parser_service import ParserService 
# >>>>> КОНЕЦ ИСПРАВЛЕНИЯ 1

from bot.services.price_service import PriceService
from bot.services.news_service import NewsService
from bot.services.quiz_service import QuizService
from bot.services.market_data_service import MarketDataService
from bot.services.ai_content_service import AIContentService
from bot.services.security_service import SecurityService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.mining_game_service import MiningGameService
from bot.services.market_service import AsicMarketService
from bot.services.event_service import MiningEventService
from bot.services.achievement_service import AchievementService
from bot.services.admin_service import AdminService


class Dependencies:
    """
    Центральный DI-контейнер. Отвечает за создание и предоставление
    всех необходимых зависимостей для работы бота.
    """
    def __init__(self, settings):
        # Сохраняем настройки в экземпляре класса
        self.settings = settings 
        # Используем современный синтаксис Union (Стандарт 2025: T | None)
        self.http_session: aiohttp.ClientSession | None = None
        self.redis_client: redis.Redis | None = None
        self.storage: RedisStorage | None = None
        self.dp: Dispatcher | None = None
        self.bot: Bot | None = None
        self.scheduler: AsyncIOScheduler | None = None
        self.workflow_data: dict = {}

    async def initialize(self):
        """Асинхронно создает и инициализирует все зависимости."""
        logging.info("Инициализация зависимостей...")

        # --- Базовые компоненты ---
        self.http_session = aiohttp.ClientSession()
        # Используем self.settings
        self.redis_client = redis.from_url(self.settings.REDIS_URL, decode_responses=True) if self.settings.REDIS_URL else redis.Redis(decode_responses=True)
        self.storage = RedisStorage(redis=self.redis_client)
        self.bot = Bot(token=self.settings.BOT_TOKEN.get_secret_value(), parse_mode="HTML")
        self.dp = Dispatcher(storage=self.storage)

        # --- Инициализация Google Gemini ---
        if self.settings.GEMINI_API_KEY:
            # Проверяем, что ключ не пустой, прежде чем конфигурировать
            if self.settings.GEMINI_API_KEY.get_secret_value():
                genai.configure(api_key=self.settings.GEMINI_API_KEY.get_secret_value())
                logging.info("Google Gemini SDK сконфигурирован.")
            else:
                logging.warning("GEMINI_API_KEY указан в переменных окружения, но его значение пусто. AI функции могут работать некорректно.")
        else:
            logging.info("GEMINI_API_KEY не найден. AI функции будут отключены.")


        # --- Инициализация APScheduler ---
        # Более надежное получение параметров подключения Redis для JobStore
        redis_kwargs = self.redis_client.connection_pool.connection_kwargs
        jobstores = {"default": RedisJobStore(
            jobs_key="scheduler_jobs", 
            run_times_key="scheduler_run_times", 
            host=redis_kwargs.get('host', 'localhost'), 
            port=redis_kwargs.get('port', 6379),
            db=redis_kwargs.get('db', 0),
            password=redis_kwargs.get('password') # Добавлено для поддержки Redis с паролем
        )}
        self.scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
        logging.info("Планировщик задач APScheduler инициализирован с RedisJobStore.")

        # --- Инициализация сервисов ---
        self._initialize_services()

        # --- Передача зависимостей в Dispatcher ---
        self.workflow_data.update({
            "bot": self.bot,
            "dp": self.dp,
            "scheduler": self.scheduler,
            "http_session": self.http_session,
            "user_service": self.user_service,
            "asic_service": self.asic_service,
            "price_service": self.price_service,
            "news_service": self.news_service,
            "quiz_service": self.quiz_service,
            "market_data_service": self.market_data_service,
            "ai_content_service": self.ai_content_service,
            "security_service": self.security_service,
            "crypto_center_service": self.crypto_center_service,
            "mining_game_service": self.mining_game_service,
            "market_service": self.market_service,
            "event_service": self.event_service,
            "achievement_service": self.achievement_service,
            "admin_service": self.admin_service,
            # Добавляем parser_service, если он нужен в хэндлерах
            "parser_service": self.parser_service 
        })
        logging.info("Все сервисы переданы в workflow_data диспетчера.")

    def _initialize_services(self):
        """Создает экземпляры всех сервисов."""
        logging.info("Создание экземпляров сервисов...")

        # >>>>> ИСПРАВЛЕНИЕ 2: Инициализация ParserService (необходим для AsicService)
        # Предполагается, что ParserService зависит от http_session
        self.parser_service = ParserService(http_session=self.http_session)
        # >>>>> КОНЕЦ ИСПРАВЛЕНИЯ 2

        self.user_service = UserService(redis_client=self.redis_client)
        
        # Используем self.settings (Best Practice)
        # БЫЛО: self.admin_service = AdminService(redis_client=self.redis_client, settings=settings, bot=self.bot)
        self.admin_service = AdminService(redis_client=self.redis_client, settings=self.settings, bot=self.bot)
        
        # >>>>> ИСПРАВЛЕНИЕ 3: Корректная инициализация AsicService
        # БЫЛО: self.asic_service = AsicService(redis_client=self.redis_client)
        self.asic_service = AsicService(
            redis_client=self.redis_client,
            parser_service=self.parser_service,      # Передаем ParserService
            config=self.settings.asic_service        # Передаем конфигурацию (AsicServiceConfig)
        )
        # >>>>> КОНЕЦ ИСПРАВЛЕНИЯ 3
        
        self.price_service = PriceService(redis_client=self.redis_client)
        # Используем self.settings (Best Practice)
        self.news_service = NewsService(redis_client=self.redis_client, settings=self.settings)
        self.market_data_service = MarketDataService(redis_client=self.redis_client, http_session=self.http_session, config_path=Path("data/market_data_config.json"))
        self.quiz_service = QuizService(config_path=Path("data/quiz_config.json"))
        self.ai_content_service = AIContentService()
        self.security_service = SecurityService(ai_service=self.ai_content_service, config_path=Path("data/threat_filter_config.json"))

        # --- Сервисы из плана "Гений 2.0" ---
        self.crypto_center_service = CryptoCenterService(
            redis_client=self.redis_client,
            ai_service=self.ai_content_service,
            news_service=self.news_service,
            # Используем self.settings (Best Practice)
            config=self.settings.crypto_center
        )
        self.event_service = MiningEventService(config_path=Path("data/events_config.json"))
        self.achievement_service = AchievementService(redis_client=self.redis_client, config_path=Path("data/achievements_config.json"))
        self.market_service = AsicMarketService(
            redis_client=self.redis_client,
            # Используем self.settings (Best Practice)
            settings=self.settings,
            achievement_service=self.achievement_service,
            bot=self.bot
        )
        self.mining_game_service = MiningGameService(
            redis_client=self.redis_client,
            scheduler=self.scheduler,
            # Используем self.settings (Best Practice)
            settings=self.settings,
            user_service=self.user_service,
            market_service=self.market_service,
            event_service=self.event_service,
            achievement_service=self.achievement_service,
            bot=self.bot
        )
        logging.info("Все сервисы успешно инициализированы.")

    # Примечание: Middlewares также должны получать свои зависимости.
    
    @property
    def throttling_middleware(self):
        # Если ThrottlingMiddleware требует конфигурацию, её нужно передать сюда.
        return ThrottlingMiddleware(storage=self.storage)

    @property
    def activity_middleware(self):
        return ActivityMiddleware(redis_client=self.redis_client)
    
    @property
    def action_tracking_middleware(self):
        # В идеале, middleware должен зависеть от сервиса (например, AdminService), а не от Redis напрямую.
        # Но мы оставляем как есть, чтобы не сломать текущую реализацию middleware.
        return ActionTrackingMiddleware(redis_client=self.redis_client)

    async def close(self):
        """Закрывает все открытые соединения."""
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        if self.bot:
            await self.bot.session.close()
        logging.info("Все соединения и ресурсы успешно закрыты.")

# Глобальный экземпляр контейнера
# Инициализируем его с глобальным объектом settings, загруженным при запуске
deps = Dependencies(settings)