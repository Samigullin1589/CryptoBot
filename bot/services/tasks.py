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

# --- "АЛЬФА" ПАТТЕРН: КАЖДАЯ ЗАДАЧА ПОЛНОСТЬЮ САМОДОСТАТОЧНА ---

async def send_news_job():
    """Задача для отправки новостей. Сама создает и закрывает свои зависимости."""
    logger.info("Executing scheduled news job...")
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    session = aiohttp.ClientSession()
    try:
        if not settings.news_chat_id: return
        
        # NewsService может требовать http_session для работы
        news_service = NewsService(http_session=session)
        news = await news_service.fetch_latest_news()
        if not news: return
        
        text = "📰 <b>Крипто-новости (авто):</b>\n\n" + "\n".join(
            [f"🔹 <a href=\"{n['link']}\">{n['title']}</a>" for n in news]
        )
        await bot.send_message(settings.news_chat_id, text, disable_web_page_preview=True)
        logger.info(f"News sent to chat {settings.news_chat_id}.")
    except Exception as e:
        logger.error(f"Error in send_news_job: {e}", exc_info=True)
    finally:
        await session.close()
        await bot.session.close()


async def update_asics_cache_job():
    """Задача для обновления базы данных ASIC в Redis."""
    logger.info("Executing scheduled ASIC DB update job...")
    redis_client = redis.from_url(settings.redis_url, decode_responses=False)
    session = aiohttp.ClientSession()
    try:
        # AsicService может требовать http_session для загрузки данных
        asic_service = AsicService(redis_client=redis_client, http_session=session)
        await asic_service.update_asics_db()
    except Exception as e:
        logger.error(f"Error in update_asics_cache_job: {e}", exc_info=True)
    finally:
        await session.close()
        await redis_client.close()


async def send_morning_summary_job():
    """Задача для отправки утренней сводки."""
    logger.info("--- Starting morning summary job ---")
    if not settings.news_chat_id: return
    
    session = aiohttp.ClientSession()
    redis_client = redis.from_url(settings.redis_url, decode_responses=False)
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    try:
        coin_list_service = CoinListService(http_session=session)
        price_service = PriceService(coin_list_service, redis_client, session)
        market_data_service = MarketDataService(http_session=session)

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
    except Exception as e:
        logger.error(f"--- CRITICAL ERROR in send_morning_summary_job: {e} ---", exc_info=True)
    finally:
        await session.close()
        await redis_client.close()
        await bot.session.close()


async def send_leaderboard_job():
    """Задача для отправки еженедельного лидерборда по майнингу."""
    logger.info("Executing weekly leaderboard job...")
    if not settings.news_chat_id: return
    
    redis_client = redis.from_url(settings.redis_url, decode_responses=False)
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    try:
        admin_service = AdminService(redis_client=redis_client)
        top_users = await admin_service.get_top_users_by_balance(limit=5)
        
        if not top_users:
            text = "🏆 <b>Еженедельный лидерборд майнеров</b>\n\nНа этой неделе у нас пока нет лидеров. Начните играть, чтобы попасть в топ!"
        else:
            leaderboard_lines = []
            medals = ["🥇", "🥈", "🥉", "4.", "5."]
            for i, user_data in enumerate(top_users):
                username = f"@{user_data['username']}" if user_data.get('username') else f"User ID {user_data['user_id']}"
                balance = user_data['balance']
                leaderboard_lines.append(f"{medals[i]} {username} - <b>{balance:.2f} монет</b>")
            
            leaderboard_text = "\n".join(leaderboard_lines)
            text = (
                "🏆 <b>Еженедельный лидерборд майнеров</b>\n\n"
                "Вот наши лучшие игроки на этой неделе:\n\n"
                f"{leaderboard_text}\n\n"
                "Продолжайте в том же духе! Новый лидерборд — в следующую пятницу."
            )
        await bot.send_message(settings.news_chat_id, text)
        logger.info(f"Leaderboard sent to chat {settings.news_chat_id}.")
    except Exception as e:
        logger.error(f"Error in send_leaderboard_job: {e}", exc_info=True)
    finally:
        await redis_client.close()
        await bot.session.close()


async def health_check_job():
    """Отладочная задача для проверки работы планировщика."""
    logger.info("--- SCHEDULER HEALTH CHECK: Job is running! ---")
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode='HTML'))
    try:
        if settings.admin_chat_id:
            await bot.send_message(settings.admin_chat_id, "Scheduler health check: OK.")
            logger.info(f"Health check message sent to admin {settings.admin_chat_id}.")
    except Exception as e:
        logger.error(f"--- CRITICAL ERROR in health_check_job: {e} ---", exc_info=True)
    finally:
        await bot.session.close()
