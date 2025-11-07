# bot/middlewares/dependencies.py
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from loguru import logger

from bot.containers import Container


class DependenciesMiddleware(BaseMiddleware):
    """
    Легковесный middleware для внедрения DI-контейнера в обработчики.
    
    Все сервисы создаются как singleton в контейнере и переиспользуются,
    а не создаются заново при каждом запросе.
    """

    def __init__(self, container: Container):
        super().__init__()
        self.container = container
        self._services_cache = {}
        logger.info("✅ DependenciesMiddleware initialized")

    async def _get_or_create_service(self, service_name: str) -> Any:
        """
        Получает сервис из кеша или создает его один раз.
        
        Args:
            service_name: Имя сервиса в контейнере
            
        Returns:
            Экземпляр сервиса
        """
        if service_name not in self._services_cache:
            try:
                provider = getattr(self.container, service_name)
                if callable(provider):
                    service = await provider() if hasattr(provider, '__await__') else provider()
                    self._services_cache[service_name] = service
                    logger.debug(f"✅ Service '{service_name}' cached")
                else:
                    self._services_cache[service_name] = provider
            except AttributeError:
                logger.warning(f"⚠️ Service '{service_name}' not found in container")
                self._services_cache[service_name] = None
            except Exception as e:
                logger.error(f"❌ Failed to initialize service '{service_name}': {e}")
                self._services_cache[service_name] = None
        
        return self._services_cache[service_name]

    async def _ensure_services_initialized(self) -> None:
        """
        Инициализирует все основные сервисы при первом запросе.
        """
        if self._services_cache:
            return
        
        service_names = [
            'admin_service',
            'user_service',
            'price_service',
            'asic_service',
            'news_service',
            'market_data_service',
            'crypto_center_service',
            'mining_game_service',
            'verification_service',
            'mining_service',
            'security_service',
            'moderation_service',
            'coin_list_service',
            'achievement_service',
            'ai_service',
            'quiz_service',
            'event_service',
            'market_service',
            'parser_service',
            'coin_alias_service',
            'anti_spam_service',
            'stop_word_service',
            'image_guard_service',
            'image_vision_service',
            'advanced_security_service',
            'antispam_learning_service',
        ]
        
        for service_name in service_names:
            await self._get_or_create_service(service_name)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Внедряет зависимости в контекст обработчика.
        
        Args:
            handler: Следующий обработчик в цепочке
            event: Событие от Telegram
            data: Контекст данных
            
        Returns:
            Результат выполнения обработчика
        """
        try:
            await self._ensure_services_initialized()
            
            data["container"] = self.container
            
            redis = await self.container.redis_client()
            data["redis"] = redis
            
            config = self.container.config
            data["settings"] = config
            
            data["admin_service"] = self._services_cache.get('admin_service')
            data["user_service"] = self._services_cache.get('user_service')
            data["price_service"] = self._services_cache.get('price_service')
            data["asic_service"] = self._services_cache.get('asic_service')
            data["news_service"] = self._services_cache.get('news_service')
            data["market_data_service"] = self._services_cache.get('market_data_service')
            data["crypto_center_service"] = self._services_cache.get('crypto_center_service')
            data["mining_game_service"] = self._services_cache.get('mining_game_service')
            data["verification_service"] = self._services_cache.get('verification_service')
            data["mining_service"] = self._services_cache.get('mining_service')
            data["security_service"] = self._services_cache.get('security_service')
            data["moderation_service"] = self._services_cache.get('moderation_service')
            data["coin_list_service"] = self._services_cache.get('coin_list_service')
            data["achievement_service"] = self._services_cache.get('achievement_service')
            data["ai_service"] = self._services_cache.get('ai_service')
            data["quiz_service"] = self._services_cache.get('quiz_service')
            data["event_service"] = self._services_cache.get('event_service')
            data["market_service"] = self._services_cache.get('market_service')
            data["parser_service"] = self._services_cache.get('parser_service')
            data["coin_alias_service"] = self._services_cache.get('coin_alias_service')
            data["anti_spam_service"] = self._services_cache.get('anti_spam_service')
            data["stop_word_service"] = self._services_cache.get('stop_word_service')
            data["image_guard_service"] = self._services_cache.get('image_guard_service')
            data["image_vision_service"] = self._services_cache.get('image_vision_service')
            data["advanced_security_service"] = self._services_cache.get('advanced_security_service')
            data["antispam_learning_service"] = self._services_cache.get('antispam_learning_service')
            
            from bot.utils.keys import KeyFactory
            data["keys"] = KeyFactory
            
            from bot.utils.dependencies import Deps
            deps = Deps(
                settings=config,
                redis=redis,
                keys=KeyFactory,
                admin_service=data["admin_service"],
                user_service=data["user_service"],
                price_service=data["price_service"],
                asic_service=data["asic_service"],
                news_service=data["news_service"],
                market_data_service=data["market_data_service"],
                crypto_center_service=data["crypto_center_service"],
                mining_game_service=data["mining_game_service"],
                verification_service=data["verification_service"],
                mining_service=data["mining_service"],
                security_service=data["security_service"],
                moderation_service=data["moderation_service"],
                coin_list_service=data["coin_list_service"],
                achievement_service=data["achievement_service"],
                ai_content_service=data["ai_service"],
                quiz_service=data["quiz_service"],
            )
            
            data["deps"] = deps
            
        except Exception as e:
            logger.error(f"❌ Critical error in DependenciesMiddleware: {e}", exc_info=True)
            data["deps"] = None
            data["container"] = self.container
        
        return await handler(event, data)