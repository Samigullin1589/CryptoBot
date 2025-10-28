# ======================================================================================
# Файл: bot/main.py
# Версия: ФИНАЛЬНАЯ (28.10.2025) - Distinguished Engineer
# Описание:
#   • ИСПРАВЛЕНО: Правильная работа с Resource провайдерами dependency-injector
#   • Resource провайдеры автоматически инициализируются при первом доступе
#   • Добавлена проверка наличия методов init/shutdown
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
    logger.info("✅ Команды бота установлены")


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
    """Импортирует и регистрирует все роутеры проекта, избегая дубликатов."""
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

    registered_routers = set()
    registered_routers_count = 0

    for path in module_paths:
        module = _import_optional(path)
        if module:
            routers = _collect_routers_from_module(module)
            if routers:
                for router in routers:
                    if id(router) not in registered_routers:
                        dp.include_router(router)
                        registered_routers.add(id(router))
                        registered_routers_count += 1
                        logger.debug(f"Роутер '{router.name or 'unknown'}' из '{path}' зарегистрирован")

    logger.info("✅ Зарегистрировано роутеров: %s", registered_routers_count)


async def setup_scheduler(container: Container) -> None:
    """Подключает плановые задачи."""
    mod = _import_optional("bot.jobs.scheduled_tasks")
    if not mod:
        logger.info("ℹ️ Модуль планировщика не найден — пропускаю")
        return
    setup = getattr(mod, "setup_scheduler", None)
    if callable(setup):
        res = setup(container)
        if inspect.isawaitable(res):
            await res
        logger.info("✅ Периодические задачи настроены")


def _bind_signals(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    """Назначает обработчик на сигналы SIGINT и SIGTERM."""
    def _handler(*_: object) -> None:
        if not stop.is_set():
            logger.warning("⚠️ Получен сигнал остановки — завершаем polling...")
            stop.set()
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, _handler)
        except NotImplementedError:
            pass


async def init_resources(container: Container) -> None:
    """
    Инициализирует ресурсы приложения.
    Resource провайдеры dependency-injector автоматически инициализируются
    при первом обращении, поэтому просто получаем объекты.
    
    Args:
        container: Контейнер зависимостей
    """
    logger.info("🔧 Инициализация ресурсов...")
    
    try:
        # Получаем Redis client - это инициализирует Resource
        redis = container.redis_client()
        logger.info("✅ Redis client инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Redis: {e}")
        raise

    try:
        # Получаем HTTP client - это инициализирует Resource
        http_client = container.http_client()
        logger.info("✅ HTTP client инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации HTTP client: {e}")
        raise

    logger.info("✅ Все ресурсы успешно инициализированы")


async def shutdown_resources(container: Container) -> None:
    """
    Корректно завершает работу всех ресурсов.
    Resource провайдеры dependency-injector автоматически вызывают
    shutdown при вызове container.shutdown_resources().
    
    Args:
        container: Контейнер зависимостей
    """
    logger.info("🛑 Завершение работы ресурсов...")
    
    try:
        # dependency-injector автоматически закроет все Resource провайдеры
        await container.shutdown_resources()
        logger.info("✅ Все ресурсы успешно завершены")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при завершении ресурсов: {e}")


async def main() -> None:
    """Основная асинхронная функция запуска бота."""
    setup_logging(level=settings.log_level, format="text")
    logger.info("🚀 Запуск CryptoBot...")

    # Инициализация контейнера зависимостей
    container = Container()
    
    # Получение основных компонентов
    bot = container.bot()
    dp = Dispatcher()
    
    # Регистрация middleware
    logger.info("📦 Регистрация middleware...")
    dp.update.outer_middleware(dependencies_middleware)
    dp.update.outer_middleware(ActivityMiddleware())
    dp.update.outer_middleware(ActionTrackingMiddleware(admin_service=container.admin_service()))
    dp.update.outer_middleware(ThrottlingMiddleware())
    logger.info("✅ Middleware зарегистрированы")
    
    # Регистрация роутеров
    logger.info("📦 Регистрация роутеров...")
    register_routers(dp)
    
    # Настройка команд и ресурсов
    await setup_commands(bot)
    
    # ✅ ИСПРАВЛЕНО: Правильная инициализация Resource провайдеров
    await init_resources(container)
    
    await setup_scheduler(container)

    logger.info("✅ Бот полностью настроен, запуск polling...")
    stop_event = asyncio.Event()
    _bind_signals(asyncio.get_running_loop(), stop_event)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("🎉 Бот успешно запущен и работает!")
        await dp.start_polling(
            bot, 
            allowed_updates=dp.resolve_used_update_types(), 
            stop_event=stop_event
        )
    except Exception as e:
        logger.error(f"❌ Критическая ошибка во время работы бота: {e}", exc_info=True)
        raise
    finally:
        logger.info("🛑 Завершение работы бота...")
        
        # ✅ ИСПРАВЛЕНО: Используем встроенный shutdown
        await shutdown_resources(container)
        
        await bot.session.close()
        logger.info("✅ Бот полностью остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Выход из программы")
    except Exception as e:
        logger.critical(f"💥 Фатальная ошибка: {e}", exc_info=True)