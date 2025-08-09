# ===============================================================
# Файл: bot/utils/scheduler.py (ПРОДАКШШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Декларативный реестр фоновых задач.
# ===============================================================

from typing import NamedTuple, Callable, Awaitable, List

# ИСПРАВЛЕНО: Импортируем Settings для корректной типизации
from bot.config.settings import Settings
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
# ИСПРАВЛЕНО: AppSettings заменен на Settings
def get_jobs(settings: Settings) -> List[ScheduledJob]:
    """Возвращает список всех запланированных задач."""
    
    return [
        ScheduledJob(
            func=scheduled_tasks.update_asics_db_job,
            trigger='interval',
            config={'hours': settings.asic_service.update_interval_hours},
            id='asic_db_update_job'
        ),
        ScheduledJob(
            func=scheduled_tasks.send_news_job,
            trigger='interval',
            config={'hours': 3}, # Пример: раз в 3 часа
            id='news_sending_job'
        ),
        ScheduledJob(
            func=scheduled_tasks.send_morning_summary_job,
            trigger='cron',
            config={
                'hour': 9, # Пример: в 9 утра
                'minute': 0
            },
            id='morning_summary_job'
        ),
        ScheduledJob(
            func=scheduled_tasks.send_leaderboard_job,
            trigger='cron',
            config={
                'day_of_week': 'mon', # Пример: каждый понедельник
                'hour': 12,
                'minute': 0
            },
            id='leaderboard_job'
        ),
    ]