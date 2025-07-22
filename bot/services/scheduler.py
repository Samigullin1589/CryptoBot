import logging
from urllib.parse import urlparse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

from bot.config.settings import settings
# --- ИЗМЕНЕНИЕ: Импортируем сам модуль с задачами ---
from bot.services import tasks

logger = logging.getLogger(__name__)

def setup_scheduler(context: dict) -> AsyncIOScheduler:
    """
    Настраивает и возвращает экземпляр планировщика APScheduler.
    Теперь он передает весь контекст (сервисы, бот) напрямую в каждую задачу.
    """
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
        timezone="Asia/Tbilisi",
        job_defaults={'misfire_grace_time': 300},
    )

    # --- ИЗМЕНЕНИЕ: Задачи добавляются с передачей контекста через kwargs ---
    job_kwargs = {'kwargs': {'context': context}}

    if settings.news_chat_id:
        scheduler.add_job(
            tasks.send_news_job, 'interval', 
            hours=settings.news_interval_hours, id='news_sending_job', 
            replace_existing=True, **job_kwargs
        )
    
    scheduler.add_job(
        tasks.update_asics_cache_job, 'interval', 
        hours=settings.asic_cache_update_hours, id='asic_cache_update_job', 
        replace_existing=True, **job_kwargs
    )
    
    scheduler.add_job(
        tasks.send_morning_summary_job, 'cron', 
        hour=9, minute=0, id='morning_summary_job', 
        replace_existing=True, **job_kwargs
    )

    scheduler.add_job(
        tasks.send_leaderboard_job, 'cron', 
        day_of_week='fri', hour=18, minute=0, id='leaderboard_job', 
        replace_existing=True, **job_kwargs
    )
    
    scheduler.add_job(
        tasks.health_check_job, 'interval', 
        minutes=5, id='health_check_job', 
        replace_existing=True, **job_kwargs
    )
    
    logger.info("Scheduler configured with all jobs, including health check.")
    return scheduler
