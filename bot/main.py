# ===============================================================
# Файл: bot/main.py (ПРОДАКШН-ВЕРСИЯ 2025 - ОКОНЧАТЕЛЬНАЯ)
# ===============================================================
import asyncio
import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault

from bot.config.settings import settings
from bot.utils.dependencies import deps
from bot.utils.logging_setup import setup_logging

from bot.handlers.public import (
    common_handler, asic_handler, price_handler, market_data_handler,
    news_handler, quiz_handler, crypto_center_handler
)
from bot.handlers.admin import admin_menu, moderation_handler, stats_handler
from bot.handlers.game import mining_game_handler
from bot.handlers.tools import calculator_handler
from bot.handlers.threats import threat_handler

async def notify_admin(bot: Bot, message: str):
    """Отправляет уведомление в чат администратора."""
    try:
        await bot.send_message(settings.admin.admin_chat_id, f"🤖 **Системное уведомление**\n\n{message}", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление администратору: {e}")

async def set_bot_commands(bot: Bot):
    """Устанавливает команды, видимые в меню Telegram."""
    commands = [
        BotCommand(command="start", description="🚀 Перезапустить бота"),
        BotCommand(command="help", description="ℹ️ Помощь по боту"),
        BotCommand(command="price", description="📈 Узнать курс криптовалюты"),
        BotCommand(command="asics", description="⚙️ Калькулятор доходности асиков"),
        BotCommand(command="calc", description="🧮 Калькулятор криптовалют"),
        BotCommand(command="news", description="📰 Последние новости"),
        BotCommand(command="fng", description="😨 Индекс страха и жадности"),
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())
    logging.info("Команды бота успешно установлены.")

async def main():
    """Основная функция для настройки и запуска бота."""
    logging.info("Инициализация зависимостей и планировщика...")
    await deps.initialize()

    dp = deps.dp
    bot = deps.bot
    scheduler = deps.scheduler

    logging.info("Настройка middlewares...")
    dp.message.middleware(deps.throttling_middleware)
    dp.update.middleware(deps.activity_middleware)
    dp.update.middleware(deps.action_tracking_middleware)

    logging.info("Регистрация роутеров...")
    dp.include_router(admin_menu.admin_router)
    dp.include_router(stats_handler.stats_router)
    dp.include_router(moderation_handler.moderation_router)
    dp.include_router(calculator_handler.calculator_router)

    if settings.feature_flags.enable_mining_game:
        dp.include_router(mining_game_handler.game_router)
        logging.info("Игровой модуль 'Mining Game' включен.")
    
    if settings.feature_flags.enable_crypto_center:
        dp.include_router(crypto_center_handler.crypto_center_router)
        logging.info("Модуль 'Crypto Center' включен.")

    dp.include_router(common_handler.common_router)
    dp.include_router(asic_handler.asic_router)
    dp.include_router(price_handler.price_router)
    dp.include_router(market_data_handler.market_data_router)
    dp.include_router(news_handler.news_router)
    dp.include_router(quiz_handler.quiz_router)
    dp.include_router(threat_handler.threat_router)

    scheduler.start()
    logging.info("Scheduler started.")

    await set_bot_commands(bot)

    try:
        await notify_admin(bot, "Бот успешно запущен и готов к работе.")
        logging.info("Bot started polling...")
        await dp.start_polling(bot, **deps.workflow_data)
    finally:
        logging.info("Bot is shutting down.")
        await deps.close()
        await notify_admin(bot, "Бот остановлен. Все ресурсы освобождены.")
        logging.info("All resources closed. Goodbye!")

if __name__ == "__main__":
    setup_logging(level=settings.app.log_level, format=settings.app.log_format)
    logging.info("Starting bot...")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped by user.")
    except Exception as e:
        logging.critical("Bot stopped due to a critical error.", exc_info=True)
        temp_bot = Bot(token=settings.api_keys.bot_token)
        asyncio.run(notify_admin(temp_bot, f"🔴 **КРИТИЧЕСКАЯ ОШИБКА** 🔴\n\nБот остановлен из-за исключения:\n`{e}`"))
        asyncio.run(temp_bot.session.close())