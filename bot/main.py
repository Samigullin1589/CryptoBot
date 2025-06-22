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
from bot.handlers import common_handlers, info_handlers, mining_handlers
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.services.asic_service import AsicService
from bot.services.coin_list_service import CoinListService
from bot.services.market_data_service import MarketDataService
from bot.services.news_service import NewsService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.services.scheduler import setup_scheduler
from bot.utils import dependencies
from bot.utils.helpers import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


async def on_shutdown(bot: Bot, scheduler: AsyncIOScheduler):
    """
    Выполняет действия при корректном завершении работы бота.
    """
    logger.info("Shutting down bot...")
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler has been shut down.")
    
    await bot.session.close()
    logger.info("Bot session has been closed.")
    logger.info("Graceful shutdown complete.")


async def main():
    """
    Основная функция для инициализации и запуска бота.
    """
    if not settings.bot_token or not settings.redis_url:
        logger.critical("BOT_TOKEN or REDIS_URL not found in environment variables.")
        return

    # Настройка зависимостей
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    storage = RedisStorage(redis=redis_client)
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=storage)
    
    # Регистрация Middlewares
    dp.message.middleware(ThrottlingMiddleware(redis_client=redis_client))
      
    # Инициализация клиентов и сервисов
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
    coin_list_service = CoinListService()
    price_service = PriceService(coin_list_service=coin_list_service)
    asic_service = AsicService()
    news_service = NewsService()
    market_data_service = MarketDataService()
    quiz_service = QuizService(openai_client=openai_client)
      
    # Заполнение глобальных зависимостей для фоновых задач
    dependencies.bot = bot
    dependencies.asic_service = asic_service
    dependencies.news_service = news_service
    dependencies.redis_client = redis_client
      
    # Регистрация роутеров
    dp.include_router(common_handlers.router)
    dp.include_router(info_handlers.router)
    dp.include_router(mining_handlers.router)

    # Словарь с данными для передачи в обработчики и планировщик
    context_data = {
        "asic_service": asic_service,
        "news_service": news_service,
        "price_service": price_service,
        "market_data_service": market_data_service,
        "quiz_service": quiz_service,
        "redis_client": redis_client,
    }

    scheduler = setup_scheduler(context_data)
    workflow_data = {**context_data, "scheduler": scheduler}
    
    # Регистрация хука для корректного завершения (современный способ)
    dp.shutdown.register(on_shutdown, scheduler=scheduler)
      
    try:
        scheduler.start()
        logger.info("Scheduler started.")
        
        # --- Предварительный прогрев кэша (возвращен) ---
        # Запускаем задачи в фоне, не блокируя старт бота, если одна из них "зависнет"
        logger.info("Pre-warming caches in background...")
        asyncio.create_task(
            asyncio.gather(
                asic_service.get_profitable_asics(), 
                coin_list_service.get_coin_list(), 
                return_exceptions=True
            )
        )
        logger.info("Cache pre-warming initiated.")
          
        # Удаляем старые вебхуки перед запуском
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Starting bot in polling mode.")

        # Запускаем опрос Telegram
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