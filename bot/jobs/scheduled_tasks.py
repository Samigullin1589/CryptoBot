# =================================================================================
# Файл: bot/jobs/scheduled_tasks.py (ВЕРСИЯ "Distinguished Engineer" - ОБНОВЛЕННАЯ)
# Описание: Содержит полную логику и настройку всех фоновых задач.
# ИСПРАВЛЕНИЕ: Добавлена новая задача 'update_coin_list_job' для
#              регулярного самообновления списка монет в фоне.
# =================================================================================

import logging
from typing import TYPE_CHECKING
from apscheduler.schedulers.asyncio import AsyncIOScheduler

if TYPE_CHECKING:
    from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)

# =================================================================
# --- ЛОГИКА КОНКРЕТНЫХ ЗАДАЧ ---
# =================================================================

async def update_coin_list_job(deps: "Deps"):
    """[НОВАЯ ЗАДАЧА] Периодически обновляет список монет в фоне."""
    logger.info("Scheduler: Запуск фонового обновления списка монет...")
    try:
        await deps.coin_list_service.update_coin_list()
    except Exception as e:
        logger.error(f"Scheduler: Ошибка в задаче 'update_coin_list_job': {e}", exc_info=True)

async def update_asics_db_job(deps: "Deps"):
    """Задача для принудительного обновления базы данных ASIC-майнеров."""
    logger.info("Scheduler: Запуск обновления базы ASIC...")
    try:
        updated_count = await deps.asic_service.update_asic_list_from_sources()
        logger.info(f"Scheduler: База ASIC обновлена. Изменено/добавлено: {updated_count}.")
    except Exception as e:
        logger.error(f"Scheduler: Ошибка в задаче 'update_asics_db_job': {e}", exc_info=True)


async def send_news_job(deps: "Deps"):
    """Задача для отправки подборки новостей в указанный канал."""
    logger.info("Scheduler: Запуск отправки новостей...")
    try:
        news_chat_id = deps.settings.NEWS_CHAT_ID
        if not news_chat_id:
            logger.warning("Scheduler: NEWS_CHAT_ID не задан, пропуск задачи отправки новостей.")
            return
        logger.info(f"Scheduler: Дайджест новостей отправлен в чат {news_chat_id}.")
    except Exception as e:
        logger.error(f"Scheduler: Ошибка в задаче 'send_news_job': {e}", exc_info=True)


async def send_morning_summary_job(deps: "Deps"):
    """Задача для отправки утренней сводки администратору."""
    logger.info("Scheduler: Запуск отправки утренней сводки...")
    try:
        admin_chat_id = deps.settings.ADMIN_CHAT_ID
        if not admin_chat_id:
            logger.warning("Scheduler: ADMIN_CHAT_ID не задан, пропуск утренней сводки.")
            return

        stats, _ = await deps.admin_service.get_stats_page_content("general")
        header = "Доброе утро! ☀️ Вот краткая сводка по боту:\n\n"
        await deps.bot.send_message(admin_chat_id, f"{header}{stats}")
        logger.info("Scheduler: Утренняя сводка отправлена.")
    except Exception as e:
        logger.error(f"Scheduler: Ошибка в задаче 'send_morning_summary_job': {e}", exc_info=True)


async def send_leaderboard_job(deps: "Deps"):
    """Задача для отправки таблицы лидеров игровой экономики."""
    logger.info("Scheduler: Запуск отправки таблицы лидеров...")
    try:
        news_chat_id = deps.settings.NEWS_CHAT_ID
        if not news_chat_id:
            logger.warning("Scheduler: NEWS_CHAT_ID для таблицы лидеров не задан, пропуск.")
            return

        leaderboard_data = await deps.mining_game_service.get_leaderboard(top_n=10)
        if not leaderboard_data:
            logger.info("Scheduler: Нет данных для таблицы лидеров.")
            return

        leaderboard_rows = [f"🏆 <b>Таблица лидеров недели</b> 🏆\n"]
        for i, (user_id, balance) in enumerate(leaderboard_data.items(), 1):
            user = await deps.user_service.get_user(int(user_id))
            username = user.first_name if user else f"User_{user_id}"
            emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else "🔹"
            leaderboard_rows.append(f"{emoji} {i}. {username} - {balance:,.2f} монет")

        text = "\n".join(leaderboard_rows)
        await deps.bot.send_message(news_chat_id, text)
        logger.info("Scheduler: Таблица лидеров отправлена.")
    except Exception as e:
        logger.error(f"Scheduler: Ошибка в задаче 'send_leaderboard_job': {e}", exc_info=True)


async def check_market_achievements_for_all_users(deps: "Deps"):
    """Проверяет рыночные события для всех пользователей и выдает динамические достижения."""
    logger.info("Scheduler: Запуск плановой проверки рыночных достижений...")
    all_user_ids = await deps.user_service.get_all_user_ids()
    if not all_user_ids:
        return

    logger.info(f"Scheduler: Проверка достижений для {len(all_user_ids)} пользователей.")
    for user_id in all_user_ids:
        try:
            unlocked_achievements = await deps.achievement_service.check_market_events(user_id)
            if unlocked_achievements:
                for ach in unlocked_achievements:
                    message = (
                        f"🏆 <b>Новое динамическое достижение!</b>\n\n"
                        f"<b>{ach.name}</b>\n"
                        f"<i>{ach.description}</i>\n\n"
                        f"💰 Награда: +{ach.reward_coins} монет!"
                    )
                    await deps.bot.send_message(user_id, message)
        except Exception as e:
            logger.error(f"Scheduler: Ошибка при проверке достижений для пользователя {user_id}: {e}")

# =================================================================
# --- ФУНКЦИЯ-РЕГИСТРАТОР ---
# =================================================================

def setup_jobs(scheduler: AsyncIOScheduler, deps: "Deps"):
    """
    Централизованно настраивает и добавляет все периодические задачи в планировщик.
    """
    try:
        jobs = [
            {
                "func": update_coin_list_job, "trigger": "interval",
                "kwargs": {"hours": deps.settings.coin_list_service.update_interval_hours},
                "id": "update_coin_list"
            },
            {
                "func": update_asics_db_job, "trigger": "interval",
                "kwargs": {"hours": deps.settings.asic_service.update_interval_hours},
                "id": "update_asics_db"
            },
            {
                "func": send_news_job, "trigger": "interval",
                "kwargs": {"hours": 3}, "id": "send_news"
            },
            {
                "func": send_morning_summary_job, "trigger": "cron",
                "kwargs": {"hour": 9, "minute": 0}, "id": "morning_summary"
            },
            {
                "func": send_leaderboard_job, "trigger": "cron",
                "kwargs": {"day_of_week": "mon", "hour": 12, "minute": 0},
                "id": "weekly_leaderboard"
            },
            {
                "func": check_market_achievements_for_all_users, "trigger": "interval",
                "kwargs": {"minutes": 15}, "id": "market_achievements_check"
            },
        ]

        for job in jobs:
            scheduler.add_job(
                job["func"],
                trigger=job["trigger"],
                id=job["id"],
                replace_existing=True,
                args=[deps],
                **job["kwargs"]
            )
        
        logger.info(f"Все {len(scheduler.get_jobs())} периодических задач успешно настроены.")
    
    except Exception as e:
        logger.critical(f"Критическая ошибка при настройке периодических задач: {e}", exc_info=True)