# =================================================================================
# Файл: bot/utils/dependencies.py (ВЕРСИЯ "ГЕНИЙ 5.0" - АВГУСТ 2025 - ПРОДАКШН)
# Описание: Самодостаточный DI-контейнер. Полная инициализация всех компонентов системы.
# =================================================================================

import json
import logging
from pathlib import Path
import sys

import aiohttp
import redis.asyncio as redis
import google.generativeai as genai
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

# Импортируем глобальные настройки
from bot.config.settings import settings
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.middlewares.action_tracking_middleware import ActionTrackingMiddleware

# Импортируем абсолютно все сервисы для обеспечения целостности DI
from bot.services.user_service import UserService
from bot.services.asic_service import AsicService
from bot.services.parser_service import ParserService
from bot.services.price_service import PriceService
from bot.services.coin_list_service import CoinListService # Необходим для PriceService
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
    Центральный DI-контейнер.
    """
    def __init__(self, settings):
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
        logging.info("Инициализация зависимостей...")

        # --- Базовые компоненты ---
        self.http_session = aiohttp.ClientSession()
        
        # Надежное подключение к Redis с проверкой соединения (Fail Fast)
        try:
            self.redis_client = redis.from_url(self.settings.REDIS_URL, decode_responses=True)
            await self.redis_client.ping()
            logging.info("Соединение с Redis установлено успешно.")
        except Exception as e:
            logging.critical(f"Не удалось подключиться к Redis по URL {self.settings.REDIS_URL}: {e}")
            # Приложение не может работать без Redis
            sys.exit(1)

        self.storage = RedisStorage(redis=self.redis_client)
        self.bot = Bot(token=self.settings.BOT_TOKEN.get_secret_value(), parse_mode="HTML")
        self.dp = Dispatcher(storage=self.storage)

        # --- Инициализация Google Gemini ---
        if self.settings.GEMINI_API_KEY and self.settings.GEMINI_API_KEY.get_secret_value():
            try:
                genai.configure(api_key=self.settings.GEMINI_API_KEY.get_secret_value())
                logging.info("Google Gemini SDK сконфигурирован.")
            except Exception as e:
                logging.error(f"Ошибка при конфигурации Google Gemini SDK: {e}. AI функции будут недоступны.")
        else:
            logging.warning("GEMINI_API_KEY отсутствует или пуст. AI функции будут отключены.")

        # --- Инициализация APScheduler ---
        # Надежное получение параметров подключения Redis для JobStore
        redis_kwargs = self.redis_client.connection_pool.connection_kwargs
        jobstores = {"default": RedisJobStore(
            jobs_key="scheduler_jobs", run_times_key="scheduler_run_times",
            host=redis_kwargs.get('host', 'localhost'), port=redis_kwargs.get('port', 6379),
            db=redis_kwargs.get('db', 0), password=redis_kwargs.get('password')
        )}
        self.scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
        logging.info("Планировщик задач APScheduler инициализирован с RedisJobStore.")

        # --- Инициализация сервисов ---
        self._initialize_services()

        # --- Передача зависимостей в Dispatcher (workflow_data) ---
        self.workflow_data.update({
            "bot": self.bot, "dp": self.dp, "scheduler": self.scheduler, "http_session": self.http_session,
            "user_service": self.user_service, "asic_service": self.asic_service, "price_service": self.price_service,
            "news_service": self.news_service, "quiz_service": self.quiz_service, "market_data_service": self.market_data_service,
            "ai_content_service": self.ai_content_service, "security_service": self.security_service,
            "crypto_center_service": self.crypto_center_service, "mining_game_service": self.mining_game_service,
            "market_service": self.market_service, "event_service": self.event_service,
            "achievement_service": self.achievement_service, "admin_service": self.admin_service,
            "parser_service": self.parser_service,
            "coin_list_service": self.coin_list_service # Включен CoinListService
        })
        logging.info("Все сервисы переданы в workflow_data диспетчера.")

    def _initialize_services(self):
        """Создает экземпляры всех сервисов в правильном порядке зависимостей."""
        logging.info("Создание экземпляров сервисов...")

        # 1. Сервисы нижнего уровня (Инфраструктурные и базовые)
        self.ai_content_service = AIContentService()
        self.user_service = UserService(redis_client=self.redis_client)
        self.admin_service = AdminService(redis_client=self.redis_client, settings=self.settings, bot=self.bot)
        self.quiz_service = QuizService(config_path=Path("data/quiz_config.json"))
        self.event_service = MiningEventService(config_path=Path("data/events_config.json"))
        self.achievement_service = AchievementService(redis_client=self.redis_client, config_path=Path("data/achievements_config.json"))
        self.market_data_service = MarketDataService(redis_client=self.redis_client, http_session=self.http_session, config_path=Path("data/market_data_config.json"))
        self.news_service = NewsService(redis_client=self.redis_client, settings=self.settings)

        # 2. Сервисы, зависящие от уровня 1
        self.security_service = SecurityService(ai_service=self.ai_content_service, config_path=Path("data/threat_filter_config.json"))
        
        self.parser_service = ParserService(
            http_session=self.http_session,
            config=self.settings.endpoints
        )
        
        # Инициализация CoinListService
        self.coin_list_service = CoinListService(
            redis_client=self.redis_client,
            http_session=self.http_session,
            endpoints=self.settings.endpoints
        )

        # 3. Сервисы, зависящие от уровня 2
        self.asic_service = AsicService(
            redis_client=self.redis_client,
            parser_service=self.parser_service,
            config=self.settings.asic_service
        )
        
        # Инициализация PriceService (зависит от CoinListService)
        self.price_service = PriceService(
            redis_client=self.redis_client,
            http_session=self.http_session,
            coin_list_service=self.coin_list_service,
            config=self.settings.price_service,
            endpoints=self.settings.endpoints
        )

        self.crypto_center_service = CryptoCenterService(
            redis_client=self.redis_client, ai_service=self.ai_content_service,
            news_service=self.news_service, config=self.settings.crypto_center
        )

        self.market_service = AsicMarketService(
            redis_client=self.redis_client, settings=self.settings,
            achievement_service=self.achievement_service, bot=self.bot
        )

        # 4. Сервис верхнего уровня (Игровой движок)
        self.mining_game_service = MiningGameService(
            redis_client=self.redis_client, scheduler=self.scheduler, settings=self.settings,
            user_service=self.user_service, market_service=self.market_service,
            event_service=self.event_service, achievement_service=self.achievement_service, bot=self.bot
        )
        logging.info("Все сервисы успешно инициализированы.")

    # --- Middlewares ---
    
    @property
    def throttling_middleware(self):
        return ThrottlingMiddleware(storage=self.storage)

    @property
    def activity_middleware(self):
        return ActivityMiddleware(redis_client=self.redis_client)
    
    @property
    def action_tracking_middleware(self):
        return ActionTrackingMiddleware(redis_client=self.redis_client)

    async def close(self):
        """Graceful shutdown: Закрывает все открытые соединения."""
        logging.info("Начало процедуры Graceful Shutdown...")
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
            logging.info("HTTP сессия закрыта.")
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logging.info("Планировщик остановлен.")
        if self.bot:
            await self.bot.session.close()
            logging.info("Сессия бота закрыта.")
        if self.redis_client:
            await self.redis_client.close()
            logging.info("Соединение с Redis закрыто.")
        logging.info("Все соединения и ресурсы успешно закрыты.")

# Глобальный экземпляр контейнера
deps = Dependencies(settings)