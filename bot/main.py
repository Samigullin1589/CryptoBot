# ===============================================================
# Файл: bot/main.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Главный файл для запуска бота. Настраивает
# логирование, инициализирует зависимости, регистрирует
# роутеры и middlewares, запускает бота и планировщик.
# ===============================================================
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

# --- Импорты для настройки ---
from bot.config.settings import settings
from bot.utils import dependencies  # Импортируем модуль, он сам инициализируется
from bot.utils.logging_setup import setup_logging
from bot.utils.scheduler import setup_scheduler

# --- Импорты роутеров ---
from bot.handlers.public import (
    common_handler,
    asic_handler,
    price_handler,
    market_data_handler,
    news_handler,
    quiz_handler,
    crypto_center_handler,
)
from bot.handlers.admin import (
    admin_menu,
    stats_handler,
    moderation_handler,
)
from bot.handlers.game import mining_game_handler
from bot.handlers.tools import calculator_handler
from bot.handlers.threats import threat_handler

# --- Импорты middlewares ---
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.middlewares.action_tracking_middleware import ActionTrackingMiddleware

# Настраиваем логирование в самом начале
setup_logging(level=settings.app.log_level, format=settings.app.log_format)
logger = logging.getLogger(__name__)

async def main():
    """Главная асинхронная функция для запуска бота."""
    logger.info("Starting bot...")

    # --- ИСПРАВЛЕНИЕ: Удаляем ненужный вызов ---
    # Модуль dependencies инициализирует все синглтоны при первом импорте.
    # Ручной вызов не требуется и приводит к ошибке.
    # await dependencies.initialize() # <-- ЭТА СТРОКА УДАЛЕНА
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    # Получаем уже готовые экземпляры из центра зависимостей
    bot: Bot = dependencies.bot
    dp: Dispatcher = dependencies.dp
    scheduler = dependencies.scheduler

    # --- Регистрация middlewares ---
    # Порядок важен: сначала троттлинг, потом остальные.
    dp.message.middleware(ThrottlingMiddleware(
        user_service=dependencies.user_service,
        settings=settings.throttling
    ))
    # ActionTrackingMiddleware должен идти до ActivityMiddleware
    dp.update.middleware(ActionTrackingMiddleware(admin_service=dependencies.admin_service))
    dp.update.middleware(ActivityMiddleware(
        user_service=dependencies.user_service,
        settings=settings.activity
    ))
    logger.info("Middlewares registered.")

    # --- Регистрация роутеров ---
    # Сначала регистрируем обработчики для админов,
    # затем публичные, чтобы избежать неверного порядка срабатывания.
    admin_routers = [
        admin_menu.admin_router,
        stats_handler.stats_router,
        moderation_handler.moderation_router,
    ]
    public_routers = [
        common_handler.router,
        price_handler.router,
        asic_handler.router,
        market_data_handler.router,
        news_handler.router,
        quiz_handler.router,
        crypto_center_handler.router,
        mining_game_handler.router,
        calculator_handler.router,
        threat_handler.router,  # Этот роутер должен быть одним из последних
    ]
    dp.include_routers(*admin_routers, *public_routers)
    logger.info("All routers included.")

    # --- Запуск компонентов ---
    try:
        scheduler.start()
        logger.info("Scheduler started.")
        # Пропускаем накопленные апдейты
        await bot.delete_webhook(drop_pending_updates=True)
        # Запускаем поллинг
        await dp.start_polling(bot)
    finally:
        # Корректно завершаем работу
        scheduler.shutdown()
        await dependencies.close_dependencies()
        logger.info("Bot stopped and resources closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution stopped manually.")
