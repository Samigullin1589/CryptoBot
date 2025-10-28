# =================================================================================
# bot/containers.py
# Версия: ИСПРАВЛЕННАЯ (28.10.2025) - Distinguished Engineer
# Описание:
#   • ИСПРАВЛЕНО: Правильная передача BOT_TOKEN через providers.Callable
#   • Добавлены методы init_resources() и shutdown_resources()
#   • Улучшено логирование
# =================================================================================

import logging
from dependency_injector import containers, providers
from redis.asyncio import Redis
from aiogram import Bot

from bot.config.settings import Settings
from bot.services.achievement_service import AchievementService
from bot.services.admin_service import AdminService
from bot.services.asic_service import AsicService
from bot.services.coin_alias_service import CoinAliasService
from bot.services.coin_list_service import CoinListService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.market_data_service import MarketDataService
from bot.services.mining_game_service import MiningGameService
from bot.services.news_service import NewsService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.services.user_service import UserService
from bot.services.verification_service import VerificationService
from bot.services.ai_content_service import AIContentService
from bot.utils.http_client import HttpClient
from bot.services.parser_service import ParserService
from bot.services.mining_service import MiningService
from bot.services.moderation_service import ModerationService
from bot.services.security_service import SecurityService
from bot.services.image_vision_service import ImageVisionService

logger = logging.getLogger(__name__)


class Container(containers.DeclarativeContainer):
    """
    Основной контейнер приложения для внедрения зависимостей.
    """
    wiring_config = containers.WiringConfiguration(
        modules=[
            "bot.main", 
            "bot.utils.dependencies", 
            "bot.jobs.scheduled_tasks",
        ],
        packages=[
            "bot.handlers", 
            "bot.middlewares",
        ],
    )

    # ==================== КОНФИГУРАЦИЯ ====================
    config = providers.Singleton(Settings)

    # ==================== BOT TOKEN (ИСПРАВЛЕНО) ====================
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем providers.Callable для получения токена
    # чтобы метод get_secret_value() вызывался в правильное время
    bot_token = providers.Callable(
        lambda cfg: cfg.BOT_TOKEN.get_secret_value() if cfg.BOT_TOKEN else "",
        config
    )

    # ==================== ОСНОВНЫЕ КОМПОНЕНТЫ ====================
    bot = providers.Singleton(
        Bot, 
        token=bot_token
    )

    redis_client = providers.Resource(
        Redis.from_url,
        url=config.provided.REDIS_URL,
        decode_responses=True,
    )

    http_client = providers.Resource(
        HttpClient, 
        config=config.provided.endpoints
    )

    # ==================== СЕРВИСЫ ====================
    ai_content_service = providers.Singleton(
        AIContentService
    )

    image_vision_service = providers.Singleton(
        ImageVisionService, 
        ai_service=ai_content_service
    )

    user_service = providers.Singleton(
        UserService, 
        redis_client=redis_client
    )

    coin_list_service = providers.Singleton(
        CoinListService, 
        redis_client=redis_client, 
        http_client=http_client, 
        config=config.provided.coin_list_service
    )

    coin_alias_service = providers.Singleton(
        CoinAliasService, 
        redis_client=redis_client
    )

    parser_service = providers.Singleton(
        ParserService, 
        http_client=http_client
    )

    market_data_service = providers.Singleton(
        MarketDataService, 
        redis_client=redis_client, 
        http_client=http_client, 
        coin_list_service=coin_list_service, 
        config=config.provided.market_data
    )

    price_service = providers.Singleton(
        PriceService, 
        redis_client=redis_client, 
        market_data_service=market_data_service, 
        config=config.provided.price_service
    )

    news_service = providers.Singleton(
        NewsService, 
        redis_client=redis_client, 
        http_client=http_client
    )

    quiz_service = providers.Singleton(
        QuizService, 
        ai_content_service=ai_content_service
    )

    achievement_service = providers.Singleton(
        AchievementService, 
        market_data_service=market_data_service, 
        redis_client=redis_client
    )

    asic_service = providers.Singleton(
        AsicService, 
        parser_service=parser_service, 
        redis_client=redis_client
    )

    crypto_center_service = providers.Singleton(
        CryptoCenterService, 
        ai_service=ai_content_service, 
        news_service=news_service, 
        redis_client=redis_client
    )

    mining_service = providers.Singleton(
        MiningService, 
        market_data_service=market_data_service
    )

    mining_game_service = providers.Singleton(
        MiningGameService, 
        user_service=user_service, 
        asic_service=asic_service, 
        achievement_service=achievement_service, 
        redis_client=redis_client
    )

    verification_service = providers.Singleton(
        VerificationService, 
        user_service=user_service
    )

    admin_service = providers.Singleton(
        AdminService, 
        redis_client=redis_client, 
        bot=bot
    )

    moderation_service = providers.Singleton(
        ModerationService, 
        redis_client=redis_client, 
        bot=bot
    )

    security_service = providers.Singleton(
        SecurityService, 
        ai_content_service=ai_content_service, 
        image_vision_service=image_vision_service, 
        moderation_service=moderation_service, 
        redis_client=redis_client, 
        bot=bot
    )

    # =============================================================================
    # МЕТОДЫ ДЛЯ УПРАВЛЕНИЯ РЕСУРСАМИ
    # =============================================================================

    async def init_resources(self) -> None:
        """
        Инициализирует все ресурсы приложения (Redis, HTTP-клиент).
        Вызывается при старте бота.
        """
        logger.info("🔧 Начинается инициализация ресурсов...")
        
        try:
            # Инициализация Redis connection
            await self.redis_client.init()
            logger.info("✅ Redis client успешно инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Redis: {e}")
            raise

        try:
            # Инициализация HTTP client
            await self.http_client.init()
            logger.info("✅ HTTP client успешно инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации HTTP client: {e}")
            raise

        logger.info("✅ Все ресурсы успешно инициализированы")

    async def shutdown_resources(self) -> None:
        """
        Корректно завершает работу всех ресурсов (Redis, HTTP-клиент).
        Вызывается при остановке бота.
        """
        logger.info("🛑 Начинается завершение работы ресурсов...")
        
        try:
            # Закрытие HTTP client
            await self.http_client.shutdown()
            logger.info("✅ HTTP client успешно закрыт")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при закрытии HTTP client: {e}")

        try:
            # Закрытие Redis connection
            await self.redis_client.shutdown()
            logger.info("✅ Redis client успешно закрыт")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при закрытии Redis: {e}")

        logger.info("✅ Все ресурсы успешно завершены")