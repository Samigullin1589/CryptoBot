# ===============================================================
# Файл: main.py (Чистая версия)
# Описание: Полный код для запуска бота. Диагностический блок убран.
# ===============================================================
import asyncio
import logging

import aiohttp
import redis.asyncio as redis
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import AsyncOpenAI

from bot.config.settings import settings
from bot.filters.admin_filter import IsAdminFilter
from bot.filters.spam_filter_alpha import AlphaSpamFilter
from bot.middlewares.activity import ActivityMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.handlers.admin import admin_menu, stats_handlers, data_management_handlers, spam_handler
from bot.handlers import (
    common_handlers, info_handlers, mining_handlers, 
    asic_info_handlers, crypto_center_handlers
)
from bot.services.user_service import UserService
from bot.services.ai_service import AIService
from bot.services.ai_consultant_service import AIConsultantService
from bot.services.asic_service import AsicService
from bot.services.coin_list_service import CoinListService
from bot.services.market_data_service import MarketDataService
from bot.services.news_service import NewsService
from bot.services.price_service import PriceService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.admin_service import AdminService
from bot.services.mining_service import MiningService
from bot.services.quiz_service import QuizService
from bot.services.scheduler import setup_scheduler
from bot.utils.helpers import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

async def delete_spam_message(message: Message):
    try:
        await message.delete()
        logger.warning(f"Удалено спам-сообщение от пользователя {message.from_user.id} в чате {message.chat.id}")
    except Exception as e:
        logger.error(f"Не удалось удалить спам-сообщение {message.message_id}: {e}")

async def on_startup(bot: Bot, scheduler: AsyncIOScheduler):
    logger.info("Bot is starting up...")
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler has been started.")
    logger.info("Bot startup complete.")

async def on_shutdown(
    bot: Bot, 
    scheduler: AsyncIOScheduler, 
    redis_client: redis.Redis, 
    http_session: aiohttp.ClientSession
):
    logger.info("Bot is shutting down...")
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler has been shut down.")
    await redis_client.close()
    logger.info("Redis connection has been closed.")
    await http_session.close()
    logger.info("Aiohttp session has been closed.")
    await bot.session.close()
    logger.info("Bot session has been closed.")
    logger.info("Graceful shutdown complete.")


async def main():
    """Основная асинхронная функция для настройки и запуска бота."""
    if not all([settings.bot_token, settings.redis_url, settings.gemini_api_key]):
        logger.critical("One or more critical environment variables are missing (BOT_TOKEN, REDIS_URL, GEMINI_API_KEY).")
        return

    http_session = aiohttp.ClientSession()
    redis_client = redis.from_url(settings.redis_url, decode_responses=False)
    
    storage = RedisStorage(redis=redis_client)
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=storage)

    user_service = UserService(redis_client=redis_client, bot=bot, admin_user_ids=settings.ADMIN_USER_IDS)
    ai_service = AIService(redis_client=redis_client, gemini_api_key=settings.gemini_api_key)
    ai_consultant_service = AIConsultantService(gemini_api_key=settings.gemini_api_key, http_session=http_session)
    asic_service = AsicService(redis_client=redis_client, http_session=http_session)
    coin_list_service = CoinListService()
    price_service = PriceService(coin_list_service=coin_list_service, redis_client=redis_client, http_session=http_session)
    news_service = NewsService()
    market_data_service = MarketDataService(http_session=http_session)
    crypto_center_service = CryptoCenterService(redis_client=redis_client)
    admin_service = AdminService(redis_client=redis_client)
    
    mining_service = MiningService(market_data_service=market_data_service)
    
    openai_client = None
    if settings.openai_api_key:
        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        logger.info("OpenAI client initialized.")
    else:
        logger.warning("OPENAI_API_KEY not found. Quiz generation will fallback to Gemini.")

    quiz_service = QuizService(ai_service=ai_service, openai_client=openai_client)

    dp.update.middleware(ActivityMiddleware(user_service=user_service))
    dp.message.middleware(ThrottlingMiddleware(redis_client=redis_client, user_service=user_service))

    alpha_spam_filter = AlphaSpamFilter(user_service=user_service, ai_service=ai_service)
    dp.message.register(delete_spam_message, F.chat.type.in_({'group', 'supergroup'}), alpha_spam_filter)

    dp.include_router(admin_menu.admin_router)
    dp.include_router(stats_handlers.stats_router)
    dp.include_router(data_management_handlers.router)
    dp.include_router(spam_handler.admin_spam_router)
    dp.include_router(crypto_center_handlers.router)
    dp.include_router(asic_info_handlers.router) 
    dp.include_router(common_handlers.router)
    dp.include_router(info_handlers.router)
    dp.include_router(mining_handlers.router)

    workflow_data = {
        "user_service": user_service,
        "ai_service": ai_service,
        "ai_consultant_service": ai_consultant_service,
        "asic_service": asic_service,
        "news_service": news_service,
        "price_service": price_service,
        "market_data_service": market_data_service,
        "crypto_center_service": crypto_center_service,
        "admin_service": admin_service,
        "redis_client": redis_client,
        "http_session": http_session,
        "mining_service": mining_service,
        "quiz_service": quiz_service,
        "coin_list_service": coin_list_service
    }
    
    scheduler = setup_scheduler()
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Starting bot in polling mode...")
        await dp.start_polling(bot, scheduler=scheduler, **workflow_data)
    except Exception as e:
        logger.error(f"An unexpected error occurred during polling: {e}", exc_info=True)
    finally:
        logger.info("Polling finished.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution stopped by user or system signal.")
