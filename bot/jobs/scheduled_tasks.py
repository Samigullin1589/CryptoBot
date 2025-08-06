# bot/jobs/scheduled_tasks.py
# =================================================================================
# Файл: bot/jobs/scheduled_tasks.py (ПРОДАКШН-ВЕРСИЯ 2025 - ПОЛНАЯ)
# Описание: Содержит логику фоновых задач и их регистрацию в планировщике.
# ИСПРАВЛЕНИЕ: Добавлена недостающая функция setup_jobs.
# =================================================================================

import logging
from typing import TYPE_CHECKING
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Используем TYPE_CHECKING для подсказок типов, избегая циклических импортов
if TYPE_CHECKING:
    from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)


# --- Логика отдельных задач ---

async def update_asics_db_job(deps: "Dependencies"):
    """Задача для принудительного обновления базы данных ASIC-майнеров."""
    logger.info("Running scheduled job: 'update_asics_db_job'...")
    try:
        updated_count = await deps.asic_service.update_asic_list_from_sources()
        logger.info(f"Scheduled ASIC DB update job completed. Updated/added {updated_count} ASICs.")
    except Exception as e:
        logger.error(f"Error in scheduled job 'update_asics_db_job': {e}", exc_info=True)


async def send_news_job(deps: "Dependencies"):
    """Задача для отправки подборки новостей в указанный канал."""
    logger.info("Running scheduled job: 'send_news_job'...")
    try:
        news_service = deps.news_service
        bot = deps.bot
        news_chat_id = deps.settings.NEWS_CHAT_ID
        
        if not news_chat_id:
            logger.warning("NEWS_CHAT_ID not set, skipping job.")
            return

        await news_service.send_news_digest(bot, news_chat_id)
        logger.info(f"Scheduled news digest sent to chat {news_chat_id}.")
    except Exception as e:
        logger.error(f"Error in scheduled job 'send_news_job': {e}", exc_info=True)


async def send_morning_summary_job(deps: "Dependencies"):
    """Задача для отправки утренней сводки администратору."""
    logger.info("Running scheduled job: 'send_morning_summary_job'...")
    try:
        admin_service = deps.admin_service
        bot = deps.bot
        admin_chat_id = deps.settings.ADMIN_CHAT_ID

        if not admin_chat_id:
            logger.warning("ADMIN_CHAT_ID not set, skipping job.")
            return

        stats_text, _ = await admin_service.get_stats_page_content("main")
        header = "Доброе утро! ☀️ Вот краткая сводка по боту:\n\n"
        await bot.send_message(admin_chat_id, f"{header}{stats_text}")
        logger.info("Morning summary job completed.")
    except Exception as e:
        logger.error(f"Error in scheduled job 'send_morning_summary_job': {e}", exc_info=True)


async def send_leaderboard_job(deps: "Dependencies"):
    """Задача для отправки таблицы лидеров игровой экономики."""
    logger.info("Running scheduled job: 'send_leaderboard_job'...")
    try:
        game_service = deps.mining_game_service
        bot = deps.bot
        news_chat_id = deps.settings.NEWS_CHAT_ID

        if not news_chat_id:
            logger.warning("NEWS_CHAT_ID not set for leaderboard, skipping job.")
            return

        leaderboard_data = await game_service.get_leaderboard(top_n=10)
        
        if not leaderboard_data:
            logger.info("No data for leaderboard, skipping.")
            return

        leaderboard_rows = [f"🏆 <b>Таблица лидеров недели</b> 🏆\n"]
        for i, (user_id, balance) in enumerate(leaderboard_data.items(), 1):
            user_info = await deps.user_service.get_user_info(user_id)
            username = user_info.get('username') or f"User {user_id}"
            emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else "🔹"
            leaderboard_rows.append(f"{emoji} {i}. @{username} - {balance:,.2f} монет")

        text = "\n".join(leaderboard_rows)
        await bot.send_message(news_chat_id, text)
        logger.info("Leaderboard sent successfully.")
    except Exception as e:
        logger.error(f"Error in scheduled job 'send_leaderboard_job': {e}", exc_info=True)


# --- Функция для настройки и регистрации всех задач ---

def setup_jobs(scheduler: AsyncIOScheduler, deps: "Dependencies"):
    """
    Настраивает и добавляет все периодические задачи в планировщик.
    """
    try:
        # Задача обновления ASIC-ов - каждые 6 часов
        scheduler.add_job(
            update_asics_db_job, 'interval', hours=6,
            id='update_asics_db', replace_existing=True, args=[deps]
        )
        # Задача отправки новостей - каждые 3 часа
        scheduler.add_job(
            send_news_job, 'interval', hours=3,
            id='send_news', replace_existing=True, args=[deps]
        )
        # Задача утренней сводки - каждый день в 9:00 по UTC
        scheduler.add_job(
            send_morning_summary_job, 'cron', hour=9, minute=0,
            id='morning_summary', replace_existing=True, args=[deps]
        )
        # Задача отправки таблицы лидеров - каждый понедельник в 12:00 по UTC
        scheduler.add_job(
            send_leaderboard_job, 'cron', day_of_week='mon', hour=12, minute=0,
            id='weekly_leaderboard', replace_existing=True, args=[deps]
        )
        
        logger.info("Все периодические задачи успешно настроены.")

    except Exception as e:
        logger.error(f"Не удалось настроить периодические задачи: {e}", exc_info=True)

