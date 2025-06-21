import logging
from apscheduler import current_scheduler
from aiogram import Bot
from bot.config.settings import settings
from bot.services.news_service import NewsService
from bot.services.asic_service import AsicService

logger = logging.getLogger(__name__)

# Задачи больше не принимают аргументов!
async def send_news_job():
    # Мы получаем доступ к зависимостям через current_scheduler
    context = current_scheduler.context
    bot: Bot = context['bot']
    news_service: NewsService = context['news_service']
    
    if not settings.news_chat_id:
        return
    logger.info("Executing scheduled news job...")
    try:
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
    # Точно так же получаем доступ к зависимостям здесь
    context = current_scheduler.context
    asic_service: AsicService = context['asic_service']
    
    logger.info("Executing scheduled ASIC cache update job...")
    try:
        await asic_service.get_profitable_asics()
    except Exception as e:
        logger.error("Error in update_asics_cache_job", extra={'error': str(e)})