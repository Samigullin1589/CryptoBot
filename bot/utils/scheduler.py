# ===============================================================
# Файл: bot/utils/scheduler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Настраивает и запускает APScheduler с централизованным
# реестром задач для максимальной гибкости и читаемости.
# ===============================================================

import logging
from urllib.parse import urlparse
from typing import NamedTuple, Callable, Awaitable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

from bot.config.settings import settings
from bot.jobs import scheduled_tasks

logger = logging.getLogger(__name__)

class ScheduledJob(NamedTuple):
    """Структура для описания фоновой задачи."""
    func: Callable[[], Awaitable[None]]  # Сама асинхронная функция задачи
    trigger: str                         # Тип триггера ('interval', 'cron')
    config: dict                         # Конфигурация для триггера
    id: str                              # Уникальный ID задачи

# --- ЦЕНТРАЛЬНЫЙ РЕЕСТР ЗАДАЧ ---
# Для добавления новой задачи, просто добавьте ее в этот список.
JOBS = [
    ScheduledJob(
        func=scheduled_tasks.update_asics_db_job,
        trigger='interval',
        config={'hours': settings.scheduler.asic_update_hours},
        id='asic_db_update_job'
    ),
    ScheduledJob(
        func=scheduled_tasks.send_news_job,
        trigger='interval',
        config={'hours': settings.scheduler.news_interval_hours},
        id='news_sending_job'
    ),
    ScheduledJob(
        func=scheduled_tasks.send_morning_summary_job,
        trigger='cron',
        config={
            'hour': settings.scheduler.morning_summary_hour,
            'minute': 0
        },
        id='morning_summary_job'
    ),
    ScheduledJob(
        func=scheduled_tasks.send_leaderboard_job,
        trigger='cron',
        config={
            'day_of_week': settings.scheduler.leaderboard_day,
            'hour': settings.scheduler.leaderboard_hour,
            'minute': 0
        },
        id='leaderboard_job'
    ),
    ScheduledJob(
        func=scheduled_tasks.health_check_job,
        trigger='interval',
        config={'minutes': 5},
        id='health_check_job'
    ),
]

def setup_scheduler() -> AsyncIOScheduler:
    """
    Настраивает и возвращает экземпляр планировщика APScheduler.
    Автоматически регистрирует все задачи из реестра JOBS.
    """
    parsed_url = urlparse(settings.database.redis_url)
    
    jobstores = {
        'default': RedisJobStore(
            host=parsed_url.hostname,
            port=parsed_url.port,
            password=parsed_url.password,
            db=0  # Используем отдельную БД Redis для задач
        )
    }
    
    scheduler = AsyncIOScheduler(
        jobstores=jobstores, 
        timezone="UTC",
        job_defaults={'misfire_grace_time': 300}, # 5 минут на выполнение "пропущенной" задачи
    )

    # Динамически добавляем все задачи из реестра
    for job in JOBS:
        # Пропускаем задачу с новостями, если чат не указан
        if job.id == 'news_sending_job' and not settings.app.news_chat_id:
            logger.warning("NEWS_CHAT_ID не установлен, задача 'news_sending_job' пропущена.")
            continue
            
        scheduler.add_job(
            job.func, 
            trigger=job.trigger,
            id=job.id,
            replace_existing=True,
            **job.config
        )
        logger.info(f"Задача '{job.id}' успешно добавлена в планировщик (триггер: {job.trigger}, конфиг: {job.config})")

    logger.info("Планировщик настроен со всеми задачами.")
    return scheduler

