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
#     • Совместимость: поддержаны и Deps.create(...), и Deps(...); await deps.init().
#     • MarketDataService создаётся внутри DI; AdminService — позже в main.py (ему нужен bot).
# ======================================================================================

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Dict, Optional

import aiohttp
import redis.asyncio as redis
from aiogram import BaseMiddleware

from bot.config.settings import settings, Settings

# ===== Импорты доменных сервисов (боевой режим — без заглушек) =====

# AI / LLM
from bot.services.ai_content_service import AIContentService  # noqa: F401

# Крипто-сервисы
from bot.services.price_service import PriceService  # noqa: F401
from bot.services.coin_list_service import CoinListService  # noqa: F401
from bot.services.news_service import NewsService  # noqa: F401
from bot.services.market_data_service import MarketDataService  # noqa: F401

# Безопасность / модерация
from bot.services.security_service import SecurityService  # noqa: F401
from bot.services.moderation_service import ModerationService  # noqa: F401

# ASIC / рынок / майнинг
from bot.services.asic_service import AsicService  # noqa: F401
from bot.services.market_service import MarketService  # noqa: F401
from bot.services.mining_service import MiningService  # noqa: F401
from bot.services.mining_game_service import MiningGameService  # noqa: F401

# Геймификация
from bot.services.achievement_service import AchievementService  # noqa: F401
from bot.services.event_service import EventService  # noqa: F401
from bot.services.quiz_service import QuizService  # noqa: F401

# Пользователи / Админ
from bot.services.user_service import UserService  # noqa: F401
# ВАЖНО: AdminService импортировать можно, но инициализировать — в main.py (нужен bot)
from bot.services.admin_service import AdminService  # noqa: F401


logger = logging.getLogger(__name__)


# =============================== Middleware (deps) ===============================

class DependenciesMiddleware(BaseMiddleware):
    """
    Простой middleware, который кладёт экземпляр Deps в data каждого апдейта.
    Подключается в main.py для router/message/callback_query и пр.
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
    Контейнер зависимостей.

    Доступные поля (основные):
        settings: Settings

        # низкоуровневые ресурсы
        redis_pool: redis.asyncio.Redis
        redis: redis.asyncio.Redis       # алиас
        http_session: aiohttp.ClientSession

        # доменные сервисы
        ai_content_service: AIContentService
        ai_service: AIContentService          # алиас для совместимости
        price_service: PriceService
        coin_list_service: CoinListService
        news_service: NewsService
        market_data_service: MarketDataService
        moderation_service: ModerationService
        security_service: SecurityService
        asic_service: AsicService
        market_service: MarketService
        mining_service: MiningService
        mining_game_service: MiningGameService
        achievement_service: AchievementService
        event_service: EventService
        quiz_service: QuizService
        user_service: UserService
        admin_service: AdminService | None     # ИНИЦИАЛИЗИРУЕТСЯ В main.py (нужен bot)
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
        self.ai_service: Optional[AIContentService] = None  # alias
        self.price_service: Optional[PriceService] = None
        self.coin_list_service: Optional[CoinListService] = None
        self.news_service: Optional[NewsService] = None
        self.market_data_service: Optional[MarketDataService] = None
        self.moderation_service: Optional[ModerationService] = None
        self.security_service: Optional[SecurityService] = None
        self.asic_service: Optional[AsicService] = None
        self.market_service: Optional[MarketService] = None
        self.mining_service: Optional[MiningService] = None
        self.mining_game_service: Optional[MiningGameService] = None
        self.achievement_service: Optional[AchievementService] = None
        self.event_service: Optional[EventService] = None
        self.quiz_service: Optional[QuizService] = None
        self.user_service: Optional[UserService] = None

        # Заполняется в main.py после создания Bot
        self.admin_service: Optional[AdminService] = None

    # --- поддержка обоих вариантов запуска ---

    @classmethod
    async def create(cls, cfg: Settings | None = None) -> "Deps":
        """
        Основная точка входа (фабричный метод): создаёт и настраивает всё необходимое.
        """
        cfg = cfg or settings
        self = cls(cfg)
        await self._init_low_level()
        await self._init_services()
        logger.info("Контейнер зависимостей (Deps) успешно собран.")
        return self

    async def init(self) -> None:
        """
        Альтернативная инициализация для совместимости с существующим main.py:
            deps = Deps(settings)
            await deps.init()
        """
        await self._init_low_level()
        await self._init_services()
        logger.info("Контейнер зависимостей (Deps) успешно собран.")

    async def close(self) -> None:
        """
        Корректное завершение всех ресурсов и сервисов.
        Вызывается из on_shutdown (main.py).
        """
        # Закрываем сервисы, у которых есть async close()/aclose()
        for svc_name in [
            "ai_content_service",
            "price_service",
            "coin_list_service",
            "news_service",
            "market_data_service",
            "security_service",
            "moderation_service",
            "asic_service",
            "market_service",
            "mining_service",
            "mining_game_service",
            "achievement_service",
            "event_service",
            "quiz_service",
            "user_service",
            # admin_service закрывать не требуется
        ]:
            svc = getattr(self, svc_name, None)
            if not svc:
                continue
            for meth in ("aclose", "close"):
                fn = getattr(svc, meth, None)
                if callable(fn):
                    try:
                        res = fn()
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as e:
                        logger.warning("Ошибка при закрытии %s.%s(): %s", svc_name, meth, e)
                    break  # не вызываем второй метод, если первый сработал

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

        # sanity check
        try:
            await self.redis_pool.ping()
            logger.info("Успешное подключение к Redis.")
        except Exception as e:
            logger.critical("Redis ping failed: %s", e, exc_info=True)
            raise

        # HTTP-сессия
        timeout = aiohttp.ClientTimeout(total=30)
        self.http_session = aiohttp.ClientSession(timeout=timeout, raise_for_status=False, trust_env=True)

        # AI / LLM (только лог; сами клиенты поднимет AIContentService)
        logger.info(
            "AIContentService: провайдер=%s, model=%s (flash=%s).",
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
            "session": self.http_session,       # если параметр так называется
            "endpoints": self.settings.endpoints,
            "ai_config": self.settings.ai,
            "gemini_api_key": self.settings.GEMINI_API_KEY.get_secret_value(),
        }

        # Базовые сервисы
        self.user_service = await self._make_instance(UserService, base_kwargs)
        self.ai_content_service = await self._make_instance(AIContentService, base_kwargs)
        # алиас для совместимости с кодом, который ожидает ai_service
        self.ai_service = self.ai_content_service

        self.coin_list_service = await self._make_instance(CoinListService, base_kwargs)
        self.price_service = await self._make_instance(
            PriceService,
            base_kwargs | {"coin_list_service": self.coin_list_service}
        )
        self.news_service = await self._make_instance(NewsService, base_kwargs)

        # Антиспам/безопасность
        self.moderation_service = await self._make_instance(
            ModerationService,
            base_kwargs | {"http": self.http_session}
        )
        self.security_service = await self._make_instance(
            SecurityService,
            base_kwargs | {"moderation_service": self.moderation_service}
        )

        # Майнинг / рынок / ASIC
        self.mining_service = await self._make_instance(MiningService, base_kwargs)
        self.asic_service = await self._make_instance(AsicService, base_kwargs)
        self.market_service = await self._make_instance(
            MarketService,
            base_kwargs | {"asic_service": self.asic_service}
        )

        # Рыночные данные (FX, топ-коины и пр.) — нужен coin_list_service
        self.market_data_service = await self._make_instance(
            MarketDataService,
            base_kwargs | {"coin_list_service": self.coin_list_service}
        )

        # Игровые сервисы (ссылки на другие)
        game_extra = base_kwargs | {
            "user_service": self.user_service,
            "asic_service": self.asic_service,
            "market_service": self.market_service,
            "mining_service": self.mining_service,
            "achievement_service": None,  # заполним после создания achievement_service
        }
        self.mining_game_service = await self._make_instance(MiningGameService, game_extra)

        self.achievement_service = await self._make_instance(AchievementService, base_kwargs)
        if self.mining_game_service and hasattr(self.mining_game_service, "__dict__"):
            try:
                setattr(self.mining_game_service, "achievement_service", self.achievement_service)
            except Exception:
                pass

        self.event_service = await self._make_instance(EventService, base_kwargs)
        self.quiz_service = await self._make_instance(QuizService, base_kwargs)

        # ----- Доп. этапы инициализации (LUA-скрипты и т.п.) -----
        if self.market_service and hasattr(self.market_service, "load_lua_scripts"):
            try:
                await self.market_service.load_lua_scripts()  # type: ignore[attr-defined]
                logger.info("LUA-скрипты для AsicMarketService успешно загружены.")
            except Exception as e:
                logger.warning("Не удалось загрузить LUA для MarketService: %s", e)

        if self.mining_game_service and hasattr(self.mining_game_service, "load_lua_scripts"):
            try:
                await self.mining_game_service.load_lua_scripts()  # type: ignore[attr-defined]
                logger.info("LUA-скрипты для MiningGameService успешно загружены.")
            except Exception as e:
                logger.warning("Не удалось загрузить LUA для MiningGameService: %s", e)

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
            kwargs = self._filter_kwargs(create, candidates)
            inst = await create(**kwargs)  # type: ignore[misc]
            logger.debug("Создан сервис %s через async create(**kwargs).", name)
            return inst

        # Обычный конструктор
        kwargs = self._filter_kwargs(cls, candidates)
        inst = cls(**kwargs)  # type: ignore[misc]
        logger.debug("Создан сервис %s через __init__(**kwargs).", name)
        return inst

    @staticmethod
    def _filter_kwargs(callable_obj: Any, candidates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выбирает из candidates только те параметры, которые поддерживаются у callable_obj.
        Поддерживает функции/методы (create) и конструкторы (__init__).
        """
        try:
            sig = inspect.signature(callable_obj)
        except (TypeError, ValueError):
            sig = inspect.signature(getattr(callable_obj, "__init__", callable_obj))

        supported = {
            p.name
            for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
        }
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