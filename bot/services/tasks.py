import logging
import aiohttp
import redis.asyncio as redis
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from bot.config.settings import settings
# Импортируем классы сервисов, чтобы создавать их экземпляры внутри задач
from bot.services.news_service import NewsService
from bot.services.asic_service import AsicService
from bot.services.price_service import PriceService
from bot.services.market_data_service import MarketDataService
from bot.services.admin_service import AdminService
from bot.services.coin_list_service import CoinListService

logger = logging.getLogger(__name__)

# --- "АЛЬФА" ПАТТЕРН: СОЗДАНИЕ И ЗАКРЫТИЕ ЗАВИСИМОСТЕЙ ВНУТРИ ЗАДАЧИ ---

async def with_task_dependencies(func):
    """
    Декоратор, который создает все необходимые зависимости для фоновой задачи,
    выполняет ее и гарантированно закрывает все соединения.
    """
    async def wrapper():
        session = aiohttp.ClientSession()
        redis_client = redis.from_url(settings.redis_url, decode_responses=False)
        bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
        
        try:
            # Создаем экземпляры сервисов
            coin_list_service = CoinListService()
            news_service = NewsService()
            market_data_service = MarketDataService()
            asic_service = AsicService(redis_client=redis_client)
            price_service = PriceService(
                coin_list_service=coin_list_service, 
                redis_client=redis_client, 
                http_session=session
            )
            admin_service = AdminService(redis_client=redis_client)
            
            # Передаем созданные зависимости в саму функцию задачи
            await func(
                bot=bot,
                news_service=news_service,
                asic_service=asic_service,
                price_service=price_service,
                market_data_service=market_data_service,
                admin_service=admin_service
            )
        finally:
            # Гарантированно закрываем все соединения
            await session.close()
            await redis_client.close()
            await bot.session.close()
    return wrapper


@with_task_dependencies
async def send_news_job(bot, news_service, **kwargs):
    """Задача для отправки новостей."""
    logger.info("Executing scheduled news job...")
    if not settings.news_chat_id: return
    news = await news_service.fetch_latest_news()
    if not news: return
    text = "📰 <b>Крипто-новости (авто):</b>\n\n" + "\n".join(
        [f"🔹 <a href=\"{n['link']}\">{n['title']}</a>" for n in news]
    )
    await bot.send_message(settings.news_chat_id, text, disable_web_page_preview=True)
    logger.info(f"News sent to chat {settings.news_chat_id}.")


@with_task_dependencies
async def update_asics_cache_job(asic_service, **kwargs):
    """Задача для обновления базы данных ASIC в Redis."""
    logger.info("Executing scheduled ASIC DB update job...")
    await asic_service.update_asics_db()


@with_task_dependencies
async def send_morning_summary_job(bot, price_service, market_data_service, **kwargs):
    """Задача для отправки утренней сводки."""
    logger.info("--- Starting morning summary job ---")
    if not settings.news_chat_id: return

    btc_coin = await price_service.get_crypto_price('BTC')
    eth_coin = await price_service.get_crypto_price('ETH')
    fng_index = await market_data_service.get_fear_and_greed_index()

    btc_price = f"{btc_coin.price:,.2f}" if btc_coin else "N/A"
    eth_price = f"{eth_coin.price:,.2f}" if eth_coin else "N/A"
    fng_value = fng_index.get('value', 'N/A') if fng_index else 'N/A'
    fng_text = fng_index.get('value_classification', 'N/A') if fng_index else 'N/A'

    text = (
        "☕️ <b>Доброе утро! Ваша крипто-сводка:</b>\n\n"
        f"<b>Bitcoin (BTC):</b> ${btc_price}\n"
        f"<b>Ethereum (ETH):</b> ${eth_price}\n\n"
        f"<b>Индекс страха и жадности:</b> {fng_value} ({fng_text})"
    )
    await bot.send_message(settings.news_chat_id, text)
    logger.info(f"--- Morning summary sent successfully to chat {settings.news_chat_id} ---")


@with_task_dependencies
async def send_leaderboard_job(bot, admin_service, **kwargs):
    """Задача для отправки еженедельного лидерборда по майнингу."""
    logger.info("Executing weekly leaderboard job...")
    if not settings.news_chat_id: return
    
    top_users = await admin_service.get_top_users_by_balance(limit=5)
    
    if not top_users:
        text = "🏆 <b>Еженедельный лидерборд майнеров</b>\n\nНа этой неделе у нас пока нет лидеров."
    else:
        leaderboard_lines = [f"{'🥇🥈🥉'[i]} {f\"@{d['username']}\" if d.get('username') else f\"User ID {d['user_id']}\"} - <b>{d['balance']:.2f} монет</b>" for i, d in enumerate(top_users)]
        leaderboard_text = "\n".join(leaderboard_lines)
        text = f"🏆 <b>Еженедельный лидерборд майнеров</b>\n\n{leaderboard_text}"
        
    await bot.send_message(settings.news_chat_id, text)
    logger.info(f"Leaderboard sent to chat {settings.news_chat_id}.")


@with_task_dependencies
async def health_check_job(bot, **kwargs):
    """Отладочная задача для проверки работы планировщика."""
    logger.info("--- SCHEDULER HEALTH CHECK: Job is running! ---")
    if settings.admin_chat_id:
        await bot.send_message(settings.admin_chat_id, "Scheduler health check: OK.")
        logger.info(f"Health check message sent to admin {settings.admin_chat_id}.")
