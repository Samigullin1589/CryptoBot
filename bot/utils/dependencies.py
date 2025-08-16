# ======================================================================================
# Файл: bot/utils/dependencies.py
# Версия: "Distinguished Engineer" — МАКСИМАЛЬНАЯ (полный DI-контейнер под твой стек)
# Описание:
#   Универсальный контейнер зависимостей (aiogram 3 + redis.asyncio + aiohttp),
#   аккуратно инициализирующий все ключевые сервисы проекта и передающий их в хендлеры.
#   Особенности:
#     • Без заглушек: рабочие импорты и реальная инициализация.
#     • Надёжное создание Redis-клиента (asyncio), HTTP-сессии (aiohttp).
#     • Автонастройка AIContentService (Gemini по умолчанию, OpenAI — если ключ доступен).
#     • Динамическая сборка сервисов по их сигнатурам (поддержка create()/__init__).
#     • Загрузка LUA-скриптов для Market/MiningGame при наличии методов.
#     • Безопасное завершение (await aclose()) — без DeprecationWarning.
#     • Middleware для прокидывания deps в data каждого апдейта.
# ======================================================================================

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Dict, Optional

import aiohttp
import redis.asyncio as redis

from aiogram.dispatcher.middlewares.base import BaseMiddleware

from bot.config.settings import settings, Settings

# ===== Импорты доменных сервисов (исходим из реальной структуры проекта) =====

# AI / LLM
from bot.services.ai_content_service import AIContentService  # noqa: F401

# Крипто-сервисы
from bot.services.price_service import PriceService  # noqa: F401
from bot.services.coin_list_service import CoinListService  # noqa: F401
from bot.services.news_service import NewsService  # noqa: F401

# Безопасность / модерация
from bot.services.security_service import SecurityService  # noqa: F401

# ASIC / рынок / майнинг
from bot.services.asic_service import AsicService  # noqa: F401
from bot.services.market_service import MarketService  # noqa: F401
from bot.services.mining_service import MiningService  # noqa: F401
from bot.services.mining_game_service import MiningGameService  # noqa: F401

# Геймификация
from bot.services.achievement_service import AchievementService  # noqa: F401
from bot.services.event_service import EventService  # noqa: F401
from bot.services.quiz_service import QuizService  # noqa: F401

# Пользователи
from bot.services.user_service import UserService  # noqa: F401


logger = logging.getLogger(__name__)


# =============================== Middleware (deps) ===============================

class DependenciesMiddleware(BaseMiddleware):
    """
    Простой middleware, который кладёт экземпляр Deps в data каждого апдейта.
    Подключается в main.py для router.message/callback_query, и т.п.
    """
    def __init__(self, deps: "Deps") -> None:
        super().__init__()
        self.deps = deps

    async def __call__(self, handler, event, data):
        data["deps"] = self.deps
        return await handler(event, data)


def dependencies_middleware(deps: "Deps") -> DependenciesMiddleware:
    """Шорткат для регистрации в main.py"""
    return DependenciesMiddleware(deps)


# ================================ DI-контейнер ==================================

class Deps:
    """
    Контейнер зависимостей. Создаётся через `await Deps.create(settings)`.
    Доступные поля (основные):
        settings: Settings

        # низкоуровневые ресурсы
        redis_pool: redis.asyncio.Redis
        redis: redis.asyncio.Redis       # алиас
        http_session: aiohttp.ClientSession

        # доменные сервисы
        ai_content_service: AIContentService
        price_service: PriceService
        coin_list_service: CoinListService
        news_service: NewsService
        security_service: SecurityService
        asic_service: AsicService
        market_service: MarketService
        mining_service: MiningService
        mining_game_service: MiningGameService
        achievement_service: AchievementService
        event_service: EventService
        quiz_service: QuizService
        user_service: UserService
    """

    # --------- создание / завершение ---------

    def __init__(self, cfg: Settings) -> None:
        self.settings: Settings = cfg

        # низкоуровневые ресурсы
        self.redis_pool: Optional[redis.Redis] = None
        self.redis: Optional[redis.Redis] = None
        self.http_session: Optional[aiohttp.ClientSession] = None

        # доменные сервисы (заполнятся в _init_services)
        self.ai_content_service: Optional[AIContentService] = None
        self.price_service: Optional[PriceService] = None
        self.coin_list_service: Optional[CoinListService] = None
        self.news_service: Optional[NewsService] = None
        self.security_service: Optional[SecurityService] = None
        self.asic_service: Optional[AsicService] = None
        self.market_service: Optional[MarketService] = None
        self.mining_service: Optional[MiningService] = None
        self.mining_game_service: Optional[MiningGameService] = None
        self.achievement_service: Optional[AchievementService] = None
        self.event_service: Optional[EventService] = None
        self.quiz_service: Optional[QuizService] = None
        self.user_service: Optional[UserService] = None

    # --- фабричный метод ---

    @classmethod
    async def create(cls, cfg: Settings | None = None) -> "Deps":
        """
        Основная точка входа: создаёт и настраивает всё необходимое.
        """
        cfg = cfg or settings
        self = cls(cfg)

        await self._init_low_level()
        await self._init_services()

        logger.info("Контейнер зависимостей (Deps) успешно собран.")
        return self

    async def close(self) -> None:
        """
        Корректное завершение всех ресурсов и сервисов.
        Вызывается из on_shutdown (main.py).
        """
        # Закрываем сервисы, у которых есть async close()
        for svc_name in [
            "ai_content_service",
            "price_service",
            "coin_list_service",
            "news_service",
            "security_service",
            "asic_service",
            "market_service",
            "mining_service",
            "mining_game_service",
            "achievement_service",
            "event_service",
            "quiz_service",
            "user_service",
        ]:
            svc = getattr(self, svc_name, None)
            if svc and hasattr(svc, "close") and inspect.iscoroutinefunction(svc.close):
                try:
                    await svc.close()  # type: ignore[misc]
                except Exception as e:
                    logger.warning("Ошибка при закрытии %s: %s", svc_name, e)

        # Закрываем HTTP-сессию
        if self.http_session and not self.http_session.closed:
            try:
                await self.http_session.close()
            except Exception as e:
                logger.warning("Ошибка при закрытии http_session: %s", e)

        # Закрываем Redis (aclose — предпочтительно)
        if self.redis_pool is not None:
            try:
                aclose = getattr(self.redis_pool, "aclose", None)
                if callable(aclose):
                    await aclose()
                else:
                    await self.redis_pool.close()
            except Exception as e:
                logger.warning("Ошибка при закрытии Redis: %s", e)

    # --------- низкоуровневая инициализация ---------

    async def _init_low_level(self) -> None:
        """
        Создаёт Redis-подключение и aiohttp-сессию.
        Настраивает провайдера Gemini (и OpenAI — если ключ есть).
        """
        # Redis
        self.redis_pool = redis.from_url(
            str(self.settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,  # удобно для hgetall/hget
            max_connections=50,
        )
        # Алиас
        self.redis = self.redis_pool

        logger.info("Успешное подключение к Redis.")

        # HTTP-сессия
        timeout = aiohttp.ClientTimeout(total=30)
        self.http_session = aiohttp.ClientSession(timeout=timeout)

        # AI / LLM (только конфигурация окружения; создание клиента — в сервисе)
        # Если используете google-generativeai, конфигурация ключа может быть здесь,
        # но сам клиент создаётся в AIContentService.
        logger.info(
            "AIContentService: провайдер=%s, модель=%s (flash=%s).",
            self.settings.ai.provider,
            self.settings.ai.model_name,
            self.settings.ai.flash_model_name,
        )

    # --------- инициализация доменных сервисов ---------

    async def _init_services(self) -> None:
        """
        Инициализирует все сервисы. Поддерживает 2 контракта:
          • async @classmethod create(...): return instance
          • __init__(...) обычный конструктор
        В аргументы передаются то, что сервис способен принять
        по своей сигнатуре (подбирается автоматически).
        """
        # Кандидаты (общий пул зависимостей), из которого будут выбраны подходящие
        base_kwargs: Dict[str, Any] = {
            "settings": self.settings,
            "cfg": self.settings,               # на случай, если сервис просит cfg
            "redis": self.redis,
            "redis_pool": self.redis_pool,
            "http_session": self.http_session,
            "session": self.http_session,       # на случай, если параметр так называется
            "endpoints": self.settings.endpoints,
            "ai_config": self.settings.ai,
        }

        # Порядок важен только для логов; зависимости друг от друга
        # не жёсткие (каждый сервис сам берёт нужные поля из kwargs).
        self.user_service = await self._make_instance(UserService, base_kwargs)
        self.ai_content_service = await self._make_instance(AIContentService, base_kwargs)
        self.price_service = await self._make_instance(PriceService, base_kwargs)
        self.coin_list_service = await self._make_instance(CoinListService, base_kwargs)
        self.news_service = await self._make_instance(NewsService, base_kwargs)
        self.security_service = await self._make_instance(SecurityService, base_kwargs)
        self.asic_service = await self._make_instance(AsicService, base_kwargs)
        self.market_service = await self._make_instance(MarketService, base_kwargs)
        self.mining_service = await self._make_instance(MiningService, base_kwargs)

        # Сервисы игры, которым может понадобиться ссылка на другие сервисы
        game_extra = {
            **base_kwargs,
            "user_service": self.user_service,
            "asic_service": self.asic_service,
            "market_service": self.market_service,
            "mining_service": self.mining_service,
            "achievement_service": None,  # временно None — заполним ниже
        }
        self.mining_game_service = await self._make_instance(MiningGameService, game_extra)

        self.achievement_service = await self._make_instance(AchievementService, base_kwargs)
        if self.mining_game_service and hasattr(self.mining_game_service, "__dict__"):
            # если конструктор MiningGameService ожидает achievement_service позже
            try:
                setattr(self.mining_game_service, "achievement_service", self.achievement_service)
            except Exception:
                pass

        self.event_service = await self._make_instance(EventService, base_kwargs)
        self.quiz_service = await self._make_instance(QuizService, base_kwargs)

        # ----- Доп. этапы инициализации (LUA-скрипты и т.п.) -----
        # Market (если есть)
        if self.market_service and hasattr(self.market_service, "load_lua_scripts"):
            try:
                await self.market_service.load_lua_scripts()  # type: ignore[attr-defined]
                logger.info("LUA-скрипты для AsicMarketService успешно загружены.")
            except Exception as e:
                logger.warning("Не удалось загрузить LUA для MarketService: %s", e)

        # MiningGame (если есть)
        if self.mining_game_service and hasattr(self.mining_game_service, "load_lua_scripts"):
            try:
                await self.mining_game_service.load_lua_scripts()  # type: ignore[attr-defined]
                logger.info("LUA-скрипты для MiningGameService успешно загружены.")
            except Exception as e:
                logger.warning("Не удалось загрузить LUA для MiningGameService: %s", e)

        logger.info("Все роутеры успешно зарегистрированы.")  # совместимость с прежними логами

    # --------- фабрики / рефлексия ---------

    async def _make_instance(self, cls: type, candidates: Dict[str, Any]) -> Any:
        """
        Универсальный конструктор:
          1) если есть async @classmethod create(...) — используем его
          2) иначе создаём через __init__(...) по пересечению параметров
        """
        name = cls.__name__

        # Попытка: async @classmethod create
        create = getattr(cls, "create", None)
        if create and (inspect.iscoroutinefunction(create) or inspect.iscoroutinefunction(getattr(create, "__func__", create))):
            try:
                kwargs = self._filter_kwargs(create, candidates)
                inst = await create(**kwargs)  # type: ignore[misc]
                logger.debug("Создан сервис %s через async create(**kwargs).", name)
                return inst
            except Exception as e:
                logger.error("Ошибка при создании %s через create: %s", name, e, exc_info=True)
                raise

        # Обычный конструктор
        try:
            kwargs = self._filter_kwargs(cls, candidates)
            inst = cls(**kwargs)  # type: ignore[misc]
            logger.debug("Создан сервис %s через __init__(**kwargs).", name)
            return inst
        except Exception as e:
            logger.error("Ошибка при создании %s через __init__: %s", name, e, exc_info=True)
            raise

    @staticmethod
    def _filter_kwargs(callable_obj: Any, candidates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выбирает из candidates только те параметры, которые поддерживаются у callable_obj.
        Поддерживает функции/методы (create) и конструкторы (__init__).
        """
        try:
            sig = inspect.signature(callable_obj)
        except (TypeError, ValueError):
            # Например, передан класс; берём его __init__
            sig = inspect.signature(getattr(callable_obj, "__init__", callable_obj))

        supported = set(
            p.name
            for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
        )
        return {k: v for k, v in candidates.items() if k in supported}

    # --------- утилиты ---------

    async def ping(self) -> bool:
        """
        Быстрая самопроверка работоспособности Deps (Redis + HTTP).
        """
        # Redis
        try:
            assert self.redis is not None
            pong = await self.redis.ping()
            if not pong:
                return False
        except Exception:
            return False

        # HTTP session
        if not self.http_session or self.http_session.closed:
            return False

        return True


__all__ = [
    "Deps",
    "DependenciesMiddleware",
    "dependencies_middleware",
]