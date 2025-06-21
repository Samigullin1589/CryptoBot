import asyncio
import logging
import redis.asyncio as redis

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from openai import AsyncOpenAI

from bot.config.settings import settings
from bot.utils.helpers import setup_logging
from bot.services.asic_service import AsicService
from bot.services.coin_list_service import CoinListService
from bot.services.price_service import PriceService
from bot.services.news_service import NewsService
from bot.services.market_data_service import MarketDataService
from bot.services.quiz_service import QuizService
from bot.services.scheduler import setup_scheduler
from bot.handlers import common_handlers, info_handlers, mining_handlers
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.utils import dependencies

setup_logging()
logger = logging.getLogger(__name__)

async def main():
    if not settings.bot_token or not settings.redis_url:
        logger.critical("Bot token or Redis URL not found in environment variables.")
        return

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    storage = RedisStorage(redis=redis_client)
      
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=storage)
      
    dp.message.middleware(ThrottlingMiddleware(redis_client=redis_client, default_rate_limit=1.0))
      
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    # Создаем сервисы
    coin_list_service = CoinListService()
    price_service = PriceService(coin_list_service=coin_list_service)
    asic_service = AsicService()
    news_service = NewsService()
    market_data_service = MarketDataService()
    quiz_service = QuizService(openai_client=openai_client)
      
    # --- ИНИЦИАЛИЗАЦИЯ ГЛОБАЛЬНЫХ ЗАВИСИМОСТЕЙ ---
    dependencies.bot = bot
    dependencies.asic_service = asic_service
    dependencies.news_service = news_service
    # ИСПРАВЛЕНИЕ: Добавляем redis_client в глобальные зависимости
    dependencies.redis_client = redis_client
      
    dp.include_router(common_handlers.router)
    dp.include_router(info_handlers.router)
    dp.include_router(mining_handlers.router)

    # Собираем словарь зависимостей для передачи в планировщик и обработчики
    context_data = {
        "asic_service": asic_service,
        "news_service": news_service,
        "price_service": price_service,
        "market_data_service": market_data_service,
        "quiz_service": quiz_service,
        "redis_client": redis_client,
    }

    # Настраиваем планировщик, передавая ему словарь с зависимостями
    scheduler = setup_scheduler(context_data)
      
    # Добавляем планировщик в общий словарь для доступа из хендлеров
    workflow_data = context_data.copy()
    workflow_data["scheduler"] = scheduler
      
    try:
        scheduler.start()
        logger.info("Scheduler started.")
          
        logger.info("Pre-warming caches...")
        await asyncio.gather(
            asic_service.get_profitable_asics(), 
            coin_list_service.get_coin_list(), 
            return_exceptions=True
        )
        logger.info("Caches are warm.")
          
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Starting bot in polling mode.")

        allowed_updates = dp.resolve_used_update_types(skip_events=['poll_answer'])

        await dp.start_polling(bot, **workflow_data, allowed_updates=allowed_updates)
    finally:
        scheduler.shutdown()
        await dp.storage.close()
        await bot.session.close()
        logger.info("Bot stopped.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")