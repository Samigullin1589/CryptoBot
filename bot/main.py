import asyncio
import logging
from typing import Any

import redis.asyncio as redis
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import AsyncOpenAI

from bot.config.settings import settings
from bot.handlers.admin import admin_menu, stats_handlers
# 👇 ДОБАВЛЯЕМ НОВЫЙ ИМПОРТ
from bot.handlers import (common_handlers, info_handlers, 
                          mining_handlers, asic_info_handlers)
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.services.asic_service import AsicService
from bot.services.coin_list_service import CoinListService
from bot.services.market_data_service import MarketDataService
from bot.services.news_service import NewsService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.services.admin_service import AdminService
from bot.services.scheduler import setup_scheduler
from bot.utils import dependencies
from bot.utils.helpers import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


async def on_shutdown(bot: Bot, scheduler: AsyncIOScheduler):
    logger.info("Shutting down bot...")
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler has been shut down.")
    await bot.session.close()
    logger.info("Bot session has been closed.")
    logger.info("Graceful shutdown complete.")


async def main():
    if not settings.bot_token or not settings.redis_url:
        logger.critical("BOT_TOKEN or REDIS_URL not found in environment variables.")
        return

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    storage = RedisStorage(redis=redis_client)
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=storage)

    dp.message.middleware(ThrottlingMiddleware(redis_client=redis_client))

    # Инициализация клиентов и сервисов
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
    coin_list_service = CoinListService()
    price_service = PriceService(coin_list_service=coin_list_service)
    # 👇 ИСПРАВЛЕНО: Передаем redis_client в AsicService
    asic_service = AsicService(redis_client=redis_client)
    news_service = NewsService()
    market_data_service = MarketDataService()
    quiz_service = QuizService(openai_client=openai_client)
    admin_service = AdminService(redis_client=redis_client)

    # Заполнение глобальных зависимостей
    dependencies.bot = bot
    dependencies.redis_client = redis_client
    dependencies.asic_service = asic_service
    dependencies.news_service = news_service
    dependencies.price_service = price_service
    dependencies.market_data_service = market_data_service
    dependencies.admin_service = admin_service
    
    # Регистрация роутеров
    dp.include_router(admin_menu.admin_router)
    dp.include_router(stats_handlers.stats_router)
    dp.include_router(asic_info_handlers.router) # <<< ДОБАВЛЕН НОВЫЙ РОУТЕР
    dp.include_router(common_handlers.router)
    dp.include_router(info_handlers.router)
    dp.include_router(mining_handlers.router)

    context_data = {
        "asic_service": asic_service,
        "news_service": news_service,
        "price_service": price_service,
        "market_data_service": market_data_service,
        "quiz_service": quiz_service,
        "redis_client": redis_client,
        "admin_service": admin_service,
    }

    scheduler = setup_scheduler(context_data)
    workflow_data = {**context_data, "scheduler": scheduler}

    dp.shutdown.register(on_shutdown)

    try:
        scheduler.start()
        logger.info("Scheduler started.")
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Starting bot in polling mode.")
        await dp.start_polling(bot, **workflow_data)
    except Exception as e:
        logger.error(f"An unexpected error occurred during polling: {e}")
    finally:
        logger.info("Polling finished.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution stopped by user or system signal.")