# ===============================================================
# Файл: bot/jobs/scheduled_tasks.py (НОВЫЙ ФАЙЛ)
# Описание: Содержит логику фоновых задач, выполняемых по расписанию.
# Каждая задача самостоятельно инициализирует необходимые зависимости.
# ===============================================================

import logging
from bot.utils import dependencies
from bot.services.admin_service import AdminService
from bot.services.asic_service import AsicService
from bot.services.news_service import NewsService

logger = logging.getLogger(__name__)

async def update_asics_db_job():
    """
    Задача для принудительного обновления базы данных ASIC-майнеров.
    """
    try:
        # Получаем зависимости в момент выполнения задачи
        asic_service = dependencies.get_asic_service()
        await asic_service.update_asics_db()
        logger.info("Scheduled ASIC DB update job completed successfully.")
    except Exception as e:
        logger.error(f"Error in scheduled ASIC DB update job: {e}", exc_info=True)

async def send_news_job():
    """
    Задача для отправки подборки новостей в указанный канал.
    """
    try:
        # Получаем зависимости в момент выполнения задачи
        news_service = dependencies.get_news_service()
        bot = dependencies.get_bot()
        settings = dependencies.get_settings()
        
        if not settings.app.news_chat_id:
            logger.warning("NEWS_CHAT_ID not set, skipping scheduled news job.")
            return

        await news_service.send_news_digest(bot, settings.app.news_chat_id)
        logger.info(f"Scheduled news digest sent to chat {settings.app.news_chat_id}.")
    except Exception as e:
        logger.error(f"Error in scheduled news sending job: {e}", exc_info=True)

# --- ЗАГЛУШКИ ДЛЯ ДРУГИХ ЗАДАЧ ---
# По аналогии вы можете реализовать остальные задачи,
# каждая из которых будет получать свои зависимости в рантайме.

async def send_morning_summary_job():
    """
    Задача для отправки утренней сводки (заглушка).
    """
    # TODO: Реализовать логику утренней сводки, получая нужные сервисы
    logger.info("Executing morning summary job (stub)...")
    admin_service: AdminService = dependencies.get_admin_service()
    bot = dependencies.get_bot()
    settings = dependencies.get_settings()
    
    # Пример: Отправка общей статистики админу
    stats_text = await admin_service.get_stats_page_content("general")
    await bot.send_message(settings.admin.admin_chat_id, f"Доброе утро!☀️\n\n{stats_text}")
    logger.info("Morning summary job completed.")

async def send_leaderboard_job():
    """
    Задача для отправки таблицы лидеров (заглушка).
    """
    # TODO: Реализовать логику таблицы лидеров
    logger.info("Executing leaderboard job (stub)...")

async def health_check_job():
    """
    Задача для проверки работоспособности (заглушка).
    """
    # TODO: Реализовать логику проверки работоспособности
    logger.info("Executing health check job (stub)...")

