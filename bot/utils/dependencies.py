# bot/utils/dependencies.py
# =================================================================================
# Файл: bot/utils/dependencies.py (ВЕРСИЯ "Distinguished Engineer" - АВГУСТ 2025)
# Описание: Самодостаточный DI-контейнер на базе Pydantic для aiogram 3.
# Обеспечивает строгую типизацию, ленивую инициализацию и четкое разделение
# ответственности. Соответствует лучшим практикам разработки.
# =================================================================================

from typing import cast

from aiohttp import ClientSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from bot.config.settings import Settings
from bot.services.user_service import UserService
from bot.services.asic_service import AsicService
from bot.services.parser_service import ParserService
from bot.services.price_service import PriceService
from bot.services.coin_list_service import CoinListService
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


class Deps(BaseModel):
    """
    Pydantic-модель, агрегирующая все зависимости приложения.
    Используется для автоматического внедрения зависимостей в хэндлеры aiogram.
    """
    # --- Основные ресурсы ---
    settings: Settings
    http_session: ClientSession
    redis_pool: Redis
    # Планировщик создается с 'ленивой' фабрикой, чтобы не инициализировать его глобально.
    scheduler: AsyncIOScheduler = Field(default_factory=lambda: AsyncIOScheduler(timezone="UTC"))

    # --- Сервисы (расположены в порядке инициализации) ---
    # Уровень 1: Базовые сервисы без зависимостей от других сервисов
    user_service: UserService
    admin_service: AdminService
    quiz_service: QuizService
    event_service: MiningEventService
    achievement_service: AchievementService
    market_data_service: MarketDataService
    news_service: NewsService
    parser_service: ParserService
    ai_content_service: AIContentService

    # Уровень 2: Сервисы, зависящие от сервисов 1-го уровня
    security_service: SecurityService
    coin_list_service: CoinListService
    asic_service: AsicService
    
    # Уровень 3: Сервисы, зависящие от сервисов 2-го уровня
    price_service: PriceService
    crypto_center_service: CryptoCenterService
    market_service: AsicMarketService
    
    # Уровень 4: Сервис-агрегатор (игровой движок)
    mining_game_service: MiningGameService

    class Config:
        # Разрешаем Pydantic работать со сложными типами, которые не являются моделями Pydantic.
        arbitrary_types_allowed = True

    @classmethod
    def build(cls, settings: Settings, http_session: ClientSession, redis_pool: Redis) -> "Deps":
        """
        Фабричный метод для сборки контейнера зависимостей.
        Гарантирует, что все сервисы создаются в правильном порядке,
        передавая им необходимые зависимости (другие сервисы или ресурсы).
        """
        # --- Уровень 1: Инициализация базовых сервисов ---
        user_service = UserService(redis=redis_pool)
        # Временное 'cast', т.к. сам bot еще не создан. В сервисе он используется для отправки сообщений.
        # В реальном коде сервиса нужно будет получать bot из хэндлера.
        admin_service = AdminService(redis=redis_pool, settings=settings, bot=cast("Bot", None))
        quiz_service = QuizService(config=settings.quiz)
        event_service = MiningEventService(config=settings.events)
        achievement_service = AchievementService(redis=redis_pool, config=settings.achievements)
        market_data_service = MarketDataService(redis=redis_pool, http_session=http_session, config=settings.market_data)
        news_service = NewsService(redis=redis_pool, http_session=http_session, config=settings.news_service)
        parser_service = ParserService(http_session=http_session, endpoints=settings.endpoints)
        ai_content_service = AIContentService(config=settings.ai)

        # --- Уровень 2: Инициализация сервисов, зависящих от Уровня 1 ---
        security_service = SecurityService(ai_service=ai_content_service, config=settings.threat_filter)
        coin_list_service = CoinListService(redis=redis_pool, http_session=http_session, config=settings.coin_list_service, endpoints=settings.endpoints)
        asic_service = AsicService(redis=redis_pool, parser_service=parser_service, config=settings.asic_service)

        # --- Уровень 3: Инициализация сервисов, зависящих от Уровня 2 ---
        price_service = PriceService(redis=redis_pool, http_session=http_session, coin_list_service=coin_list_service, config=settings.price_service, endpoints=settings.endpoints)
        crypto_center_service = CryptoCenterService(redis=redis_pool, ai_service=ai_content_service, news_service=news_service, config=settings.crypto_center)
        market_service = AsicMarketService(redis=redis_pool, settings=settings, achievement_service=achievement_service, bot=cast("Bot", None))

        # --- Уровень 4: Инициализация сервисов верхнего уровня ---
        mining_game_service = MiningGameService(
            redis=redis_pool,
            scheduler=cast(AsyncIOScheduler, None), # Планировщик будет добавлен в main
            settings=settings,
            user_service=user_service,
            market_service=market_service,
            event_service=event_service,
            achievement_service=achievement_service,
            bot=cast("Bot", None)
        )

        # Сборка финального объекта Deps
        return cls(
            settings=settings,
            http_session=http_session,
            redis_pool=redis_pool,
            user_service=user_service,
            admin_service=admin_service,
            quiz_service=quiz_service,
            event_service=event_service,
            achievement_service=achievement_service,
            market_data_service=market_data_service,
            news_service=news_service,
            parser_service=parser_service,
            ai_content_service=ai_content_service,
            security_service=security_service,
            coin_list_service=coin_list_service,
            asic_service=asic_service,
            price_service=price_service,
            crypto_center_service=crypto_center_service,
            market_service=market_service,
            mining_game_service=mining_game_service
        )
