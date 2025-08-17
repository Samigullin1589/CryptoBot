# ======================================================================================
# Файл: bot/utils/dependencies.py
# Версия: "Distinguished Engineer" — МАКСИМАЛЬНАЯ (DI с безопасными опционалами)
# ======================================================================================

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional, Type

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
from bot.services.admin_service import AdminService  # noqa: F401

# Безопасность / модерация — ДЕЛАЕМ ОПЦИОНАЛЬНЫМИ (не создаём в DI)
try:
    from bot.services.security_service import SecurityService  # type: ignore
except Exception:  # noqa: BLE001
    SecurityService = None  # type: ignore

try:
    from bot.services.moderation_service import ModerationService  # type: ignore
except Exception:  # noqa: BLE001
    ModerationService = None  # type: ignore


logger = logging.getLogger(__name__)


# =============================== Middleware (deps) ===============================

class DependenciesMiddleware(BaseMiddleware):
    """Кладёт экземпляр Deps в data каждого апдейта."""
    def __init__(self, deps: "Deps") -> None:
        super().__init__()
        self.deps = deps

    async def __call__(self, handler, event, data):
        data["deps"] = self.deps
        return await handler(event, data)


def dependencies_middleware(deps: "Deps") -> DependenciesMiddleware:
    return DependenciesMiddleware(deps)


# ================================ DI-контейнер ==================================

class Deps:
    """
    Контейнер зависимостей.
    """

    def __init__(self, cfg: Settings) -> None:
        self.settings: Settings = cfg

        # низкоуровневые ресурсы
        self.redis_pool: Optional[redis.Redis] = None
        self.redis: Optional[redis.Redis] = None
        self.http_session: Optional[aiohttp.ClientSession] = None

        # доменные сервисы
        self.ai_content_service: Optional[AIContentService] = None
        self.ai_service: Optional[AIContentService] = None  # alias
        self.price_service: Optional[PriceService] = None
        self.coin_list_service: Optional[CoinListService] = None
        self.news_service: Optional[NewsService] = None
        self.market_data_service: Optional[MarketDataService] = None
        self.asic_service: Optional[AsicService] = None
        self.market_service: Optional[MarketService] = None
        self.mining_service: Optional[MiningService] = None
        self.mining_game_service: Optional[MiningGameService] = None
        self.achievement_service: Optional[AchievementService] = None
        self.event_service: Optional[EventService] = None
        self.quiz_service: Optional[QuizService] = None
        self.user_service: Optional[UserService] = None

        # опциональные (создаём позже в main.py)
        self.moderation_service: Optional[Any] = None
        self.security_service: Optional[Any] = None
        self.admin_service: Optional[AdminService] = None

    # --- фабрика ---

    @classmethod
    async def create(cls, cfg: Settings | None = None) -> "Deps":
        cfg = cfg or settings
        self = cls(cfg)
        try:
            await self._init_low_level()
            await self._init_services()
            logger.info("Контейнер зависимостей (Deps) успешно собран.")
            return self
        except Exception:
            with contextlib.suppress(Exception):
                await self.close()
            raise

    async def init(self) -> None:
        await self._init_low_level()
        await self._init_services()
        logger.info("Контейнер зависимостей (Deps) успешно собран.")

    async def close(self) -> None:
        # Закрываем сервисы
        for svc_name in [
            "ai_content_service",
            "price_service",
            "coin_list_service",
            "news_service",
            "market_data_service",
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
                    break

        # HTTP-сессия
        if self.http_session and not self.http_session.closed:
            try:
                await self.http_session.close()
            except Exception as e:
                logger.warning("Ошибка при закрытии http_session: %s", e)

        # Redis
        if self.redis_pool is not None:
            try:
                aclose = getattr(self.redis_pool, "aclose", None)
                if callable(aclose):
                    await aclose()
                else:
                    await self.redis_pool.close()
            except Exception as e:
                logger.warning("Ошибка при закрытии Redis: %s", e)

    # --------- низкоуровневые ресурсы ---------

    async def _init_low_level(self) -> None:
        self.redis_pool = redis.from_url(
            str(self.settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
        self.redis = self.redis_pool
        await self.redis_pool.ping()
        logger.info("Успешное подключение к Redis.")

        timeout = aiohttp.ClientTimeout(total=30)
        self.http_session = aiohttp.ClientSession(timeout=timeout, raise_for_status=False, trust_env=True)

        logger.info(
            "AIContentService: провайдер=%s, model=%s (flash=%s).",
            self.settings.ai.provider,
            self.settings.ai.model_name,
            self.settings.ai.flash_model_name,
        )

    # --------- доменные сервисы ---------

    async def _init_services(self) -> None:
        base_kwargs: Dict[str, Any] = {
            "settings": self.settings,
            "cfg": self.settings,
            "config": self.settings,
            "redis": self.redis,
            "redis_pool": self.redis_pool,
            "http_session": self.http_session,
            "session": self.http_session,
            "endpoints": self.settings.endpoints,
            "ai_config": self.settings.ai,
            "gemini_api_key": self.settings.GEMINI_API_KEY.get_secret_value(),
        }

        # Базовые
        self.user_service = await self._make_instance(UserService, base_kwargs)

        self.ai_content_service = await self._make_instance(AIContentService, base_kwargs)
        self.ai_service = self.ai_content_service
        base_kwargs |= {"ai_content_service": self.ai_content_service, "ai_service": self.ai_content_service}

        # Монеты / рынок как основа
        self.coin_list_service = await self._make_instance(CoinListService, base_kwargs)
        base_kwargs |= {"coin_list_service": self.coin_list_service}

        self.market_data_service = await self._make_instance(
            MarketDataService,
            base_kwargs | {"coin_list_service": self.coin_list_service},
        )
        base_kwargs |= {"market_data_service": self.market_data_service}

        # Цены и новости
        self.price_service = await self._make_instance(
            PriceService,
            base_kwargs | {"coin_list_service": self.coin_list_service},
        )
        self.news_service = await self._make_instance(NewsService, base_kwargs)

        # Опциональный парсер для AsicService
        parser_service = None
        for module_path, class_name in [
            ("bot.services.parser_service", "ParserService"),
            ("bot.services.asic_parser_service", "AsicParserService"),
            ("bot.services.parsers.asic", "ParserService"),
        ]:
            try:
                mod = import_module(module_path)
                cls: Optional[Type[Any]] = getattr(mod, class_name, None)  # type: ignore[assignment]
                if cls:
                    parser_service = await self._make_instance(cls, base_kwargs)
                    break
            except Exception:
                continue

        # Майнинг / рынок / ASIC
        self.asic_service = await self._make_instance(
            AsicService,
            base_kwargs | {"parser_service": parser_service},
        )
        base_kwargs |= {"asic_service": self.asic_service}

        self.market_service = await self._make_instance(
            MarketService,
            base_kwargs | {"asic_service": self.asic_service},
        )
        base_kwargs |= {"market_service": self.market_service}

        self.mining_service = await self._make_instance(
            MiningService,
            base_kwargs | {"market_data_service": self.market_data_service},
        )
        base_kwargs |= {"mining_service": self.mining_service}

        # ---- AchievementService (разные сигнатуры) ----
        achievements_cfg_path = (
            getattr(self.settings, "ACHIEVEMENTS_CONFIG_PATH", None)
            or getattr(self.settings, "achievements_config_path", None)
            or getattr(getattr(self.settings, "paths", None) or object(), "achievements", None)
            or "bot/config/achievements.yaml"
        )
        if not Path(str(achievements_cfg_path)).is_file():
            logger.warning("Achievement config file not found: %s — продолжу без падения", achievements_cfg_path)

        def _param_names(callable_obj: Any) -> set[str]:
            try:
                sig = inspect.signature(callable_obj)
            except (TypeError, ValueError):
                sig = inspect.signature(getattr(callable_obj, "__init__", callable_obj))
            return {
                p.name
                for p in sig.parameters.values()
                if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
            }

        ach_param_names = _param_names(AchievementService)

        class _SettingsProxy:
            """Прозрачный прокси Settings с добавленным config_path для старых реализаций."""
            def __init__(self, base: Settings, config_path: str) -> None:
                self.__dict__["_base"] = base
                self.__dict__["config_path"] = config_path

            def __getattr__(self, item: str) -> Any:
                return getattr(self.__dict__["_base"], item)

            def __setattr__(self, key: str, value: Any) -> None:
                self.__dict__[key] = value

        ach_kwargs = base_kwargs | {"market_data_service": self.market_data_service}
        if "config" in ach_param_names:
            ach_kwargs |= {"config": SimpleNamespace(config_path=str(achievements_cfg_path))}
        elif "settings" in ach_param_names:
            ach_kwargs |= {"settings": _SettingsProxy(self.settings, str(achievements_cfg_path))}

        self.achievement_service = await self._make_instance(AchievementService, ach_kwargs)
        base_kwargs |= {"achievement_service": self.achievement_service}

        # Игровые сервисы
        self.mining_game_service = await self._make_instance(
            MiningGameService,
            base_kwargs,
        )

        self.event_service = await self._make_instance(EventService, base_kwargs)

        # ВАЖНО: теперь QuizService получит ai_content_service из base_kwargs
        self.quiz_service = await self._make_instance(QuizService, base_kwargs)

        # ----- Доп. этапы (LUA) -----
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

    # --------- фабрика инстансов ---------

    async def _make_instance(self, cls: type, candidates: Dict[str, Any]) -> Any:
        name = cls.__name__

        create = getattr(cls, "create", None)
        if create and (inspect.iscoroutinefunction(create) or inspect.iscoroutinefunction(getattr(create, "__func__", create))):
            kwargs = self._filter_kwargs(create, candidates)
            inst = await create(**kwargs)  # type: ignore[misc]
            logger.debug("Создан сервис %s через async create(**kwargs).", name)
            return inst

        kwargs = self._filter_kwargs(cls, candidates)
        inst = cls(**kwargs)  # type: ignore[misc]
        logger.debug("Создан сервис %s через __init__(**kwargs).", name)
        return inst

    @staticmethod
    def _filter_kwargs(callable_obj: Any, candidates: Dict[str, Any]) -> Dict[str, Any]:
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
        try:
            assert self.redis is not None
            if not await self.redis.ping():
                return False
        except Exception:
            return False
        return bool(self.http_session and not self.http_session.closed)


__all__ = [
    "Deps",
    "DependenciesMiddleware",
    "dependencies_middleware",
]