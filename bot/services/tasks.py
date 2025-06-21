import logging
from bot.utils import dependencies
from bot.config.settings import settings

logger = logging.getLogger(__name__)

# Задачи теперь не принимают никаких аргументов.
# Они сами знают, где взять все необходимое.

async def send_news_job():
    """Задача для отправки новостей."""
    logger.info("Executing scheduled news job...")
    try:
        # Получаем зависимости из общего модуля
        bot = dependencies.bot
        news_service = dependencies.news_service

        if not bot or not news_service:
            logger.warning("send_news_job skipped: dependencies not initialized.")
            return

        if not settings.news_chat_id:
            return
            
        news = await news_service.fetch_latest_news()
        if not news:
            return
        text = "📰 <b>Крипто-новости (авто):</b>\n\n" + "\n".join(
            [f"🔹 <a href=\"{n['link']}\">{n['title']}</a>" for n in news]
        )
        await bot.send_message(settings.news_chat_id, text, disable_web_page_preview=True)
        logger.info(f"News sent to chat {settings.news_chat_id}.")
    except Exception as e:
        logger.error("Error in send_news_job", extra={'error': str(e)})


async def update_asics_cache_job():
    """Задача для обновления кэша ASIC."""
    logger.info("Executing scheduled ASIC cache update job...")
    try:
        # Получаем зависимость из общего модуля
        asic_service = dependencies.asic_service
        if not asic_service:
            logger.warning("update_asics_cache_job skipped: asic_service not initialized.")
            return

        await asic_service.get_profitable_asics()
    except Exception as e:
        logger.error("Error in update_asics_cache_job", extra={'error': str(e)})