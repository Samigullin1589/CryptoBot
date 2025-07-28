# ===============================================================
# Файл: bot/utils/dependencies.py (ПРОДАКШН-ВЕРСИЯ 2025 v2)
# Описание: Централизованный модуль для управления зависимостями (DI).
# Создает и хранит единственные экземпляры всех ключевых
# компонентов бота (Bot, Dispatcher, сервисы и т.д.).
# ===============================================================

import aiohttp
import redis.asyncio as redis
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import AsyncOpenAI
from typing import Optional

# Импортируем все наши компоненты
from bot.config.settings import settings
from bot.services.admin_service import AdminService
from bot.services.asic_service import AsicService
from bot.services.coin_list_service import CoinListService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.market_data_service import MarketDataService
from bot.services.mining_game_service import MiningGameService
from bot.services.mining_service import MiningService
from bot.services.news_service import NewsService
from bot.services.parser_service import ParserService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.services.security_service import SecurityService
from bot.services.stop_word_service import StopWordService
from bot.services.user_service import UserService
from bot.services.ai_content_service import AIContentService

# --- Объявляем переменные для зависимостей (будут созданы позже) ---

bot: Optional[Bot] = None
storage: Optional[RedisStorage] = None
dp: Optional[Dispatcher] = None
redis_client: Optional[redis.Redis] = None
http_session: Optional[aiohttp.ClientSession] = None
openai_client: Optional[AsyncOpenAI] = None
scheduler: Optional[AsyncIOScheduler] = None
admin_service: Optional[AdminService] = None
user_service: Optional[UserService] = None
# ... и так далее для всех сервисов
asic_service: Optional[AsicService] = None
coin_list_service: Optional[CoinListService] = None
crypto_center_service: Optional[CryptoCenterService] = None
market_data_service: Optional[MarketDataService] = None
mining_game_service: Optional[MiningGameService] = None
mining_service: Optional[MiningService] = None
news_service: Optional[NewsService] = None
parser_service: Optional[ParserService] = None
price_service: Optional[PriceService] = None
quiz_service: Optional[QuizService] = None
security_service: Optional[SecurityService] = None
stop_word_service: Optional[StopWordService] = None
ai_content_service: Optional[AIContentService] = None
workflow_data: dict = {}

async def initialize_dependencies():
    """
    Асинхронно создает и инициализирует все зависимости.
    Должна вызываться внутри запущенного event loop.
    """
    global bot, storage, dp, redis_client, http_session, openai_client, scheduler
    global admin_service, user_service, asic_service, coin_list_service, crypto_center_service
    global market_data_service, mining_game_service, mining_service, news_service, parser_service
    global price_service, quiz_service, security_service, stop_word_service, ai_content_service
    global workflow_data

    # Основные компоненты aiogram
    bot = Bot(
        token=settings.api_keys.bot_token,
        default=DefaultBotProperties(parse_mode='HTML')
    )
    storage = RedisStorage.from_url(settings.api_keys.redis_url)
    dp = Dispatcher(storage=storage)

    # Вспомогательные клиенты
    redis_client = redis.from_url(settings.api_keys.redis_url, decode_responses=True)
    http_session = aiohttp.ClientSession()
    openai_client = AsyncOpenAI(api_key=settings.api_keys.openai_api_key) if settings.api_keys.openai_api_key else None
    scheduler = AsyncIOScheduler()

    # Сервисы (создаются в правильном порядке зависимостей)
    stop_word_service = StopWordService(redis_client=redis_client)
    security_service = SecurityService(http_session=http_session, config=settings)
    admin_service = AdminService(redis_client=redis_client)
    user_service = UserService(redis_client=redis_client, admin_service=admin_service, settings=settings)
    parser_service = ParserService(http_session=http_session, config=settings.endpoints)
    asic_service = AsicService(redis_client=redis_client, parser_service=parser_service, config=settings)
    coin_list_service = CoinListService(redis_client=redis_client, http_session=http_session, config=settings.endpoints)
    market_data_service = MarketDataService(redis_client=redis_client, http_session=http_session, config=settings.endpoints)
    price_service = PriceService(redis_client=redis_client, http_session=http_session, coin_list_service=coin_list_service, config=settings.endpoints)
    news_service = NewsService(http_session=http_session, config=settings.news)
    ai_content_service = AIContentService(http_session=http_session, openai_client=openai_client, config=settings.api_keys)
    crypto_center_service = CryptoCenterService(redis_client=redis_client, news_service=news_service, ai_content_service=ai_content_service)
    mining_service = MiningService(market_data_service=market_data_service)
    mining_game_service = MiningGameService(redis_client=redis_client, admin_service=admin_service, settings=settings)
    quiz_service = QuizService(ai_content_service=ai_content_service, fallback_questions=settings.fallback_quiz)

    workflow_data.update({
        "bot": bot, "dp": dp, "redis_client": redis_client, "http_session": http_session,
        "scheduler": scheduler, "settings": settings, "admin_service": admin_service,
        "asic_service": asic_service, "coin_list_service": coin_list_service,
        "crypto_center_service": crypto_center_service, "market_data_service": market_data_service,
        "mining_game_service": mining_game_service, "mining_service": mining_service,
        "news_service": news_service, "parser_service": parser_service, "price_service": price_service,
        "quiz_service": quiz_service, "security_service": security_service,
        "stop_word_service": stop_word_service, "user_service": user_service,
        "ai_content_service": ai_content_service,
    })

async def close_dependencies():
    """Корректно закрывает все соединения."""
    if http_session:
        await http_session.close()
    if redis_client:
        await redis_client.close()
    if bot:
        await bot.session.close()
