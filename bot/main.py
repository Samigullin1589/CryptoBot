# ======================================================================================
# Файл: bot/main.py
# Версия: "Distinguished Engineer" — ПРОДАКШН-СБОРКА (aiogram 3.x, Aug 21, 2025)
# Описание:
#   • Полная инициализация бота (настройки, DI, middlewares, routers, команды)
#   • Плановые задачи (jobs/scheduled_tasks)
#   • Корректное завершение (await deps.close()) и обработка сигналов
#   • AdminService, ModerationService, SecurityService создаются после Bot
#     и безопасно добавляются в DI-контейнер deps.
#   • Полностью асинхронная инициализация без блокирующих вызовов.
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
from bot.utils.logging_setup import setup_logging

# ===== Middlewares =====
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.security_middleware import SecurityMiddleware

logger = logging.getLogger(__name__)


# ----------------------------- Команды бота -----------------------------------

async def setup_commands(bot: Bot) -> None:
    """Устанавливает команды, видимые пользователям в меню Telegram."""
    commands: list[BotCommand] = [
        BotCommand(command="start", description="Перезапустить бота"),
        BotCommand(command="help", description="Помощь и справка"),
        BotCommand(command="ask", description="Задать вопрос AI-консультанту (в ЛС)"),
        BotCommand(command="check", description="Проверить пользователя"),
        BotCommand(command="admin", description="Панель администратора"),
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
    """Безопасно импортирует модуль, возвращая None в случае ошибки."""
    try:
        return import_module(module_path)
    except ImportError as e:
        logger.debug("Модуль %s не загружен: %s", module_path, e)
        return None


def register_routers(dp: Dispatcher) -> None:
    """
    Импортирует и регистрирует все известные роутеры проекта.
    Если какой-то модуль отсутствует — просто пропускаем.
    """
    module_paths: list[str] = [
        # --- Public Handlers ---
        "bot.handlers.public.start_handler",
        "bot.handlers.public.common_handler",
        "bot.handlers.public.onboarding_handler",
        "bot.handlers.public.menu_handlers",
        "bot.handlers.public.price_handler",
        "bot.handlers.public.asic_handler",
        "bot.handlers.public.news_handler",
        "bot.handlers.public.quiz_handler",
        "bot.handlers.public.market_info_handler",
        "bot.handlers.public.crypto_center_handler",
        "bot.handlers.public.achievements_handler",
        "bot.handlers.public.verification_public_handler",
        "bot.handlers.public.text_handler", # Должен идти последним из public
        
        # --- Tool Handlers ---
        "bot.handlers.tools.calculator_handler",

        # --- Game Handlers ---
        "bot.handlers.game.mining_game_handler",

        # --- Threat/Spam Handlers ---
        "bot.handlers.threats.threat_handler",

        # --- Admin Handlers ---
        "bot.handlers.admin.admin_menu",
        "bot.handlers.admin.moderation_handler",
        "bot.handlers.admin.stats_handler",
        "bot.handlers.admin.game_admin_handler",
        "bot.handlers.admin.verification_admin_handler",
        "bot.handlers.admin.cache_handler",
        "bot.handlers.admin.health_handler",
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

    logger.info("Всего роутеров успешно зарегистрировано: %s", total)


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
        res = setup(deps, dp)
        if inspect.isawaitable(res):
            await res
        logger.info("Все периодические задачи успешно настроены.")
    else:
        logger.info("В модуле scheduled_tasks нет setup_scheduler — пропускаю.")


# ------------------------ Сигналы и остановка ---------------------------------

def _bind_signals(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    """Назначает обработчик на сигналы SIGINT и SIGTERM."""
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


# --------- Фабрика для безопасного создания сервисов ---------

async def _safe_make_instance_async(cls: Type, candidates: dict[str, Any]) -> Any:
    """Универсальная безопасная фабрика для создания экземпляров сервисов."""
    create = getattr(cls, "create", None)
    if callable(create):
        res = create(**_filter_kwargs(create, candidates))
        if inspect.isawaitable(res):
            return await res
        return res
    return cls(**_filter_kwargs(cls, candidates))


def _filter_kwargs(callable_obj: Any, candidates: dict[str, Any]) -> dict[str, Any]:
    """Фильтрует kwargs, оставляя только те, что принимает конструктор/функция."""
    target = getattr(callable_obj, "__init__", callable_obj) if inspect.isclass(callable_obj) else callable_obj
    try:
        sig = inspect.signature(target)
        supported = {p.name for p in sig.parameters.values()}
        return {k: v for k, v in candidates.items() if k in supported}
    except (TypeError, ValueError):
        return {}


# -------------------- Создание сервисов модерации и безопасности -------------------------

async def _init_moderation_and_security(deps: Deps, bot: Bot) -> None:
    """Создаёт и инициализирует сервисы модерации и безопасности."""
    base_kwargs: dict[str, Any] = {
        "bot": bot, "settings": settings, "redis": deps.redis,
        "user_service": deps.user_service, "admin_service": deps.admin_service,
        "ai_content_service": deps.ai_content_service
    }

    # Сервисы безопасности (опциональные)
    services_to_init = {
        "ModerationService": "bot.services.moderation_service",
        "SecurityService": "bot.services.security_service"
    }
    for class_name, module_path in services_to_init.items():
        if mod := _import_optional(module_path):
            if service_class := getattr(mod, class_name, None):
                try:
                    instance = await _safe_make_instance_async(service_class, base_kwargs)
                    setattr(deps, class_name.lower().replace("service", "_service"), instance)
                    base_kwargs[class_name.lower().replace("service", "_service")] = instance
                    logger.info("%s инициализирован.", class_name)
                except Exception as e:
                    logger.warning("%s не удалось инициализировать: %s", class_name, e)


# --------------------------------- main() -------------------------------------

async def main() -> None:
    """Основная асинхронная функция запуска бота."""
    setup_logging(level=settings.log_level, format="text")

    deps = await Deps.create(settings)
    bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # AdminService зависит от bot, поэтому создаём его здесь
    if mod := _import_optional("bot.services.admin_service"):
        if service_class := getattr(mod, "AdminService", None):
            deps.admin_service = service_class(bot=bot, redis=deps.redis, settings=settings)
            logger.info("AdminService инициализирован.")

    await _init_moderation_and_security(deps, bot)

    # Middlewares (порядок важен)
    dp.update.outer_middleware(dependencies_middleware(deps))
    dp.update.outer_middleware(ActivityMiddleware())
    if deps.security_service:
        dp.update.outer_middleware(SecurityMiddleware(deps=deps))
    dp.update.outer_middleware(ThrottlingMiddleware(deps=deps))

    register_routers(dp)
    await setup_commands(bot)
    await setup_scheduler(deps, dp)

    logger.info("Запуск бота...")
    stop_event = asyncio.Event()
    _bind_signals(asyncio.get_running_loop(), stop_event)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), stop_event=stop_event)
    finally:
        logger.info("Завершение работы бота...")
        await deps.close()
        await bot.session.close()
        logger.info("Бот остановлен.")


# --------------------------------- Entrypoint ---------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Выход из программы.")