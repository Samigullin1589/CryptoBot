# ===============================================================
# Файл: bot/main.py (ПРОДАКШН-ВЕРСИЯ 2025 v2)
# Описание: Главный файл для запуска бота.
# Инициализирует все компоненты и запускает long polling.
# ===============================================================

import asyncio
import logging

from bot.config.settings import settings
from bot.utils.logging_setup import setup_logging
from bot.utils.scheduler import setup_scheduler
from bot.utils import dependencies

# Импортируем роутеры из всех модулей
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
    moderation_handler,
    stats_handler,
)
from bot.handlers.game import mining_game_handler
from bot.handlers.tools import calculator_handler
from bot.handlers.threats import threat_handler

# Импортируем middlewares
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.middlewares.action_tracking_middleware import ActionTrackingMiddleware

# --- Главная асинхронная функция ---

async def main():
    """Основная функция для настройки и запуска бота."""
    
    # Шаг 1: Инициализируем все зависимости (Bot, Dispatcher, сервисы)
    # Это должно быть первым действием в main.
    await dependencies.initialize_dependencies()

    # Шаг 2: Получаем готовые экземпляры из модуля dependencies
    dp = dependencies.dp
    bot = dependencies.bot
    user_service = dependencies.user_service
    admin_service = dependencies.admin_service
    scheduler = dependencies.scheduler
    
    # Шаг 3: Настраиваем middlewares
    # Порядок важен: сначала троттлинг, потом отслеживание
    dp.message.middleware(ThrottlingMiddleware())
    dp.update.middleware(ActivityMiddleware())
    dp.update.middleware(ActionTrackingMiddleware(admin_service=admin_service))

    # Шаг 4: Регистрируем роутеры
    # Порядок важен: сначала более специфичные, потом общие.
    
    # Админские хэндлеры
    dp.include_router(admin_menu.admin_router)
    dp.include_router(stats_handler.stats_router)
    dp.include_router(moderation_handler.moderation_router)
    
    # Хэндлеры инструментов
    dp.include_router(calculator_handler.calculator_router)

    # Хэндлеры игры
    dp.include_router(mining_game_handler.game_router)

    # Публичные хэндлеры
    dp.include_router(common_handler.common_router)
    dp.include_router(asic_handler.asic_router)
    dp.include_router(price_handler.price_router)
    dp.include_router(market_data_handler.market_data_router)
    dp.include_router(news_handler.news_router)
    dp.include_router(quiz_handler.quiz_router)
    dp.include_router(crypto_center_handler.crypto_center_router)
    
    # Хэндлер угроз (должен быть последним, чтобы ловить все остальное)
    dp.include_router(threat_handler.threat_router)

    # Шаг 5: Настраиваем и запускаем планировщик
    setup_scheduler(scheduler)
    scheduler.start()
    logging.info("Scheduler started.")

    try:
        # Шаг 6: Запускаем long polling
        logging.info("Bot started polling...")
        await dp.start_polling(bot, **dependencies.workflow_data)
    finally:
        # Шаг 7: Корректно завершаем работу
        logging.info("Bot is shutting down.")
        scheduler.shutdown()
        await dependencies.close_dependencies()
        logging.info("All resources closed. Goodbye!")

# --- Точка входа ---

if __name__ == "__main__":
    # Настраиваем логирование перед запуском
    setup_logging(level=settings.app.log_level, format=settings.app.log_format)
    logging.info("Starting bot...")
    
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped by user.")
    except Exception as e:
        logging.critical("Bot stopped due to a critical error.", exc_info=True)
