# =================================================================================
# Файл: bot/utils/dependencies.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ, ИСПРАВЛЕННАЯ)
# Описание: DI-контейнер, поддерживающий асинхронную инициализацию сервисов.
# ИСПРАВЛЕНИЕ: Устранена проблема с передачей зависимостей в CoinListService
# для обеспечения работы с PRO API ключом.
# =================================================================================

import aiohttp
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from bot.config.settings import Settings
from bot.services.user_service import UserService
from bot.services.admin_service import AdminService
from bot.services.ai_content_service import AIContentService
from bot.services.news_service import NewsService
from bot.services.parser_service import ParserService
from bot.services.security_service import SecurityService
from bot.services.coin_list_service import CoinListService
from bot.services.price_service import PriceService
from bot.services.asic_service import AsicService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.quiz_service import QuizService
from bot.services.market_data_service import MarketDataService
from bot.services.event_service import MiningEventService
from bot.services.achievement_service import AchievementService
from bot.services.market_service import AsicMarketService
from bot.services.mining_game_service import MiningGameService


class Deps(BaseModel):
    settings: Settings
    http_session: aiohttp.ClientSession
    redis_pool: Redis
    scheduler: AsyncIOScheduler = Field(default_factory=lambda: AsyncIOScheduler(timezone="UTC"))
    bot: Bot
    user_service: UserService
    admin_service: AdminService
    ai_content_service: AIContentService
    news_service: NewsService
    parser_service: ParserService
    quiz_service: QuizService
    event_service: MiningEventService
    achievement_service: AchievementService
    market_data_service: MarketDataService
    security_service: SecurityService
    coin_list_service: CoinListService
    asic_service: AsicService
    price_service: PriceService
    crypto_center_service: CryptoCenterService
    market_service: AsicMarketService
    mining_game_service: MiningGameService

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    async def build(cls, settings: Settings, http_session: aiohttp.ClientSession, redis_pool: Redis, bot: Bot) -> "Deps":
        """
        Асинхронный фабричный метод для сборки и настройки контейнера зависимостей.
        """
        # --- Сначала создаем все экземпляры синхронно ---
        user_service = UserService(redis=redis_pool)
        admin_service = AdminService(redis=redis_pool, settings=settings, bot=bot)
        ai_content_service = AIContentService(api_key=settings.GEMINI_API_KEY.get_secret_value(), config=settings.ai)
        news_service = NewsService(redis=redis_pool, http_session=http_session, config=settings.news_service)
        parser_service = ParserService(http_session=http_session, config=settings.endpoints)
        quiz_service = QuizService(ai_content_service=ai_content_service, config=settings.quiz)
        event_service = MiningEventService(config=settings.events)
        market_data_service = MarketDataService(redis=redis_pool, http_session=http_session, config=settings.market_data, endpoints=settings.endpoints)
        achievement_service = AchievementService(redis=redis_pool, config=settings.achievements, market_data_service=market_data_service)
        security_service = SecurityService(ai_service=ai_content_service, config=settings.threat_filter)

        # ======================= КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ =======================
        # Передаем весь объект settings, а не его части.
        # Это позволяет сервису получить доступ к COINGECKO_API_KEY и другим настройкам.
        coin_list_service = CoinListService(redis=redis_pool, http_session=http_session, settings=settings)
        # =====================================================================

        asic_service = AsicService(redis=redis_pool, parser_service=parser_service, config=settings.asic_service)

        price_service = PriceService(
            redis=redis_pool,
            http_session=http_session,
            config=settings.price_service,
            endpoints=settings.endpoints
        )

        crypto_center_service = CryptoCenterService(redis=redis_pool, ai_service=ai_content_service, news_service=news_service, config=settings.crypto_center)
        market_service = AsicMarketService(redis=redis_pool, settings=settings, achievement_service=achievement_service, bot=bot)
        scheduler_instance = AsyncIOScheduler(timezone="UTC")
        mining_game_service = MiningGameService(
            redis=redis_pool, scheduler=scheduler_instance, settings=settings, user_service=user_service,
            market_service=market_service, event_service=event_service, achievement_service=achievement_service, bot=bot
        )

        # --- Затем асинхронно настраиваем те, которым это нужно ---
        await market_service.setup()
        await mining_game_service.setup()

        # Сборка финального объекта Deps
        return cls(
            settings=settings, http_session=http_session, redis_pool=redis_pool, scheduler=scheduler_instance,
            bot=bot, user_service=user_service, admin_service=admin_service, ai_content_service=ai_content_service,
            news_service=news_service, parser_service=parser_service, quiz_service=quiz_service,
            event_service=event_service, achievement_service=achievement_service, market_data_service=market_data_service,
            security_service=security_service, coin_list_service=coin_list_service, asic_service=asic_service,
            price_service=price_service, crypto_center_service=crypto_center_service, market_service=market_service,
            mining_game_service=mining_game_service
        )