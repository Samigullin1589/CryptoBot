# ===============================================================
# Файл: bot/utils/scheduler.py (ПРОДАКШШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Декларативный реестр фоновых задач.
# ===============================================================

from typing import NamedTuple, Callable, Awaitable, List

from bot.config.settings import AppSettings
from bot.jobs import scheduled_tasks

# --- УЛУЧШЕНИЕ: Добавляем 'Dependencies' для корректной типизации ---
# Используем строку, чтобы избежать циклического импорта
if False:
    from bot.utils.dependencies import Dependencies


class ScheduledJob(NamedTuple):
    """Структура для описания фоновой задачи."""
    func: Callable[["Dependencies"], Awaitable[None]]  # Задача теперь принимает контейнер deps
    trigger: str
    config: dict
    id: str

# --- УЛУЧШЕНИЕ: Реестр теперь является функцией для лучшей инкапсуляции ---
def get_jobs(settings: AppSettings) -> List[ScheduledJob]:
    """Возвращает список всех запланированных задач."""
    
    # ПРИМЕЧАНИЕ: health_check_job больше не нужен, т.к. бот теперь сам
    # уведомляет о сбоях. Если он нужен для внешних систем, можно оставить.
    # Мы его пока уберем для чистоты.

    return [
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
    ]