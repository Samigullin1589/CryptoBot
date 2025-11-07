# bot/containers/container.py
"""
Dependency Injection Container.
Версия: 3.0.0 Production (07.11.2025)

Управляет всеми зависимостями приложения через dependency-injector.

Архитектура:
┌─────────────────────────────────────┐
│      Container (Main DI)            │
├─────────────────────────────────────┤
│  Infrastructure:                    │
│  - Redis Client                     │
│  - HTTP Client                      │
│  - Instance Lock                    │
│  - Bot Instance                     │
├─────────────────────────────────────┤
│  Services:                          │
│  - 25+ Business Services            │
│  - AI Service                       │
│  - Security Services                │
└─────────────────────────────────────┘
"""
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dependency_injector import containers, providers
from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.containers.lock import InstanceLockManager
from bot.containers.wiring import WIRING_MODULES
from bot.utils.http_client import HTTPClient

from bot.services.admin_service import AdminService
from bot.services.user_service import UserService
from bot.services.price_service import PriceService
from bot.services.asic_service import AsicService
from bot.services.news_service import NewsService
from bot.services.market_data_service import MarketDataService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.mining_game_service import MiningGameService
from bot.services.verification_service import VerificationService
from bot.services.mining_service import MiningService
from bot.services.security_service import SecurityService
from bot.services.moderation_service import ModerationService
from bot.services.coin_list_service import CoinListService
from bot.services.achievement_service import AchievementService
from bot.services.quiz_service import QuizService
from bot.services.event_service import EventService
from bot.services.market_service import MarketService
from bot.services.parser_service import ParserService
from bot.services.coin_alias_service import CoinAliasService
from bot.services.anti_spam_service import AntiSpamService
from bot.services.stop_word_service import StopWordService
from bot.services.image_guard_service import ImageGuardService
from bot.services.image_vision_service import ImageVisionService
from bot.services.advanced_security_service import AdvancedSecurityService
from bot.services.antispam_learning import AntiSpamLearningService
from bot.services.ai.service import AIService


class Container(containers.DeclarativeContainer):
    """
    Главный DI контейнер приложения.
    
    Управляет:
    - Инфраструктурой (Redis, HTTP, Bot)
    - Бизнес-сервисами
    - Жизненным циклом ресурсов
    """
    
    wiring_config = containers.WiringConfiguration(
        modules=WIRING_MODULES
    )
    
    config = providers.Configuration()
    
    redis_client = providers.Singleton(
        Redis.from_url,
        url=settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30,
    )
    
    http_client = providers.Singleton(
        HTTPClient,
    )
    
    instance_lock_manager = providers.Singleton(
        InstanceLockManager,
        redis=redis_client,
        lock_key="bot:instance_lock",
        ttl=30,
    )
    
    bot = providers.Singleton(
        Bot,
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    
    admin_service = providers.Singleton(
        AdminService,
        redis=redis_client,
    )
    
    user_service = providers.Singleton(
        UserService,
        redis=redis_client,
    )
    
    coin_alias_service = providers.Singleton(
        CoinAliasService,
        redis=redis_client,
    )
    
    stop_word_service = providers.Singleton(
        StopWordService,
        redis=redis_client,
    )
    
    price_service = providers.Singleton(
        PriceService,
        redis=redis_client,
        http_client=http_client,
    )
    
    asic_service = providers.Singleton(
        AsicService,
        redis=redis_client,
        http_client=http_client,
    )
    
    parser_service = providers.Singleton(
        ParserService,
        http_client=http_client,
    )
    
    news_service = providers.Singleton(
        NewsService,
        redis=redis_client,
        http_client=http_client,
        parser_service=parser_service,
    )
    
    coin_list_service = providers.Singleton(
        CoinListService,
        redis=redis_client,
        http_client=http_client,
        coin_alias_service=coin_alias_service,
    )
    
    market_service = providers.Singleton(
        MarketService,
        redis=redis_client,
        http_client=http_client,
    )
    
    market_data_service = providers.Singleton(
        MarketDataService,
        redis=redis_client,
        http_client=http_client,
        coin_alias_service=coin_alias_service,
    )
    
    crypto_center_service = providers.Singleton(
        CryptoCenterService,
        redis=redis_client,
        price_service=price_service,
        news_service=news_service,
        market_data_service=market_data_service,
    )
    
    achievement_service = providers.Singleton(
        AchievementService,
        redis=redis_client,
    )
    
    quiz_service = providers.Singleton(
        QuizService,
        redis=redis_client,
        http_client=http_client,
    )
    
    event_service = providers.Singleton(
        EventService,
        redis=redis_client,
    )
    
    mining_service = providers.Singleton(
        MiningService,
        redis=redis_client,
    )
    
    mining_game_service = providers.Singleton(
        MiningGameService,
        redis=redis_client,
        achievement_service=achievement_service,
    )
    
    verification_service = providers.Singleton(
        VerificationService,
        redis=redis_client,
    )
    
    image_vision_service = providers.Singleton(
        ImageVisionService,
        http_client=http_client,
    )
    
    image_guard_service = providers.Singleton(
        ImageGuardService,
        redis=redis_client,
        vision_service=image_vision_service,
    )
    
    antispam_learning_service = providers.Singleton(
        AntiSpamLearningService,
        redis=redis_client,
    )
    
    anti_spam_service = providers.Singleton(
        AntiSpamService,
        redis=redis_client,
        stop_word_service=stop_word_service,
        learning_service=antispam_learning_service,
    )
    
    security_service = providers.Singleton(
        SecurityService,
        redis=redis_client,
        anti_spam_service=anti_spam_service,
    )
    
    advanced_security_service = providers.Singleton(
        AdvancedSecurityService,
        redis=redis_client,
        security_service=security_service,
    )
    
    moderation_service = providers.Singleton(
        ModerationService,
        redis=redis_client,
        security_service=security_service,
    )
    
    ai_service = providers.Singleton(
        AIService,
    )
    
    async def init_resources(self) -> None:
        """
        Инициализирует все ресурсы контейнера.
        
        Порядок инициализации:
        1. Redis подключение
        2. Instance Lock (проверка единственности)
        3. HTTP Client
        
        Raises:
            RuntimeError: Если другой instance уже запущен
            Exception: Ошибки инициализации ресурсов
        """
        logger.info("🔧 Initializing container resources...")
        
        await self._init_redis()
        await self._init_lock_manager()
        await self._init_http_client()
        
        logger.info("✅ All container resources initialized")
    
    async def _init_redis(self) -> None:
        """
        Инициализирует Redis соединение.
        
        Raises:
            Exception: Ошибки подключения к Redis
        """
        try:
            redis = self.redis_client()
            await redis.ping()
            logger.info("✅ Redis connected successfully")
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}", exc_info=True)
            raise
    
    async def _init_lock_manager(self) -> None:
        """
        Инициализирует и получает Instance Lock.
        
        Гарантирует, что запущен только один instance бота.
        
        Raises:
            RuntimeError: Если другой instance уже запущен
        """
        try:
            lock_manager = self.instance_lock_manager()
            acquired = await lock_manager.acquire_lock()
            
            if not acquired:
                raise RuntimeError(
                    "Another bot instance is already running. "
                    "Please stop it before starting a new one."
                )
            
            self._lock_manager = lock_manager
            logger.info("✅ Instance lock acquired")
            
        except RuntimeError:
            raise
            
        except Exception as e:
            logger.error(
                f"❌ Failed to initialize lock manager: {e}",
                exc_info=True
            )
            raise
    
    async def _init_http_client(self) -> None:
        """
        Инициализирует HTTP Client.
        
        Raises:
            Exception: Ошибки инициализации HTTP клиента
        """
        try:
            http = self.http_client()
            logger.info("✅ HTTP client initialized")
            
        except Exception as e:
            logger.error(
                f"❌ HTTP client initialization failed: {e}",
                exc_info=True
            )
            raise
    
    async def shutdown_resources(self) -> None:
        """
        Освобождает все ресурсы контейнера.
        
        Порядок освобождения (обратный инициализации):
        1. Instance Lock
        2. HTTP Client
        3. Bot Session
        4. Redis Connection
        """
        logger.info("🛑 Shutting down container resources...")
        
        await self._release_lock()
        await self._close_http_client()
        await self._close_bot_session()
        await self._close_redis()
        
        logger.info("✅ All container resources shutdown")
    
    async def _release_lock(self) -> None:
        """Освобождает Instance Lock."""
        try:
            if hasattr(self, '_lock_manager'):
                await self._lock_manager.release_lock()
                logger.info("✅ Instance lock released")
                
        except Exception as e:
            logger.error(f"⚠️ Error releasing lock: {e}")
    
    async def _close_http_client(self) -> None:
        """Закрывает HTTP Client."""
        try:
            http = self.http_client()
            await http.close()
            logger.info("✅ HTTP client closed")
            
        except Exception as e:
            logger.error(f"⚠️ Error closing HTTP client: {e}")
    
    async def _close_bot_session(self) -> None:
        """Закрывает Bot Session."""
        try:
            bot_instance = self.bot()
            if hasattr(bot_instance, 'session') and bot_instance.session:
                await bot_instance.session.close()
            logger.info("✅ Bot session closed")
            
        except Exception as e:
            logger.error(f"⚠️ Error closing bot session: {e}")
    
    async def _close_redis(self) -> None:
        """Закрывает Redis соединение."""
        try:
            redis = self.redis_client()
            await redis.aclose()
            logger.info("✅ Redis client closed")
            
        except Exception as e:
            logger.error(f"⚠️ Error closing Redis: {e}")