# ===============================================================
# Файл: bot/main.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Главный файл для запуска Telegram-бота.
# Собирает все компоненты (хэндлеры, мидлвари, сервисы)
# и запускает процесс поллинга.
# ===============================================================

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

# --- 1. Настройка и инициализация ---

# Настраиваем логирование
from bot.utils.logging_setup import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

# Инициализируем зависимости (Bot, Redis, HTTP-сессия и все сервисы)
from bot.utils import dependencies
dependencies.initialize()

# --- 2. Импорт и регистрация роутеров ---

# Импортируем все наши роутеры из папки handlers
from bot.handlers.public import (
    common_handler,
    asic_handler,
    crypto_center_handler,
    market_data_handler,
    news_handler,
    price_handler,
    quiz_handler
)
from bot.handlers.admin import (
    admin_menu,
    moderation_handler,
    stats_handler
)
from bot.handlers.game import (
    mining_game_handler
)
from bot.handlers.tools import (
    calculator_handler
)
from bot.handlers.threats import (
    threat_handler
)

# --- 3. Основная функция запуска ---

async def main():
    """
    Основная асинхронная функция, которая настраивает и запускает бота.
    """
    # Получаем уже созданные экземпляры зависимостей
    bot = dependencies.bot
    dp = dependencies.dp
    scheduler = dependencies.scheduler

    # --- Регистрация Middleware ---
    # Порядок регистрации важен!
    from bot.middlewares.activity_middleware import ActivityMiddleware
    from bot.middlewares.throttling_middleware import ThrottlingMiddleware
    from bot.middlewares.action_tracking_middleware import ActionTrackingMiddleware

    # ActionTrackingMiddleware должен идти первым, чтобы отслеживать все действия
    dp.update.outer_middleware(ActionTrackingMiddleware(
        admin_service=dependencies.admin_service
    ))
    # ThrottlingMiddleware для защиты от флуда сообщениями
    dp.message.outer_middleware(ThrottlingMiddleware(
        user_service=dependencies.user_service
    ))
    # ActivityMiddleware для отслеживания активности пользователей
    dp.update.outer_middleware(ActivityMiddleware(
        user_service=dependencies.user_service
    ))

    # --- Регистрация роутеров ---
    # Регистрируем роутеры в определенном порядке.
    # Сначала специфические (админские), затем более общие.
    dp.include_routers(
        # Админские команды
        admin_menu.router,
        stats_handler.router,
        moderation_handler.router,
        
        # Обработка спама и угроз
        threat_handler.router,

        # Инструменты
        calculator_handler.router,

        # Игра
        mining_game_handler.router,

        # Публичные команды
        common_handler.router,
        price_handler.router,
        asic_handler.router,
        crypto_center_handler.router,
        market_data_handler.router,
        news_handler.router,
        quiz_handler.router
    )

    try:
        # Запускаем фоновые задачи
        scheduler.start()
        logger.info("Scheduler has been started.")
        
        # Перед запуском бота удаляем вебхук, если он был установлен
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запускаем поллинг
        logger.info("Bot is starting polling...")
        await dp.start_polling(bot)

    finally:
        # Корректно завершаем работу при остановке
        logger.info("Stopping bot...")
        scheduler.shutdown()
        await dependencies.close_dependencies()
        logger.info("Bot has been stopped.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
