import logging
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

from bot.config.settings import settings
from bot.services.news_service import NewsService
from bot.services.asic_service import AsicService

logger = logging.getLogger(__name__)

async def send_news_job(bot: Bot, news_service: NewsService):
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

async def update_asics_cache_job(asic_service: AsicService):
    logger.info("Executing scheduled ASIC cache update job...")
    try:
        await asic_service.get_profitable_asics()
    except Exception as e:
        logger.error("Error in update_asics_cache_job", extra={'error': str(e)})

def setup_scheduler(bot: Bot, news_service: NewsService, asic_service: AsicService) -> AsyncIOScheduler:
    # Создаем хранилище задач в Redis для отказоустойчивости
    jobstores = {
        'default': RedisJobStore(url=settings.redis_url)
    }
    
    # Инициализируем планировщик с указанием хранилища
    scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
    
    if settings.news_chat_id:
        scheduler.add_job(
            send_news_job, 
            'interval', 
            hours=settings.news_interval_hours, 
            args=(bot, news_service),
            id='news_sending_job', # Добавляем ID для избежания дублирования
            replace_existing=True
        )
    
    scheduler.add_job(
        update_asics_cache_job, 
        'interval', 
        hours=settings.asic_cache_update_hours, 
        args=(asic_service,),
        id='asic_cache_update_job', # Добавляем ID для избежания дублирования
        replace_existing=True
    )
    
    logger.info("Scheduler configured with RedisJobStore.")
    return scheduler