# =================================================================================
# Файл: bot/main.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ УСИЛЕННАЯ)
# Описание: Точка входа с улучшенной архитектурой, роутингом и процедурой
#           завершения работы для максимальной стабильности.
# =================================================================================

import asyncio
import logging

import redis.asyncio as redis
from aiohttp import ClientSession
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from bot.config.config import settings
from bot.utils.dependencies import Deps
from bot.utils.logging_setup import setup_logging
from bot.middlewares.activity_middleware import ActivityMiddleware
from bot.middlewares.throttling_middleware import ThrottlingMiddleware
from bot.jobs.scheduled_tasks import setup_jobs

# Импортируем все необходимые пакеты с роутерами
from bot.handlers import admin, game, public, tools, threats

logger = logging.getLogger(__name__)

def register_routers(dp: Dispatcher):
    """
    Централизованно регистрирует все роутеры приложения.
    Такой подход упрощает управление и масштабирование.
    """
    # Админские роутеры
    dp.include_router(admin.admin_menu.admin_router)
    dp.include_router(admin.verification_admin_handler.router)
    dp.include_router(admin.stats_handler.stats_router)
    dp.include_router(admin.moderation_handler.moderation_router)
    dp.include_router(admin.game_admin_handler.router)

    # Публичные роутеры
    dp.include_router(public.common_handler.router)
    dp.include_router(public.menu_handlers.router)
    dp.include_router(public.price_handler.router)
    dp.include_router(public.asic_handler.router)
    dp.include_router(public.news_handler.router)
    dp.include_router(public.quiz_handler.router)
    dp.include_router(public.market_info_handler.router)
    dp.include_router(public.crypto_center_handler.router)
    dp.include_router(public.verification_public_handler.router)
    dp.include_router(public.achievements_handler.router)
    dp.include_router(public.market_handler.router) # Обработчик рынка

    # Игровые роутеры
    dp.include_router(game.mining_game_handler.game_router)

    # Инструменты
    dp.include_router(tools.calculator_handler.calculator_router)

    # Обработка угроз (должен быть в конце, чтобы ловить все, что не поймали другие)
    dp.include_router(threats.threat_handler.threat_router)

    logger.info("Все роутеры успешно зарегистрированы.")

async def set_bot_commands(bot: Bot):
    """Устанавливает команды, видимые пользователям в меню Telegram."""
    commands = [
        BotCommand(command="start", description="🚀 Перезапустить бота"),
        BotCommand(command="help", description="ℹ️ Помощь по боту"),
        BotCommand(command="check", description="✅ Проверить статус пользователя"),
        BotCommand(command="infoverif", description="📄 Узнать о верификации"),
        BotCommand(command="admin", description="🔒 Панель администратора"),
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())
    logger.info("Команды бота успешно установлены.")

async def on_startup(bot: Bot, deps: Deps):
    """Выполняет действия при старте бота."""
    logger.info("Запуск процедур on_startup...")
    await set_bot_commands(bot)
    await deps.coin_list_service.update_coin_list()
    setup_jobs(deps.scheduler, deps)
    deps.scheduler.start()
    logger.info("Планировщик задач запущен.")
    if deps.admin_service:
        await deps.admin_service.notify_admins("✅ Бот успешно запущен!")
    logger.info("Процедуры on_startup завершены.")

async def on_shutdown(bot: Bot, deps: Deps):
    """Выполняет действия при остановке бота, гарантируя чистое закрытие ресурсов."""
    logger.info("Запуск процедур on_shutdown...")
    if deps.admin_service:
        await deps.admin_service.notify_admins("❗️ Бот останавливается!")
    if deps.scheduler and deps.scheduler.running:
        deps.scheduler.shutdown(wait=False)
        logger.info("Планировщик задач остановлен.")
    if deps.redis_pool:
        await deps.redis_pool.close()
        logger.info("Пул соединений Redis закрыт.")
    if bot.session:
        await bot.session.close()
        logger.info("Сессия бота закрыта.")
    logger.info("Процедуры on_shutdown завершены. Бот остановлен.")

async def main():
    """Главная точка входа для приложения бота."""
    setup_logging(level=settings.log_level, format="json") # JSON-логи для продакшена
    
    redis_pool = redis.from_url(str(settings.REDIS_URL), encoding="utf-8", decode_responses=True)
    storage = RedisStorage(redis=redis_pool)

    bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=storage)

    register_routers(dp)

    async with ClientSession() as http_session:
        deps = await Deps.build(
            settings=settings,
            http_session=http_session,
            redis_pool=redis_pool,
            bot=bot
        )

        dp.update.middleware(ThrottlingMiddleware(storage=storage))
        dp.update.middleware(ActivityMiddleware(user_service=deps.user_service))
        logger.info("Все Middleware успешно зарегистрированы.")
        
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        await bot.delete_webhook(drop_pending_updates=True)

        logger.info("Запуск процесса опроса Telegram...")
        # Передаем контейнер зависимостей во все обработчики
        await dp.start_polling(bot, deps=deps)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную (KeyboardInterrupt/SystemExit).")
    except Exception as e:
        logger.critical(f"Критическая ошибка привела к остановке бота: {e}", exc_info=True)