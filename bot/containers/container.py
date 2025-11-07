# bot/containers/container.py
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dependency_injector import containers, providers
from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.containers.lock import InstanceLockManager
from bot.containers.providers import create_service_providers


class Container(containers.DynamicContainer):
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
        lambda: __import__('bot.utils.http_client', fromlist=['HTTPClient']).HTTPClient(),
    )
    
    instance_lock_manager = providers.Factory(
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
            lock_manager = self.instance_lock_manager()
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
            http = self.http_client()
            logger.info("✅ HTTP client initialized")
        except Exception as e:
            logger.error(f"❌ HTTP client initialization failed: {e}")
            raise
    
    async def shutdown_resources(self) -> None:
        logger.info("🛑 Shutting down container resources...")
        
        try:
            if hasattr(self, '_lock_manager'):
                await self._lock_manager.release_lock()
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
        
        try:
            if hasattr(self, '_singletons') and 'http_client' in self._singletons:
                http = self.http_client()
                await http.close()
                logger.info("✅ HTTP client closed")
        except Exception as e:
            logger.error(f"Error closing HTTP client: {e}")
        
        try:
            if hasattr(self, '_singletons') and 'bot' in self._singletons:
                bot_instance = self.bot()
                if hasattr(bot_instance, 'session') and bot_instance.session:
                    await bot_instance.session.close()
                logger.info("✅ Bot session closed")
        except Exception as e:
            logger.error(f"Error closing bot session: {e}")
        
        try:
            if hasattr(self, '_singletons') and 'redis_client' in self._singletons:
                redis = await self.redis_client()
                await redis.aclose()
                logger.info("✅ Redis client closed")
        except Exception as e:
            logger.error(f"Error closing Redis: {e}")


for service_name, service_provider in create_service_providers().items():
    setattr(Container, service_name, service_provider)