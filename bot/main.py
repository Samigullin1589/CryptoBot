# ======================================================================================
# Файл: bot/main.py
# Версия: "Distinguished Engineer" — ФИНАЛЬНАЯ СБОРКА (25 августа 2025)
# Описание:
#   • ИСПРАВЛЕНО: Удалена лишняя строка инициализации конфигурации,
#     вызывавшая AttributeError при запуске.
# ======================================================================================

from __future__ import annotations

import asyncio
import inspect
import logging
import signal
from importlib import import_module
from typing import Any

from aiogram import Bot, Dispatcher, Router
from aiogram.types import BotCommand

from bot.config.settings import settings
from bot.containers import Container
from bot.utils.dependencies import dependencies_middleware
from bot.utils.logging_setup import setup_logging
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.action_tracking_middleware import ActionTrackingMiddleware

logger = logging.getLogger(__name__)


async def setup_commands(bot: Bot) -> None:
    """Устанавливает команды, видимые пользователям в меню Telegram."""
    commands: list[BotCommand] = [
        BotCommand(command="start", description="Перезапустить бота"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="help", description="Помощь и справка"),
        BotCommand(command="ask", description="Задать вопрос AI-консультанту (в ЛС)"),
        BotCommand(command="check", description="Проверить пользователя"),
        BotCommand(command="admin", description="Панель администратора"),
    ]
    await bot.set_my_commands(commands)


def _collect_routers_from_module(module: Any) -> list[Router]:
    """Ищет все объекты Router в модуле."""
    routers: list[Router] = []
    for name, obj in vars(module).items():
        if isinstance(obj, Router):
            if not obj.name:
                obj.name = name
            routers.append(obj)
    return routers


def _import_optional(module_path: str) -> object | None:
    """Безопасно импортирует модуль."""
    try:
        return import_module(module_path)
    except ImportError as e:
        logger.debug("Модуль %s не загружен: %s", module_path, e)
        return None


def register_routers(dp: Dispatcher) -> None:
    """Импортирует и регистрирует все роутеры проекта напрямую."""
    module_paths: list[str] = [
        "bot.handlers.public.start_handler", "bot.handlers.public.menu_handlers",
        "bot.handlers.public.help_handler", "bot.handlers.public.common_handler",
        "bot.handlers.public.onboarding_handler", "bot.handlers.public.price_handler",
        "bot.handlers.public.asic_handler", "bot.handlers.public.news_handler",
        "bot.handlers.public.quiz_handler", "bot.handlers.public.market_info_handler",
        "bot.handlers.public.crypto_center_handler", "bot.handlers.public.achievements_handler",
        "bot.handlers.public.verification_public_handler", "bot.handlers.public.game_handler",
        "bot.handlers.public.market_handler", "bot.handlers.tools.calculator_handler",
        "bot.handlers.game.mining_game_handler", "bot.handlers.threats.threat_handler",
        "bot.handlers.admin.admin_menu", "bot.handlers.admin.moderation_handler",
        "bot.handlers.admin.stats_handler", "bot.handlers.admin.game_admin_handler",
        "bot.handlers.admin.verification_admin_handler", "bot.handlers.admin.cache_handler",
        "bot.handlers.admin.health_handler", "bot.handlers.admin.version_handler",
        "bot.handlers.public.text_handler",
    ]

    registered_routers_count = 0
    for path in module_paths:
        module = _import_optional(path)
        if module:
            routers = _collect_routers_from_module(module)
            if routers:
                for router in routers:
                    dp.include_router(router)
                    registered_routers_count += 1
                    logger.debug(f"Роутер '{router.name}' из модуля '{path}' успешно зарегистрирован.")

    logger.info("Всего роутеров успешно зарегистрировано: %s", registered_routers_count)


async def setup_scheduler(container: Container) -> None:
    """Подключает плановые задачи."""
    mod = _import_optional("bot.jobs.scheduled_tasks")
    if not mod:
        logger.info("Модуль планировщика не найден — пропускаю.")
        return
    setup = getattr(mod, "setup_scheduler", None)
    if callable(setup):
        res = setup(container)
        if inspect.isawaitable(res):
            await res
        logger.info("Все периодические задачи успешно настроены.")


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
            pass


async def main() -> None:
    """Основная асинхронная функция запуска бота."""
    setup_logging(level=settings.log_level, format="text")

    container = Container()
    # ИСПРАВЛЕНО: Эта строка удалена, так как она вызывала ошибку
    # container.config.from_object(settings) 
    container.wire(
        modules=[__name__],
        packages=["bot.handlers", "bot.middlewares", "bot.jobs"],
    )
    
    bot = await container.bot()
    dp = Dispatcher()
    
    # Регистрация middleware
    dp.update.outer_middleware(dependencies_middleware)
    dp.update.outer_middleware(ActivityMiddleware())
    dp.update.outer_middleware(ActionTrackingMiddleware(admin_service=await container.admin_service()))
    dp.update.outer_middleware(ThrottlingMiddleware(deps=data['deps']))
    
    # Регистрация роутеров
    register_routers(dp)
    
    await setup_commands(bot)
    await container.init_resources()
    await setup_scheduler(container)

    logger.info("Запуск бота...")
    stop_event = asyncio.Event()
    _bind_signals(asyncio.get_running_loop(), stop_event)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), stop_event=stop_event)
    finally:
        logger.info("Завершение работы бота...")
        await container.shutdown_resources()
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Выход из программы.")