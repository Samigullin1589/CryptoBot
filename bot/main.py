# =============================================================================
# File: bot/main.py
# Purpose: Entry point — aiogram v3 launcher with middlewares & graceful shutdown
# =============================================================================

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
import pkgutil
from typing import Callable, Optional

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config.settings import settings
from bot.utils.dependencies import Deps

# Middlewares (под твой проект — уже есть в репо)
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.middlewares.security_middleware import SecurityMiddleware


# ----------------------------- utils -----------------------------------------

def _setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level)
    logging.getLogger("aiogram").setLevel(level)
    logging.info("Логирование инициализировано. Уровень: %s", settings.log_level.upper())


def _register_middlewares(dp: Dispatcher, deps: Deps) -> None:
    """
    Единая точка регистрации middleware:
      - ActivityMiddleware: трекаем активность пользователя/чата
      - ThrottlingMiddleware: защита от флуд-спама
      - SecurityMiddleware: антиспам/модерация контента
    """
    activity = ActivityMiddleware(deps)
    throttle = ThrottlingMiddleware(deps)
    security = SecurityMiddleware(deps)

    # Сообщения
    dp.message.middleware(activity)
    dp.message.middleware(throttle)
    dp.message.middleware(security)

    # Колбэки
    dp.callback_query.middleware(activity)
    dp.callback_query.middleware(throttle)
    dp.callback_query.middleware(security)

    logging.info("Middleware зарегистрированы: activity, throttling, security.")


def _discover_and_include_routers(dp: Dispatcher) -> int:
    """
    Рекурсивно импортирует все модули из bot.handlers.*
    и включает любые найденные объекты aiogram.Router.
    """
    base_pkg = "bot.handlers"
    try:
        pkg = importlib.import_module(base_pkg)
    except Exception as e:
        logging.error("Не удалось импортировать пакет %s: %s", base_pkg, e, exc_info=True)
        return 0

    found = 0
    for mod_info in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        try:
            mod = importlib.import_module(mod_info.name)
        except Exception as e:
            logging.error("Ошибка импорта модуля %s: %s", mod_info.name, e, exc_info=True)
            continue

        for attr_name, attr_val in vars(mod).items():
            if isinstance(attr_val, Router):
                dp.include_router(attr_val)
                found += 1

    logging.info("Все роутеры успешно зарегистрированы. Всего: %s", found)
    return found


async def _set_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Справка и команды"),
        BotCommand(command="menu", description="Главное меню"),
    ]
    await bot.set_my_commands(commands)
    logging.info("Команды бота успешно установлены.")


# ----------------------------- lifecycle -------------------------------------

def make_on_startup(bot: Bot, deps: Deps) -> Callable[[], asyncio.Future]:
    async def _on_startup() -> None:
        logging.info("Запуск процедур on_startup...")
        await _set_bot_commands(bot)

        # Планировщик / периодические задачи — опционально, если есть модуль
        try:
            from bot.jobs.scheduled_tasks import register_scheduled_tasks  # type: ignore
            if inspect.iscoroutinefunction(register_scheduled_tasks):
                await register_scheduled_tasks(deps)
            else:
                register_scheduled_tasks(deps)
            logging.info("Все периодические задачи успешно настроены.")
        except Exception as e:
            logging.warning("Планировщик задач не настроен: %s", e)

        logging.info("Процедуры on_startup завершены.")
    return _on_startup


def make_on_shutdown(deps: Deps) -> Callable[[], asyncio.Future]:
    async def _on_shutdown() -> None:
        logging.info("Запуск процедур on_shutdown...")
        try:
            await deps.close()  # корректное закрытие: Redis, HTTP, пулы и т.д.
        except Exception as e:
            logging.warning("Во время deps.close() возникло исключение: %s", e, exc_info=True)
        logging.info("Процедуры on_shutdown завершены.")
    return _on_shutdown


# ----------------------------- main ------------------------------------------

async def main() -> None:
    _setup_logging()

    # Бот и диспетчер
    bot = Bot(
        token=settings.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # DI контейнер
    deps: Deps
    if hasattr(Deps, "create") and inspect.iscoroutinefunction(getattr(Deps, "create")):
        deps = await Deps.create(bot=bot, settings=settings)  # наш recommended путь
    elif hasattr(Deps, "build") and inspect.iscoroutinefunction(getattr(Deps, "build")):
        deps = await Deps.build(bot=bot, settings=settings)
    else:
        # синхронный конструктор
        deps = Deps(bot=bot, settings=settings)

    # Middleware + Routers
    _register_middlewares(dp, deps)
    _discover_and_include_routers(dp)

    # Lifecycle hooks
    dp.startup.register(make_on_startup(bot, deps))
    dp.shutdown.register(make_on_shutdown(deps))

    logging.info("Запуск бота...")
    try:
        await dp.start_polling(
            bot,
            deps=deps,  # прокидываем deps в хендлеры (aiogram 3 — kwargs)
            allowed_updates=dp.resolve_used_update_types(),
        )
    except (KeyboardInterrupt, SystemExit):
        logging.info("Остановка по сигналу.")
    finally:
        # страхуемся: если shutdown-хук не отработал — всё равно закрываем
        try:
            await deps.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())