# =================================================================================
# Файл: bot/utils/dependencies.py (ВЕРСИЯ "Distinguished Engineer" - ОТКАЗОУСТОЙЧИВАЯ)
# Описание: DI-контейнер с логированием и отказоустойчивым подключением к Redis.
# ИСПРАВЛЕНИЕ: Добавлена логика повторных попыток подключения к Redis при старте.
#              Подключены все недостающие сервисы для модерации.
# =================================================================================
import logging
import asyncio
import aiohttp
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel, Field
import redis.asyncio as redis

from bot.config.settings import settings, Settings
from bot.utils.keys import KeyFactory

# Импортируем все сервисы
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
from bot.services.verification_service import VerificationService
from bot.services.mining_service import MiningService
from bot.services.stop_word_service import StopWordService
from bot.services.moderation_service import ModerationService

logger = logging.getLogger(__name__)

class Deps(BaseModel):
    """Data Injection контейнер для всех сервисов и клиентов."""
    settings: Settings
    http_session: aiohttp.ClientSession
    redis_pool: redis.Redis
    scheduler: AsyncIOScheduler
    bot: Bot
    keys: KeyFactory = Field(default_factory=KeyFactory)

    # Все сервисы приложения
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
    verification_service: VerificationService
    mining_service: MiningService
    stop_word_service: StopWordService
    moderation_service: ModerationService

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    async def build(cls, settings: Settings, http_session: aiohttp.ClientSession, bot: Bot) -> "Deps":
        """Асинхронный фабричный метод для безопасной сборки и настройки контейнера зависимостей."""
        logger.info("Начало сборки контейнера зависимостей (Deps)...")
        
        # --- УЛУЧШЕНИЕ: Отказоустойчивое подключение к Redis ---
        redis_pool = None
        max_retries = 5
        retry_delay = 5  # seconds
        for attempt in range(max_retries):
            try:
                redis_pool = redis.from_url(str(settings.REDIS_URL), encoding="utf-8", decode_responses=True)
                await redis_pool.ping()
                logger.info("Успешное подключение к Redis.")
                break
            except redis.exceptions.ConnectionError as e:
                logger.warning(f"Не удалось подключиться к Redis (попытка {attempt + 1}/{max_retries}): {e}. Повтор через {retry_delay} сек...")
                if attempt + 1 == max_retries:
                    logger.critical("Не удалось подключиться к Redis после всех попыток. Остановка бота.")
                    raise
                await asyncio.sleep(retry_delay)
        
        try:
            # Инициализация базовых сервисов
            user_service = UserService(redis=redis_pool)
            admin_service = AdminService(redis=redis_pool, settings=settings, bot=bot)
            ai_content_service = AIContentService(api_key=settings.GEMINI_API_KEY.get_secret_value(), config=settings.ai)
            news_service = NewsService(redis=redis_pool, http_session=http_session, config=settings.news_service)
            parser_service = ParserService(http_session=http_session, config=settings.endpoints)
            quiz_service = QuizService(ai_content_service=ai_content_service)
            event_service = MiningEventService(config=settings.events)
            coin_list_service = CoinListService(redis=redis_pool, http_session=http_session, settings=settings)
            stop_word_service = StopWordService(redis_client=redis_pool)
            moderation_service = ModerationService(bot=bot, user_service=user_service, admin_service=admin_service,
                                                   stop_word_service=stop_word_service, config=settings.threat_filter)

            # Инициализация сервисов, зависящих от других
            market_data_service = MarketDataService(redis=redis_pool, http_session=http_session, settings=settings, coin_list_service=coin_list_service)
            mining_service = MiningService(market_data_service=market_data_service)
            achievement_service = AchievementService(redis=redis_pool, config=settings.achievements, market_data_service=market_data_service)
            security_service = SecurityService(ai_service=ai_content_service, config=settings.threat_filter)
            asic_service = AsicService(redis=redis_pool, parser_service=parser_service, config=settings.asic_service)
            price_service = PriceService(redis=redis_pool, config=settings.price_service, market_data_service=market_data_service)
            crypto_center_service = CryptoCenterService(redis=redis_pool, ai_service=ai_content_service, news_service=news_service, config=settings.crypto_center)
            market_service = AsicMarketService(redis=redis_pool, settings=settings, achievement_service=achievement_service, bot=bot)
            
            scheduler_instance = AsyncIOScheduler(timezone="UTC")

            mining_game_service = MiningGameService(
                redis=redis_pool, scheduler=scheduler_instance, settings=settings, user_service=user_service,
                market_service=market_service, event_service=event_service,
                achievement_service=achievement_service, bot=bot
            )
            verification_service = VerificationService(user_service=user_service)

            await market_service.setup()
            await mining_game_service.setup()

            deps_instance = cls(
                settings=settings, http_session=http_session, redis_pool=redis_pool,
                scheduler=scheduler_instance, bot=bot, user_service=user_service,
                admin_service=admin_service, ai_content_service=ai_content_service,
                news_service=news_service, parser_service=parser_service,
                quiz_service=quiz_service, event_service=event_service,
                achievement_service=achievement_service, market_data_service=market_data_service,
                security_service=security_service, coin_list_service=coin_list_service,
                asic_service=asic_service, price_service=price_service,
                crypto_center_service=crypto_center_service, market_service=market_service,
                mining_game_service=mining_game_service, verification_service=verification_service,
                mining_service=mining_service, stop_word_service=stop_word_service,
                moderation_service=moderation_service
            )
            logger.info("Контейнер зависимостей (Deps) успешно собран.")
            return deps_instance

        except Exception as e:
            logger.critical(f"Критическая ошибка при сборке контейнера зависимостей: {e}", exc_info=True)
            raise