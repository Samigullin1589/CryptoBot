import logging
from bot.utils import dependencies
from bot.config.settings import settings

logger = logging.getLogger(__name__)

async def send_news_job():
    """Задача для отправки новостей."""
    logger.info("Executing scheduled news job...")
    try:
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
        logger.error("Error in send_news_job", exc_info=True)


async def update_asics_cache_job():
    """Задача для обновления кэша ASIC."""
    logger.info("Executing scheduled ASIC cache update job...")
    try:
        asic_service = dependencies.asic_service
        if not asic_service:
            logger.warning("update_asics_cache_job skipped: asic_service not initialized.")
            return
        await asic_service.get_profitable_asics()
    except Exception as e:
        logger.error("Error in update_asics_cache_job", exc_info=True)


# --- ИЗМЕНЕНИЯ ЗДЕСЬ ---
async def send_morning_summary_job():
    """Задача для отправки утренней сводки (Курсы + Индекс F&G)."""
    logger.info("--- Starting morning summary job ---")
    try:
        bot = dependencies.bot
        price_service = dependencies.price_service
        market_data_service = dependencies.market_data_service

        if not all([bot, price_service, market_data_service, settings.news_chat_id]):
            logger.warning("send_morning_summary_job skipped: dependencies or chat_id not available.")
            return

        logger.info("All dependencies found. Fetching data...")
        
        # ИСПРАВЛЕНИЕ: Получаем каждую цену отдельно
        btc_coin = await price_service.get_crypto_price('BTC')
        eth_coin = await price_service.get_crypto_price('ETH')
        logger.info(f"Prices fetched: BTC {'OK' if btc_coin else 'Failed'}, ETH {'OK' if eth_coin else 'Failed'}")
        
        fng_index = await market_data_service.get_fear_and_greed_index()
        logger.info(f"F&G Index fetched: {'OK' if fng_index else 'Failed'}")

        # Формируем текст, проверяя наличие данных
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
        logger.error("--- CRITICAL ERROR in send_morning_summary_job ---", exc_info=True)


async def send_leaderboard_job():
    """Задача для отправки еженедельного лидерборда по майнингу."""
    logger.info("Executing weekly leaderboard job...")
    try:
        bot = dependencies.bot
        admin_service = dependencies.admin_service
        if not all([bot, admin_service, settings.news_chat_id]):
            logger.warning("send_leaderboard_job skipped: dependencies or chat_id not available.")
            return

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
        logger.error("Error in send_leaderboard_job", exc_info=True)


async def health_check_job():
    """Отладочная задача для проверки работы планировщика."""
    logger.info("--- SCHEDULER HEALTH CHECK: Job is running! ---")
    try:
        bot = dependencies.bot
        if bot and settings.admin_chat_id:
            await bot.send_message(settings.admin_chat_id, "Scheduler health check: OK. Задачи выполняются по расписанию.")
            logger.info(f"Health check message sent to admin {settings.admin_chat_id}.")
        else:
            logger.warning("Health check: Bot or admin_chat_id not available to send message.")
    except Exception as e:
        logger.error("--- CRITICAL ERROR in health_check_job ---", exc_info=True)