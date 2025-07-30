# ===============================================================
# Файл: bot/jobs/scheduled_tasks.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Содержит логику фоновых задач. Каждая задача получает
# все необходимые зависимости через единый контейнер 'deps'.
# ===============================================================

import logging
from typing import TYPE_CHECKING

# --- УЛУЧШЕНИЕ: Используем TYPE_CHECKING для подсказок типов, избегая циклических импортов ---
if TYPE_CHECKING:
    from bot.utils.dependencies import Dependencies

logger = logging.getLogger(__name__)


async def update_asics_db_job(deps: "Dependencies"):
    """Задача для принудительного обновления базы данных ASIC-майнеров."""
    logger.info("Running scheduled job: 'update_asics_db_job'...")
    try:
        # --- УЛУCHЕНИЕ: Получаем сервис напрямую из контейнера ---
        updated_count = await deps.asic_service.update_asic_list_from_sources()
        logger.info(f"Scheduled ASIC DB update job completed. Updated/added {updated_count} ASICs.")
    except Exception as e:
        logger.error(f"Error in scheduled job 'update_asics_db_job': {e}", exc_info=True)


async def send_news_job(deps: "Dependencies"):
    """Задача для отправки подборки новостей в указанный канал."""
    logger.info("Running scheduled job: 'send_news_job'...")
    try:
        # --- УЛУCHЕНИЕ: Получаем все зависимости из контейнера ---
        news_service = deps.news_service
        bot = deps.bot
        news_chat_id = deps.settings.admin.news_chat_id
        
        # Проверка перенесена в scheduler.py, но дублирование не повредит
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
        admin_chat_id = deps.settings.admin.admin_chat_id

        stats_text = await admin_service.get_stats_page_content("general")
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
        news_chat_id = deps.settings.admin.news_chat_id # Отправляем в общий чат

        leaderboard_data = await game_service.get_leaderboard(top_n=10)
        
        if not leaderboard_data:
            logger.info("No data for leaderboard, skipping.")
            return

        leaderboard_rows = [f"🏆 <b>Таблица лидеров недели</b> 🏆\n"]
        for i, (user_id, balance) in enumerate(leaderboard_data.items(), 1):
            # Получаем информацию о пользователе
            user_info = await deps.user_service.get_user_info(user_id) # Предполагаем наличие такого метода
            username = user_info.get('username') or f"User {user_id}"
            emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else "🔹"
            leaderboard_rows.append(f"{emoji} {i}. @{username} - {balance:,.2f} монет")

        text = "\n".join(leaderboard_rows)
        await bot.send_message(news_chat_id, text)
        logger.info("Leaderboard sent successfully.")
    except Exception as e:
        logger.error(f"Error in scheduled job 'send_leaderboard_job': {e}", exc_info=True)