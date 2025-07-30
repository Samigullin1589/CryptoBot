# ===============================================================
# Файл: bot/main.py (ПРОДАКШН-ВЕРСИЯ 2025 - ГЕНИЙ 2.0)
# Описание: Главный файл для запуска бота. Инициализирует
# все компоненты, регистрирует роутеры с учетом feature flags
# и обеспечивает отказоустойчивость.
# ===============================================================
import asyncio
import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault

from bot.config.settings import settings
from bot.utils.dependencies import deps
from bot.utils.logging_setup import setup_logging

# Импортируем все наши роутеры
from bot.handlers.public import (
    common_handler, asic_handler, price_handler, market_data_handler,
    news_handler, quiz_handler, crypto_center_handler, market_handler,
    achievements_handler
)
from bot.handlers.admin import (
    admin_menu, moderation_handler, stats_handler, game_admin_handler
)
from bot.handlers.game import mining_game_handler
from bot.handlers.tools import calculator_handler
from bot.handlers.threats import threat_handler

async def notify_admin(bot: Bot, message: str):
    """Отправляет системное уведомление администратору."""
    try:
        # Используем MarkdownV2 для большей гибкости
        await bot.send_message(settings.admin.admin_chat_id, f"🤖 *Системное уведомление*\n\n{message}", parse_mode="MarkdownV2")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление администратору: {e}")

async def set_bot_commands(bot: Bot):
    """Устанавливает команды, видимые в меню Telegram."""
    commands = [
        BotCommand(command="start", description="🚀 Перезапустить бота / Главное меню"),
        BotCommand(command="help", description="ℹ️ Помощь по всем функциям"),
        BotCommand(command="market", description="🛒 Рынок оборудования"),
        BotCommand(command="achievements", description="🏆 Мои достижения"),
        BotCommand(command="crypto_center", description="💎 AI-аналитика (Crypto Center)")
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())
    logging.info("Команды бота успешно установлены.")

async def main():
    """Основная функция для настройки и запуска бота."""
    logging.info("Инициализация зависимостей...")
    await deps.initialize()

    dp = deps.dp
    bot = deps.bot
    scheduler = deps.scheduler

    logging.info("Настройка middlewares (Throttling, Activity, Action Tracking)...")
    dp.update.middleware(deps.throttling_middleware)
    dp.update.middleware(deps.activity_middleware)
    dp.update.middleware(deps.action_tracking_middleware)

    logging.info("Регистрация роутеров...")
    # --- Административные роутеры ---
    dp.include_router(admin_menu.admin_router)
    dp.include_router(stats_handler.stats_router)
    dp.include_router(moderation_handler.moderation_router)
    dp.include_router(game_admin_handler.router)

    # --- Инструменты ---
    dp.include_router(calculator_handler.calculator_router)

    # --- Игровые модули (с проверкой флагов) ---
    if settings.feature_flags.enable_mining_game:
        dp.include_router(mining_game_handler.game_router)
        dp.include_router(market_handler.router) # Рынок - часть игры
        dp.include_router(achievements_handler.router) # Достижения - часть игры
        logging.info("Игровые модули (Майнинг, Рынок, Достижения) включены.")
    
    # --- AI-модули (с проверкой флагов) ---
    if settings.feature_flags.enable_crypto_center:
        dp.include_router(crypto_center_handler.router)
        logging.info("Модуль 'Crypto Center' включен.")

    # --- Публичные информационные роутеры ---
    dp.include_router(common_handler.router)
    dp.include_router(asic_handler.router)
    dp.include_router(price_handler.router)
    dp.include_router(market_data_handler.router)
    dp.include_router(news_handler.router)
    dp.include_router(quiz_handler.router)
    
    # --- Роутер угроз (регистрируется последним, чтобы ловить все остальное) ---
    dp.include_router(threat_handler.threat_router)

    scheduler.start()
    logging.info("Планировщик фоновых задач запущен.")

    await set_bot_commands(bot)

    try:
        await notify_admin(bot, "Бот успешно запущен и готов к работе\\.")
        logging.info("Bot started polling...")
        await dp.start_polling(bot, **deps.workflow_data)
    finally:
        logging.info("Bot is shutting down...")
        await notify_admin(bot, "Бот остановлен\\. Все ресурсы освобождены\\.")
        await deps.close()
        logging.info("All resources closed. Goodbye!")

if __name__ == "__main__":
    setup_logging(level=settings.app.log_level, format=settings.app.log_format)
    logging.info("Запуск бота...")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен пользователем.")
    except Exception as e:
        logging.critical(f"Бот остановлен из-за критической ошибки: {e}", exc_info=True)
        # Отправка уведомления о сбое "последней воли"
        temp_bot_token = settings.api_keys.bot_token
        if temp_bot_token:
            temp_bot = Bot(token=temp_bot_token)
            error_message = f"🔴 *КРИТИЧЕСКАЯ ОШИБКА* 🔴\n\nБот остановлен из\\-за исключения:\n`{str(e)}`"
            asyncio.run(notify_admin(temp_bot, error_message))
            asyncio.run(temp_bot.session.close())