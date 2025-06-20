# bot.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from openai import AsyncOpenAI

from config import config
from utils.helpers import setup_logging
from services.api_client import ApiClient
from services.scheduler import setup_scheduler
from handlers import common_handlers, info_handlers

# Настройка логирования в JSON-формате
setup_logging()
logger = logging.getLogger(__name__)

async def main():
    """Основная функция для запуска бота и всех его компонентов."""
    if not config.BOT_TOKEN:
        logger.critical("Bot token not found. Please set BOT_TOKEN in your .env file.")
        return

    # Инициализация основных компонентов
    bot = Bot(token=config.BOT_TOKEN, parse_mode='HTML')
    dp = Dispatcher()
    
    # Инициализация клиента OpenAI, если ключ предоставлен
    openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None
    api_client = ApiClient(openai_client)
    
    # Регистрация роутеров
    dp.include_router(common_handlers.router)
    dp.include_router(info_handlers.router)
    
    # Передаем api_client во все обработчики через аргументы kwargs
    # Это предпочтительный способ в aiogram 3.x
    workflow_data = {"api_client": api_client}

    # Настройка и запуск планировщика
    scheduler = setup_scheduler(bot, api_client)
    
    try:
        scheduler.start()
        logger.info("Scheduler started.")
        
        logger.info("Pre-warming caches...")
        await asyncio.gather(
            api_client.get_profitable_asics(), 
            api_client.get_coin_list(), 
            return_exceptions=True
        )
        logger.info("Caches are warm.")
        
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Starting bot in polling mode.")
        await dp.start_polling(bot, **workflow_data)
    finally:
        scheduler.shutdown()
        logger.info("Scheduler shut down.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")