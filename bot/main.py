import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
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
from bot.handlers import common_handlers, info_handlers

# Настраиваем логирование в самом начале
setup_logging()
logger = logging.getLogger(__name__)

async def main():
    if not settings.bot_token:
        logger.critical("Bot token not found. Please set BOT_TOKEN in your .env file.")
        return

    # Используем MemoryStorage для FSM. Для Render это оптимальный вариант.
    storage = MemoryStorage()
    
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=storage)
    
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    # Создаем экземпляры сервисов
    coin_list_service = CoinListService()
    price_service = PriceService(coin_list_service=coin_list_service)
    asic_service = AsicService()
    news_service = NewsService()
    market_data_service = MarketDataService()
    quiz_service = QuizService(openai_client=openai_client)
    
    # Регистрируем роутеры
    dp.include_router(common_handlers.router)
    dp.include_router(info_handlers.router)
    
    # Данные, которые будут доступны во всех обработчиках
    workflow_data = {
        "asic_service": asic_service,
        "price_service": price_service,
        "news_service": news_service,
        "market_data_service": market_data_service,
        "quiz_service": quiz_service,
    }

    scheduler = setup_scheduler(
        bot=bot, 
        news_service=news_service, 
        asic_service=asic_service
    )
    
    try:
        scheduler.start()
        logger.info("Scheduler started.")
        
        logger.info("Pre-warming caches...")
        # Прогреваем кэш при старте, чтобы первые ответы были быстрыми
        await asyncio.gather(
            asic_service.get_profitable_asics(), 
            coin_list_service.get_coin_list(), 
            return_exceptions=True
        )
        logger.info("Caches are warm.")
        
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Starting bot in polling mode.")
        await dp.start_polling(bot, **workflow_data)
    finally:
        scheduler.shutdown()
        logger.info("Scheduler shut down.")
        await bot.session.close()
        logger.info("Bot session closed.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
