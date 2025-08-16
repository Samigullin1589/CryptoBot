# ======================================================================================
# Файл: bot/main.py
# Версия: "Distinguished Engineer" — ПРОДАКШН-СБОРКА (aiogram 3.x)
# Описание:
#   • Полная инициализация бота (настройки, DI, middlewares, routers, команды)
#   • Поддержка плановых задач (jobs/scheduled_tasks)
#   • Корректное завершение (await deps.close()) и обработка сигналов
# ======================================================================================

from __future__ import annotations

import asyncio
import logging
import os
import signal
from importlib import import_module
from typing import Iterable, List, Optional

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config.settings import settings
from bot.utils.dependencies import Deps, dependencies_middleware

# ===== Middlewares (строго из твоего проекта) =====
# Обязательные:
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.middlewares.activity_middleware import ActivityMiddleware

# Опциональные (подключим, если присутствуют в репо):
try:
    from bot.middlewares.security_middleware import SecurityMiddleware  # антиспам/фильтры
except Exception:  # noqa: BLE001
    SecurityMiddleware = None  # type: ignore


logger = logging.getLogger(__name__)


# -------------------------------- Логирование ---------------------------------

def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("aiogram.event").setLevel(logging.INFO)
    logging.getLogger("aiogram.dispatcher").setLevel(logging.INFO)


# ----------------------------- Команды бота -----------------------------------

async def setup_commands(bot: Bot) -> None:
    commands: List[BotCommand] = [
        BotCommand(command="start", description="Запуск"),
        BotCommand(command="help", description="Справка"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="price", description="Котировки"),
        BotCommand(command="market", description="Рынок ASIC"),
        BotCommand(command="mining", description="Виртуальный майнинг"),
        BotCommand(command="news", description="Крипто-новости"),
        BotCommand(command="quiz", description="Квиз"),
    ]
    await bot.set_my_commands(commands)


# ------------------------ Регистрация роутеров --------------------------------

def _collect_routers(module) -> List[Router]:
    """Ищет все объекты Router в модуле (router, *_router и т.п.)."""
    routers: List[Router] = []
    for name, obj in vars(module).items():
        if isinstance(obj, Router):
            routers.append(obj)
    return routers


def _import_optional(module_path: str) -> Optional[object]:
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
    module_paths: List[str] = [
        # базовые
        "bot.handlers.start_handler",
        "bot.handlers.help_handler",
        "bot.handlers.menu_handler",
        "bot.handlers.text_handler",

        # цены/рынок/новости
        "bot.handlers.price_handler",
        "bot.handlers.market_handler",
        "bot.handlers.news_handler",
        "bot.handlers.crypto_center_handler",

        # игра, калькулятор, квиз
        "bot.handlers.game.mining_game_handler",
        "bot.handlers.calculator_handler",
        "bot.handlers.quiz_handler",

        # угрозы/модерация/админка
        "bot.handlers.threats",
        "bot.handlers.admin.admin_handler",
        "bot.handlers.admin.moderation_handler",
        "bot.handlers.admin.stats_handler",

        # онбординг
        "bot.handlers.onboarding_handler",
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
        await setup(deps, dp)  # type: ignore[misc]
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
            # Windows / ограниченные окружения
            pass


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
            deps,
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
        # Закрываем DI/ресурсы
        await deps.close()
        logger.info("Процедуры on_shutdown завершены.")


# --------------------------------- Entrypoint ---------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
    pass