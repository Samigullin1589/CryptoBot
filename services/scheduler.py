# services/scheduler.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import config
from services.api_client import ApiClient

logger = logging.getLogger(__name__)

async def send_news_job(bot, api_client: ApiClient):
    if not config.NEWS_CHAT_ID: return
    logger.info("Executing scheduled news job...")
    try:
        news = await api_client.fetch_latest_news()
        if not news: return
        text = "📰 <b>Крипто-новости (авто):</b>\n\n" + "\n".join([f"🔹 <a href=\"{n['link']}\">{n['title']}</a>" for n in news])
        await bot.send_message(config.NEWS_CHAT_ID, text, disable_web_page_preview=True)
        logger.info(f"News sent to chat {config.NEWS_CHAT_ID}.")
    except Exception as e:
        logger.error("Error in send_news_job", extra={'error': str(e)})

async def update_asics_cache_job(api_client: ApiClient):
    logger.info("Executing scheduled ASIC cache update job...")
    await api_client.get_profitable_asics.cache.clear()
    await api_client.get_profitable_asics()

def setup_scheduler(bot, api_client: ApiClient) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    if config.NEWS_CHAT_ID:
        scheduler.add_job(send_news_job, 'interval', hours=config.NEWS_INTERVAL_HOURS, args=(bot, api_client))
    scheduler.add_job(update_asics_cache_job, 'interval', hours=config.ASIC_CACHE_UPDATE_HOURS, args=(api_client,))
    logger.info("Scheduler configured.")
    return scheduler