# ===============================================================
# Файл: bot/utils/dependencies.py (ПРОДАКШН-ВЕРСИЯ 2025 - ОКОНЧАТЕЛЬНАЯ v16)
# ===============================================================
import logging
import aiohttp
import redis.asyncio as redis
import google.generativeai as genai
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from typing import Dict, Any

from bot.config.settings import settings
from bot.services.admin_service import AdminService
from bot.services.asic_service import AsicService
from bot.services.coin_list_service import CoinListService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.market_data_service import MarketDataService
from bot.services.mining_game_service import MiningGameService
from bot.services.moderation_service import ModerationService
from bot.services.news_service import NewsService
from bot.services.parser_service import ParserService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.services.stop_word_service import StopWordService
from bot.services.user_service import UserService
from bot.services.ai_content_service import AIContentService
from bot.utils.scheduler import get_jobs
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.action_tracking_middleware import ActionTrackingMiddleware

class Dependencies:
    """Контейнер для всех зависимостей приложения."""
    def __init__(self, app_settings):
        self.settings = app_settings
        self.workflow_data: Dict[str, Any] = {"settings": self.settings}
        self.scheduler: AsyncIOScheduler = None
        self.bot: Bot = None
        self.http_session: aiohttp.ClientSession = None
        self.redis_client: redis.Redis = None
        self.gemini_client: genai.GenerativeModel = None

    async def initialize(self):
        """Асинхронно создает и инициализирует все зависимости."""
        self.redis_client = redis.from_url(self.settings.api_keys.redis_url, decode_responses=True)
        self.bot = Bot(token=self.settings.api_keys.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
        storage = RedisStorage(redis=self.redis_client)
        self.dp = Dispatcher(storage=storage)
        self.bot_info = await self.bot.get_me()
        self.http_session = aiohttp.ClientSession()
        jobstores = {'default': RedisJobStore(connection_pool=self.redis_client.connection_pool)}
        self.scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC", job_defaults={'misfire_grace_time': 300, 'replace_existing': True})
        jobs = get_jobs(self.settings)
        for job in jobs:
            if job.id == 'news_sending_job' and not self.settings.admin.news_chat_id:
                logging.warning("NEWS_CHAT_ID не установлен, задача 'news_sending_job' пропущена.")
                continue
            self.scheduler.add_job(job.func, trigger=job.trigger, id=job.id, args=[self], **job.config)
        logging.info("Планировщик настроен со всеми задачами.")
        if self.settings.api_keys.gemini_api_key:
            genai.configure(api_key=self.settings.api_keys.gemini_api_key)
            self.gemini_client = genai.GenerativeModel(self.settings.ai.default_model_name)
        else:
            self.gemini_client = None
        self._initialize_services()
        self._populate_workflow_data()


    def _initialize_services(self):
        """Создает экземпляры всех сервисов и middleware."""
        self.stop_word_service = StopWordService(redis_client=self.redis_client)
        self.user_service = UserService(redis_client=self.redis_client, settings=self.settings)
        self.admin_service = AdminService(bot=self.bot, redis_client=self.redis_client, settings=self.settings.admin)
        self.parser_service = ParserService(http_session=self.http_session, config=self.settings.endpoints)
        self.asic_service = AsicService(redis_client=self.redis_client, parser_service=self.parser_service, config=self.settings.asic_service)
        self.coin_list_service = CoinListService(
            redis_client=self.redis_client, http_session=self.http_session,
            config=self.settings.coin_list_service, endpoints=self.settings.endpoints,
            ticker_aliases=self.settings.ticker_aliases
        )
        self.price_service = PriceService(
            redis_client=self.redis_client, http_session=self.http_session,
            coin_list_service=self.coin_list_service, config=self.settings.price_service,
            endpoints=self.settings.endpoints
        )
        self.market_data_service = MarketDataService(
            redis_client=self.redis_client, http_session=self.http_session,
            config=self.settings.market_data_service, endpoints=self.settings.endpoints
        )
        self.ai_content_service = AIContentService(gemini_client=self.gemini_client, config=self.settings.ai)
        self.news_service = NewsService(
            redis_client=self.redis_client, http_session=self.http_session,
            config=self.settings.news_service, endpoints=self.settings.endpoints,
            api_keys=self.settings.api_keys, feeds=self.settings.news
        )
        self.crypto_center_service = CryptoCenterService(
            redis_client=self.redis_client, ai_service=self.ai_content_service,
            news_service=self.news_service, config=self.settings.crypto_center_service
        )
        self.mining_game_service = MiningGameService(
            redis_client=self.redis_client, admin_service=self.admin_service,
            scheduler=self.scheduler, settings=self.settings
        )
        self.moderation_service = ModerationService(
            bot=self.bot, user_service=self.user_service,
            admin_service=self.admin_service, stop_word_service=self.stop_word_service,
            config=self.settings.threat_filter
        )
        self.quiz_service = QuizService(
            ai_content_service=self.ai_content_service,
            fallback_questions=self.settings.fallback_quiz
        )
        
        # --- Middleware ---
        self.throttling_middleware = ThrottlingMiddleware(redis_client=self.redis_client, user_service=self.user_service, config=self.settings.throttling)
        self.activity_middleware = ActivityMiddleware(user_service=self.user_service)
        self.action_tracking_middleware = ActionTrackingMiddleware(admin_service=self.admin_service)

    def _populate_workflow_data(self):
        for attr_name, attr_value in self.__dict__.items():
            if not attr_name.startswith('_') and attr_name not in self.workflow_data and attr_value is not None:
                self.workflow_data[attr_name] = attr_value


    async def close(self):
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
        if self.http_session:
            await self.http_session.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.bot:
            await self.bot.session.close()


deps = Dependencies(settings)