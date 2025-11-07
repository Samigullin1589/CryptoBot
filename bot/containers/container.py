# bot/containers/container.py
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dependency_injector import containers, providers
from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.containers.lock import InstanceLockManager
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
    wiring_config = containers.WiringConfiguration(
        modules=[
            "bot.middlewares.dependencies",
            "bot.handlers.public.command_handler_extended",
            "bot.handlers.public.common_handler",
            "bot.handlers.public.price_handler",
            "bot.handlers.public.asic_handler",
            "bot.handlers.public.news_handler",
            "bot.handlers.public.market_handler",
            "bot.handlers.public.market_info_handler",
            "bot.handlers.public.crypto_center_handler",
            "bot.handlers.public.achievements_handler",
            "bot.handlers.public.menu_handler",
            "bot.handlers.public.help_handler",
            "bot.handlers.public.start_handler",
            "bot.handlers.public.text_handler",
            "bot.handlers.public.verification_public_handler",
            "bot.handlers.public.onboarding_handler",
            "bot.handlers.game.game_handler",
            "bot.handlers.game.mining_game_handler",
            "bot.handlers.admin.admin_handler",
            "bot.handlers.admin.admin_menu",
            "bot.handlers.admin.cache_handler",
            "bot.handlers.admin.game_admin_handler",
            "bot.handlers.admin.health_handler",
            "bot.handlers.admin.moderation_handler",
            "bot.handlers.admin.stats_handler",
            "bot.handlers.admin.verification_admin_handler",
            "bot.handlers.admin.version_handler",
            "bot.handlers.tools.calculator_handler",
            "bot.handlers.threats.threat_handler",
        ]
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
        redis=redis_client,
        http_client=http_client,
    )

    async def init_resources(self) -> None:
        logger.info("🔧 Initializing container resources...")
        
        try:
            redis = await self.redis_client()
            await redis.ping()
            logger.info("✅ Redis connected")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise
        
        try:
            lock_manager = await self.instance_lock_manager()
            acquired = await lock_manager.acquire_lock()
            
            if not acquired:
                raise RuntimeError(
                    "Another bot instance is already running. "
                    "Please stop it before starting a new one."
                )
            
            self._lock_manager = lock_manager
            
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"❌ Failed to initialize lock manager: {e}")
            raise
        
        try:
            http = await self.http_client()
            logger.info("✅ HTTP client initialized")
        except Exception as e:
            logger.error(f"❌ HTTP client initialization failed: {e}")
            raise
    
    async def shutdown_resources(self) -> None:
        logger.info("🛑 Shutting down container resources...")
        
        try:
            if hasattr(self, '_lock_manager'):
                await self._lock_manager.release_lock()
                logger.info("✅ Instance lock released")
        except Exception as e:
            logger.error(f"❌ Error releasing lock: {e}")
        
        try:
            http = await self.http_client()
            await http.close()
            logger.info("✅ HTTP client closed")
        except Exception as e:
            logger.error(f"❌ Error closing HTTP client: {e}")
        
        try:
            bot_instance = await self.bot()
            if hasattr(bot_instance, 'session') and bot_instance.session:
                await bot_instance.session.close()
            logger.info("✅ Bot session closed")
        except Exception as e:
            logger.error(f"❌ Error closing bot session: {e}")
        
        try:
            redis = await self.redis_client()
            await redis.aclose()
            logger.info("✅ Redis client closed")
        except Exception as e:
            logger.error(f"❌ Error closing Redis: {e}")