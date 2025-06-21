import logging
from urllib.parse import urlparse
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

from bot.config.settings import settings
from bot.services.news_service import NewsService
from bot.services.asic_service import AsicService

logger = logging.getLogger(__name__)

# Теперь мы не определяем задачи как глобальные функции.
# Вместо этого мы создадим их внутри setup_scheduler.

def setup_scheduler(bot: Bot, news_service: NewsService, asic_service: AsicService) -> AsyncIOScheduler:
    # Разбираем URL Redis на компоненты
    parsed_url = urlparse(settings.redis_url)

    # Создаем хранилище задач в Redis для отказоустойчивости
    jobstores = {
        'default': RedisJobStore(
            host=parsed_url.hostname,
            port=parsed_url.port,
            password=parsed_url.password,
            db=0 
        )
    }
    
    scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")

    # --- ОПРЕДЕЛЯЕМ ЗАДАЧИ КАК ВНУТРЕННИЕ ФУНКЦИИ ---
    # Они "видят" bot, news_service и asic_service из внешней функции.

    async def send_news_job():
        """Эта задача отправляет новости, используя объекты bot и news_service из замыкания."""
        if not settings.news_chat_id: return
        logger.info("Executing scheduled news job...")
        try:
            news = await news_service.fetch_latest_news()
            if not news: return
            text = "📰 <b>Крипто-новости (авто):</b>\n\n" + "\n".join([f"🔹 <a href=\"{n['link']}\">{n['title']}</a>" for n in news])
            await bot.send_message(settings.news_chat_id, text, disable_web_page_preview=True)
            logger.info(f"News sent to chat {settings.news_chat_id}.")
        except Exception as e:
            logger.error("Error in send_news_job", extra={'error': str(e)})

    async def update_asics_cache_job():
        """Эта задача обновляет кэш ASIC, используя asic_service из замыкания."""
        logger.info("Executing scheduled ASIC cache update job...")
        try:
            await asic_service.get_profitable_asics()
        except Exception as e:
            logger.error("Error in update_asics_cache_job", extra={'error': str(e)})

    # --- ДОБАВЛЯЕМ ЗАДАЧИ В ПЛАНИРОВЩИК БЕЗ АРГУМЕНТОВ ---
    
    if settings.news_chat_id:
        scheduler.add_job(
            send_news_job,  # Передаем внутреннюю функцию
            'interval', 
            hours=settings.news_interval_hours, 
            id='news_sending_job',
            replace_existing=True
            # Аргументы (args) больше не нужны!
        )
    
    scheduler.add_job(
        update_asics_cache_job, # Передаем внутреннюю функцию
        'interval', 
        hours=settings.asic_cache_update_hours, 
        id='asic_cache_update_job',
        replace_existing=True
        # Аргументы (args) больше не нужны!
    )
    
    logger.info("Scheduler configured with RedisJobStore and pickle-safe jobs.")
    return scheduler