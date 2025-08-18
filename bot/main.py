# ======================================================================================
# Файл: bot/main.py
# Версия: "Distinguished Engineer" — ПРОДАКШН-СБОРКА (aiogram 3.x, Aug 17, 2025)
# Описание:
#   • Полная инициализация бота (настройки, DI, middlewares, routers, команды)
#   • Плановые задачи (jobs/scheduled_tasks)
#   • Корректное завершение (await deps.close()) и обработка сигналов
#   • AdminService создаётся ПОСЛЕ Bot (ему нужен bot)
#   • Здесь же создаём ModerationService и SecurityService и сохраняем в deps.*
#   • ZERO sync-хакинга: никаких run_until_complete внутри async-кода
# ======================================================================================

from __future__ import annotations

import asyncio
import inspect
import logging
import signal
from importlib import import_module
from typing import Any, Type

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config.settings import settings
from bot.utils.dependencies import Deps, dependencies_middleware

# ===== Middlewares =====
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.middlewares.activity_middleware import ActivityMiddleware

try:
    from bot.middlewares.security_middleware import SecurityMiddleware  # антиспам/фильтры
except Exception:  # noqa: BLE001
    SecurityMiddleware = None  # type: ignore

logger = logging.getLogger(__name__)


# -------------------------------- Логирование ---------------------------------

def setup_logging() -> None:
    level = getattr(logging, getattr(settings, "log_level", "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    # aiogram достаточно «шумный» — чуть приглушим
    logging.getLogger("aiogram.event").setLevel(logging.INFO)
    logging.getLogger("aiogram.dispatcher").setLevel(logging.INFO)


# ----------------------------- Команды бота -----------------------------------

async def setup_commands(bot: Bot) -> None:
    commands: list[BotCommand] = [
        BotCommand(command="start", description="Запуск"),
        BotCommand(command="help", description="Справка"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="price", description="Котировки"),
        BotCommand(command="news", description="Крипто-новости"),
        BotCommand(command="convert", description="Калькулятор: конвертация"),
        BotCommand(command="pnl", description="Калькулятор: PnL"),
        BotCommand(command="roi", description="Калькулятор: ROI"),
        # Админ-команды не выставляем глобально, чтобы не «светить» их всем.
    ]
    await bot.set_my_commands(commands)


# ------------------------ Регистрация роутеров --------------------------------

def _collect_routers(module: Any) -> list[Router]:
    """Ищет все объекты Router в модуле (router, *_router и т.п.)."""
    routers: list[Router] = []
    for _, obj in vars(module).items():
        if isinstance(obj, Router):
            routers.append(obj)
    return routers


def _import_optional(module_path: str) -> object | None:
    try:
        return import_module(module_path)
    except Exception as e:  # noqa: BLE001
        logger.debug("Модуль %s не загружен: %s", module_path, e)
        return None


def register_routers(dp: Dispatcher) -> None:
    """
    Импортирует и регистрирует все известные роутеры проекта.
    Если какой-то модуль отсутствует — просто пропускаем (без заглушек).
    """
    module_paths: list[str] = [
        # --- public ---
        "bot.handlers.public.start_handler",
        "bot.handlers.public.help_handler",
        "bot.handlers.public.menu_handler",
        "bot.handlers.public.text_handler",
        "bot.handlers.public.price_handler",
        "bot.handlers.public.news_handler",
        "bot.handlers.public.onboarding_handler",

        # --- tools ---
        "bot.handlers.tools.calculator_handler",

        # --- game ---
        "bot.handlers.game.mining_game_handler",

        # --- threats ---
        "bot.handlers.threats",

        # --- admin ---
        "bot.handlers.admin.admin_handler",
        "bot.handlers.admin.moderation_handler",
        "bot.handlers.admin.stats_handler",
        "bot.handlers.admin.health_handler",
        "bot.handlers.admin.cache_handler",
        "bot.handlers.admin.version_handler",
    ]

    total = 0
    for mp in module_paths:
        mod = _import_optional(mp)
        if not mod:
            continue
        routers = _collect_routers(mod)
        for r in routers:
            dp.include_router(r)
            total += 1

    logger.info("Все роутеры успешно зарегистрированы. Кол-во: %s", total)


# ------------------------ Плановые задачи (jobs) -------------------------------

async def setup_scheduler(deps: Deps, dp: Dispatcher) -> None:
    """
    Подключает плановые задачи, если модуль есть в проекте.
    Ожидается, что внутри есть функция setup_scheduler(deps, dp).
    """
    mod = _import_optional("bot.jobs.scheduled_tasks")
    if not mod:
        logger.info("Модуль планировщика не найден: bot.jobs.scheduled_tasks — пропускаю.")
        return
    setup = getattr(mod, "setup_scheduler", None)
    if callable(setup):
        # поддержим и sync, и async вариант
        res = setup(deps, dp)  # type: ignore[misc]
        if inspect.isawaitable(res):
            await res
        logger.info("Все периодические задачи успешно настроены.")
    else:
        logger.info("В модуле scheduled_tasks нет setup_scheduler — пропускаю.")


# ------------------------ Сигналы и остановка ---------------------------------

def _bind_signals(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    def _handler(*_: object) -> None:
        if not stop.is_set():
            logger.warning("Получен сигнал остановки — завершаем polling...")
            stop.set()

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, _handler)
        except NotImplementedError:
            # Windows / контейнеры без поддержки сигналов
            pass


# --------- Вспомогательная фабрика (безопасное создание по сигнатуре) ---------

def _filter_kwargs(callable_obj: Any, candidates: dict[str, Any]) -> dict[str, Any]:
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


async def _safe_make_instance_async(cls: Type, candidates: dict[str, Any]) -> Any:
    """
    Универсальная безопасная фабрика:
      • если есть create(...): вызываем, await если нужно
      • иначе конструктор __init__(...) по пересечению параметров
    НИКАКИХ run_until_complete — только чистый async.
    """
    create = getattr(cls, "create", None)
    if callable(create):
        kwargs = _filter_kwargs(create, candidates)
        res = create(**kwargs)  # type: ignore[misc]
        if inspect.isawaitable(res):
            return await res
        return res
    kwargs = _filter_kwargs(cls, candidates)
    return cls(**kwargs)  # type: ignore[misc]


# -------------------- Создание модерации/безопасности -------------------------

async def _init_moderation_and_security(deps: Deps, bot: Bot) -> None:
    """
    Создаёт ModerationService и SecurityService и сохраняет в deps.
    Все импорты и зависимости — опционально, чтобы не валить процесс.
    Полностью асинхронно и безопасно.
    """
    # Сбор общих кандидатов для конструкторов
    base_kwargs: dict[str, Any] = {
        "bot": bot,
        "settings": settings,
        "config": settings,         # если сервис ждёт параметр 'config'
        "redis": deps.redis,
        "http_session": deps.http_session,
        "user_service": deps.user_service,
        "admin_service": deps.admin_service,
        "ai_content_service": deps.ai_content_service,
        "moderation_service": deps.moderation_service,  # будет обновлён после создания
        "security_service": deps.security_service,
    }

    # Необязательный StopWordService
    try:
        from bot.services.stop_word_service import StopWordService  # type: ignore
        try:
            sws = await _safe_make_instance_async(StopWordService, base_kwargs)
            base_kwargs["stop_word_service"] = sws
            logger.info("StopWordService инициализирован.")
        except Exception as e:
            logger.warning("StopWordService init failed: %s", e, exc_info=True)
    except Exception:
        logger.info("StopWordService не найден — продолжаю без него.")

    # ModerationService
    try:
        from bot.services.moderation_service import ModerationService  # type: ignore
        deps.moderation_service = await _safe_make_instance_async(ModerationService, base_kwargs)
        base_kwargs["moderation_service"] = deps.moderation_service
        logger.info("ModerationService инициализирован.")
    except Exception as e:
        deps.moderation_service = None
        logger.warning("ModerationService init failed: %s", e, exc_info=True)

    # SecurityService (если есть)
    try:
        from bot.services.security_service import SecurityService  # type: ignore
        deps.security_service = await _safe_make_instance_async(SecurityService, base_kwargs)
        logger.info("SecurityService инициализирован.")
    except Exception as e:
        deps.security_service = None
        logger.info("SecurityService недоступен или не инициализировался: %s", e)


# --------------------------------- main() -------------------------------------

async def main() -> None:
    setup_logging()
    logger.info("Конфигурация успешно загружена и валидирована.")

    # DI контейнер
    deps = await Deps.create(settings)

    # Бот и диспетчер
    bot = Bot(
        token=settings.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # --- AdminService зависит от bot, поэтому создаём его здесь и кладём в deps ---
    try:
        from bot.services.admin_service import AdminService
        deps.admin_service = AdminService(redis=deps.redis, settings=settings, bot=bot)  # type: ignore[arg-type]
        logger.info("AdminService инициализирован.")
    except Exception as e:  # noqa: BLE001
        deps.admin_service = None
        logger.warning("AdminService init failed: %s", e, exc_info=True)

    # --- ModerationService / SecurityService создаём здесь и сохраняем в deps ---
    await _init_moderation_and_security(deps, bot)

    # Middlewares (порядок важен: deps → активность → антиспам → троттлинг)
    dp.update.outer_middleware(dependencies_middleware(deps))
    dp.update.outer_middleware(ActivityMiddleware())
    if SecurityMiddleware:
        try:
            dp.update.outer_middleware(SecurityMiddleware(deps=deps))
            logger.info("SecurityMiddleware подключён.")
        except Exception as e:  # noqa: BLE001
            logger.warning("Не удалось подключить SecurityMiddleware: %s", e)

    dp.update.outer_middleware(
        ThrottlingMiddleware(
            deps=deps,
            user_rate=settings.throttling.user_rate_limit,
            chat_rate=settings.throttling.chat_rate_limit,
            key_prefix=settings.throttling.key_prefix,
            exempt_admins=True,
            feedback=True,
        )
    )

    # Роутеры
    register_routers(dp)

    # Команды
    await setup_commands(bot)

    # Плановые задачи
    await setup_scheduler(deps, dp)

    logger.info("Запуск бота...")
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    _bind_signals(loop, stop_event)

    # Сбросим вебхук (если был) и очистим подвисшие апдейты
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    # Aiogram 3: получим список типов апдейтов, чтобы Telegram не ругался
    try:
        allowed = dp.resolve_used_update_types()
    except Exception:
        allowed = None

    try:
        logger.info("Start polling")
        await dp.start_polling(
            bot,
            allowed_updates=allowed,
            stop_event=stop_event,
        )
    finally:
        logger.info("Запуск процедур on_shutdown...")
        try:
            await deps.close()
        finally:
            # Закрываем HTTP-сессию бота (на всякий случай)
            try:
                await bot.session.close()
            except Exception:
                pass
        logger.info("Процедуры on_shutdown завершены.")


# --------------------------------- Entrypoint ---------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
