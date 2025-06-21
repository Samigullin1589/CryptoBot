import logging
from urllib.parse import urlparse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

from bot.config.settings import settings

logger = logging.getLogger(__name__)

def setup_scheduler() -> AsyncIOScheduler:
    parsed_url = urlparse(settings.redis_url)
    
    jobstores = {
        'default': RedisJobStore(
            host=parsed_url.hostname,
            port=parsed_url.port,
            password=parsed_url.password,
            db=0
        )
    }
    
    scheduler = AsyncIOScheduler(
        jobstores=jobstores, 
        timezone="UTC",
        job_defaults={'misfire_grace_time': 300}
    )

    if settings.news_chat_id:
        scheduler.add_job(
            'bot.services.tasks:send_news_job',
            'interval',
            hours=settings.news_interval_hours,
            id='news_sending_job',
            replace_existing=True
        )
    
    scheduler.add_job(
        'bot.services.tasks:update_asics_cache_job',
        'interval',
        hours=settings.asic_cache_update_hours,
        id='asic_cache_update_job',
        replace_existing=True
    )
    
    logger.info("Scheduler configured with RedisJobStore and dependency module.")
    return scheduler