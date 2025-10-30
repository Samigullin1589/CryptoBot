# bot/containers.py

import asyncio
import logging
from typing import AsyncIterator, Optional
from datetime import datetime

from dependency_injector import containers, providers
from redis.asyncio import Redis
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

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


# =================================================================================
# INSTANCE LOCK MANAGER
# =================================================================================

class InstanceLockManager:
    """Менеджер блокировки для предотвращения множественных запусков"""
    
    LOCK_KEY = "bot:instance:lock"
    LOCK_TTL = 300  # 5 минут
    
    def __init__(self, redis: Redis):
        self.redis = redis
        self.instance_id = f"{datetime.utcnow().timestamp()}"
        self.is_locked = False
    
    async def acquire_lock(self, force: bool = False) -> bool:
        """
        Получить блокировку запуска бота
        
        Args:
            force: Принудительно захватить блокировку
            
        Returns:
            True если блокировка получена
        """
        try:
            if force:
                await self.redis.delete(self.LOCK_KEY)
                logger.warning("🔓 Принудительное удаление старой блокировки")
            
            result = await self.redis.set(
                self.LOCK_KEY,
                self.instance_id,
                nx=True,
                ex=self.LOCK_TTL
            )
            
            if result:
                self.is_locked = True
                logger.info(f"🔒 Instance lock получен: {self.instance_id}")
                asyncio.create_task(self._keep_alive())
                return True
            else:
                existing = await self.redis.get(self.LOCK_KEY)
                logger.error(f"❌ Instance lock уже занят: {existing}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения lock: {e}")
            return False
    
    async def release_lock(self):
        """Освободить блокировку"""
        if not self.is_locked:
            return
        
        try:
            current = await self.redis.get(self.LOCK_KEY)
            if current == self.instance_id:
                await self.redis.delete(self.LOCK_KEY)
                logger.info(f"🔓 Instance lock освобожден: {self.instance_id}")
            self.is_locked = False
        except Exception as e:
            logger.error(f"❌ Ошибка освобождения lock: {e}")
    
    async def _keep_alive(self):
        """Периодически обновлять TTL блокировки"""
        while self.is_locked:
            try:
                await asyncio.sleep(self.LOCK_TTL // 2)
                if self.is_locked:
                    await self.redis.expire(self.LOCK_KEY, self.LOCK_TTL)
            except asyncio.CancelledError:
                break
            except Exception:
                pass


# =================================================================================
# RESOURCE FACTORIES
# =================================================================================

async def init_redis_client(url: str) -> AsyncIterator[Redis]:
    """Фабрика для создания Redis клиента"""
    client = await Redis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        max_connections=10
    )
    
    try:
        await client.ping()
        logger.info("✅ Redis client initialized")
        yield client
    finally:
        await client.aclose()
        logger.info("✅ Redis client closed")


async def init_http_client(config: dict) -> AsyncIterator[HttpClient]:
    """Фабрика для создания HTTP клиента"""
    client = HttpClient(config=config)
    
    try:
        logger.info("✅ HTTP client initialized")
        yield client
    finally:
        await client.close()
        logger.info("✅ HTTP client closed")


async def init_bot(token: str) -> AsyncIterator[Bot]:
    """Фабрика для создания Bot"""
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)
        
        me = await bot.get_me()
        logger.info(f"✅ Bot initialized: @{me.username} (ID: {me.id})")
        yield bot
    finally:
        if bot.session:
            await bot.session.close()
        logger.info("✅ Bot session closed")


# =================================================================================
# MAIN CONTAINER
# =================================================================================

class Container(containers.DeclarativeContainer):
    """Основной контейнер приложения"""
    
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

    bot_token = providers.Callable(
        lambda cfg: cfg.BOT_TOKEN.get_secret_value() if cfg.BOT_TOKEN else "",
        config
    )

    # ==================== РЕСУРСЫ ====================
    
    redis_client = providers.Resource(
        init_redis_client,
        url=config.provided.REDIS_URL
    )

    http_client = providers.Resource(
        init_http_client,
        config=config.provided.endpoints
    )

    bot = providers.Resource(
        init_bot,
        token=bot_token
    )

    # ==================== СЕРВИСЫ ====================
    
    ai_content_service = providers.Singleton(AIContentService)

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
    
    # ==================== INSTANCE LOCK ====================
    instance_lock_manager: Optional[InstanceLockManager] = None

    # ==================== ПУБЛИЧНЫЕ МЕТОДЫ ====================
    
    async def init_resources(self) -> None:
        """Инициализация всех ресурсов контейнера"""
        try:
            logger.info("🔧 Инициализация ресурсов контейнера...")
            
            # Инициализируем Redis
            redis = await self.redis_client()
            
            # Создаем и получаем instance lock
            self.instance_lock_manager = InstanceLockManager(redis)
            lock_acquired = await self.instance_lock_manager.acquire_lock(force=False)
            
            if not lock_acquired:
                logger.critical("❌ Не удалось получить instance lock!")
                raise RuntimeError("Failed to acquire instance lock")
            
            # Инициализируем остальные ресурсы
            await self.http_client()
            await self.bot()
            
            logger.info("✅ Все ресурсы инициализированы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации ресурсов: {e}")
            await self.shutdown_resources()
            raise
    
    async def shutdown_resources(self) -> None:
        """Корректное освобождение всех ресурсов"""
        try:
            logger.info("🛑 Освобождение ресурсов контейнера...")
            
            # Освобождаем instance lock
            if self.instance_lock_manager:
                await self.instance_lock_manager.release_lock()
            
            # Закрываем провайдеры ресурсов
            if hasattr(self, '_singletons'):
                await self.shutdown()
            
            logger.info("✅ Все ресурсы освобождены")
            
        except Exception as e:
            logger.error(f"⚠️ Ошибка при освобождении ресурсов: {e}")