# bot/containers.py
import asyncio
from typing import Optional

from dependency_injector import containers, providers
from redis.asyncio import Redis
from aiohttp import ClientSession, TCPConnector, ClientTimeout
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from bot.config.settings import settings


class InstanceLockManager:
    """Менеджер блокировки для предотвращения множественных запусков"""
    
    def __init__(self, redis: Redis, lock_key: str = "bot:instance_lock", ttl: int = 30):
        self.redis = redis
        self.lock_key = lock_key
        self.ttl = ttl
        self._lock_acquired = False
        self._refresh_task: Optional[asyncio.Task] = None
    
    async def acquire_lock(self) -> bool:
        """Попытка захвата блокировки"""
        try:
            result = await self.redis.set(
                self.lock_key,
                "1",
                nx=True,
                ex=self.ttl
            )
            
            if result:
                self._lock_acquired = True
                self._refresh_task = asyncio.create_task(self._refresh_lock())
                logger.info(f"✅ Instance lock acquired: {self.lock_key}")
                return True
            else:
                logger.warning(f"⚠️ Instance lock already held by another process")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to acquire lock: {e}")
            return False
    
    async def _refresh_lock(self):
        """Периодическое обновление TTL блокировки"""
        try:
            while self._lock_acquired:
                await asyncio.sleep(self.ttl / 2)
                if self._lock_acquired:
                    await self.redis.expire(self.lock_key, self.ttl)
                    logger.debug(f"🔄 Lock TTL refreshed: {self.lock_key}")
        except asyncio.CancelledError:
            logger.debug("Lock refresh task cancelled")
        except Exception as e:
            logger.error(f"Error refreshing lock: {e}")
    
    async def release_lock(self):
        """Освобождение блокировки"""
        if not self._lock_acquired:
            return
        
        try:
            self._lock_acquired = False
            
            if self._refresh_task:
                self._refresh_task.cancel()
                try:
                    await self._refresh_task
                except asyncio.CancelledError:
                    pass
            
            await self.redis.delete(self.lock_key)
            logger.info(f"✅ Instance lock released: {self.lock_key}")
            
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")


async def create_http_client() -> ClientSession:
    """Factory для создания HTTP клиента с connector"""
    connector = TCPConnector(
        limit=100,
        limit_per_host=30,
        ttl_dns_cache=300,
        ssl=False,
    )
    return ClientSession(
        connector=connector,
        timeout=ClientTimeout(total=30, connect=10),
    )


class Container(containers.DynamicContainer):
    """DI контейнер приложения"""
    
    config = providers.Configuration()
    
    # Redis клиент
    redis_client = providers.Singleton(
        Redis.from_url,
        url=settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30,
    )
    
    # HTTP клиент
    http_client = providers.Resource(
        create_http_client,
    )
    
    # Instance Lock Manager
    instance_lock_manager = providers.Factory(
        InstanceLockManager,
        redis=redis_client,
        lock_key="bot:instance_lock",
        ttl=30,
    )
    
    # Bot - исправлено для aiogram 3.7.0+
    bot = providers.Singleton(
        Bot,
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    
    # Services - ленивая инициализация с правильными зависимостями
    image_vision_service = providers.Singleton(
        lambda: __import__('bot.services.image_vision_service', fromlist=['ImageVisionService']).ImageVisionService(),
    )
    
    admin_service = providers.Singleton(
        lambda redis_client, bot_instance: __import__('bot.services.admin_service', fromlist=['AdminService']).AdminService(
            redis_client=redis_client,
            bot=bot_instance
        ),
        redis_client=redis_client,
        bot_instance=bot,
    )
    
    user_service = providers.Singleton(
        lambda redis_client: __import__('bot.services.user_service', fromlist=['UserService']).UserService(
            redis_client=redis_client
        ),
        redis_client=redis_client,
    )
    
    market_data_service = providers.Singleton(
        lambda http_session: __import__('bot.services.market_data_service', fromlist=['MarketDataService']).MarketDataService(
            http_client=http_session
        ),
        http_session=http_client,
    )
    
    parser_service = providers.Singleton(
        lambda http_session: __import__('bot.services.parser_service', fromlist=['ParserService']).ParserService(
            http_client=http_session
        ),
        http_session=http_client,
    )
    
    news_service = providers.Singleton(
        lambda http_session: __import__('bot.services.news_service', fromlist=['NewsService']).NewsService(
            http_client=http_session
        ),
        http_session=http_client,
    )
    
    moderation_service = providers.Singleton(
        lambda redis_client, bot_instance: __import__('bot.services.moderation_service', fromlist=['ModerationService']).ModerationService(
            redis_client=redis_client,
            bot=bot_instance
        ),
        redis_client=redis_client,
        bot_instance=bot,
    )
    
    coin_list_service = providers.Singleton(
        lambda http_session, redis_client: __import__('bot.services.coin_list_service', fromlist=['CoinListService']).CoinListService(
            http_client=http_session,
            redis_client=redis_client
        ),
        http_session=http_client,
        redis_client=redis_client,
    )
    
    verification_service = providers.Singleton(
        lambda redis_client: __import__('bot.services.verification_service', fromlist=['VerificationService']).VerificationService(
            redis_client=redis_client
        ),
        redis_client=redis_client,
    )
    
    price_service = providers.Singleton(
        lambda http_session: __import__('bot.services.price_service', fromlist=['PriceService']).PriceService(
            http_client=http_session
        ),
        http_session=http_client,
    )
    
    achievement_service = providers.Singleton(
        lambda redis_client: __import__('bot.services.achievement_service', fromlist=['AchievementService']).AchievementService(
            redis_client=redis_client
        ),
        redis_client=redis_client,
    )
    
    mining_service = providers.Singleton(
        lambda redis_client: __import__('bot.services.mining_service', fromlist=['MiningService']).MiningService(
            redis_client=redis_client
        ),
        redis_client=redis_client,
    )
    
    asic_service = providers.Singleton(
        lambda redis_client: __import__('bot.services.asic_service', fromlist=['AsicService']).AsicService(
            redis_client=redis_client
        ),
        redis_client=redis_client,
    )
    
    crypto_center_service = providers.Singleton(
        lambda news_svc, redis_client: __import__('bot.services.crypto_center_service', fromlist=['CryptoCenterService']).CryptoCenterService(
            news_service=news_svc,
            redis_client=redis_client
        ),
        news_svc=news_service,
        redis_client=redis_client,
    )
    
    security_service = providers.Singleton(
        lambda img_vision, moderation_svc, redis_client, bot_instance: __import__('bot.services.security_service', fromlist=['SecurityService']).SecurityService(
            image_vision_service=img_vision,
            moderation_service=moderation_svc,
            redis_client=redis_client,
            bot=bot_instance
        ),
        img_vision=image_vision_service,
        moderation_svc=moderation_service,
        redis_client=redis_client,
        bot_instance=bot,
    )
    
    mining_game_service = providers.Singleton(
        lambda asic_svc, achievement_svc, redis_client: __import__('bot.services.mining_game_service', fromlist=['MiningGameService']).MiningGameService(
            asic_service=asic_svc,
            achievement_service=achievement_svc,
            redis_client=redis_client
        ),
        asic_svc=asic_service,
        achievement_svc=achievement_service,
        redis_client=redis_client,
    )
    
    ai_content_service = providers.Singleton(
        lambda: __import__('bot.services.ai_content_service', fromlist=['AIContentService']).AIContentService(),
    )
    
    quiz_service = providers.Singleton(
        lambda ai_svc: __import__('bot.services.quiz_service', fromlist=['QuizService']).QuizService(
            ai_content_service=ai_svc
        ),
        ai_svc=ai_content_service,
    )
    
    async def init_resources(self) -> None:
        """Инициализация ресурсов и получение блокировки"""
        logger.info("🔧 Initializing container resources...")
        
        # Инициализируем Redis
        try:
            redis = await self.redis_client()
            await redis.ping()
            logger.info("✅ Redis connected")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise
        
        # Получаем блокировку инстанса
        try:
            lock_manager = self.instance_lock_manager()
            acquired = await lock_manager.acquire_lock()
            
            if not acquired:
                raise RuntimeError(
                    "Another bot instance is already running. "
                    "Please stop it before starting a new one."
                )
            
            # Сохраняем lock_manager для последующего использования
            self._lock_manager = lock_manager
            
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"❌ Failed to initialize lock manager: {e}")
            raise
        
        # Инициализируем HTTP клиент
        try:
            await self.http_client.init()
            logger.info("✅ HTTP client initialized")
        except Exception as e:
            logger.error(f"❌ HTTP client initialization failed: {e}")
            raise
    
    async def shutdown_resources(self) -> None:
        """Корректное закрытие всех ресурсов"""
        logger.info("🛑 Shutting down container resources...")
        
        # Освобождаем блокировку
        try:
            if hasattr(self, '_lock_manager'):
                await self._lock_manager.release_lock()
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
        
        # Закрываем HTTP клиент
        try:
            await self.http_client.shutdown()
            logger.info("✅ HTTP client closed")
        except Exception as e:
            logger.error(f"Error closing HTTP client: {e}")
        
        # Закрываем Bot сессию
        try:
            if hasattr(self, '_singletons') and 'bot' in self._singletons:
                bot = await self.bot()
                if hasattr(bot, 'session') and bot.session:
                    await bot.session.close()
                logger.info("✅ Bot session closed")
        except Exception as e:
            logger.error(f"Error closing bot session: {e}")
        
        # Закрываем Redis
        try:
            if hasattr(self, '_singletons') and 'redis_client' in self._singletons:
                redis = await self.redis_client()
                await redis.aclose()
                logger.info("✅ Redis client closed")
        except Exception as e:
            logger.error(f"Error closing Redis: {e}")