# ===============================================================
# Файл: bot/utils/dependencies.py (ПРОДАКШН-ВЕРСИЯ 2025)
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

# --- Создаем единственные экземпляры (singletons) ---

# Основные компоненты aiogram
bot: Bot = Bot(
    token=settings.api_keys.bot_token,
    default=DefaultBotProperties(parse_mode='HTML')
)
storage: RedisStorage = RedisStorage.from_url(settings.api_keys.redis_url)
dp: Dispatcher = Dispatcher(storage=storage)

# Вспомогательные клиенты
redis_client: redis.Redis = redis.from_url(settings.api_keys.redis_url, decode_responses=True)
http_session: aiohttp.ClientSession = aiohttp.ClientSession()
openai_client: AsyncOpenAI = AsyncOpenAI(api_key=settings.api_keys.openai_api_key) if settings.api_keys.openai_api_key else None
scheduler: AsyncIOScheduler = AsyncIOScheduler()

# Сервисы (создаются в правильном порядке зависимостей)
# Сначала базовые сервисы
stop_word_service: StopWordService = StopWordService(redis_client=redis_client)
security_service: SecurityService = SecurityService(
    http_session=http_session,
    config=settings
)
admin_service: AdminService = AdminService(redis_client=redis_client)
user_service: UserService = UserService(
    redis_client=redis_client,
    admin_service=admin_service,
    settings=settings
)
parser_service: ParserService = ParserService(
    http_session=http_session,
    config=settings.endpoints
)
asic_service: AsicService = AsicService(
    redis_client=redis_client,
    parser_service=parser_service,
    config=settings
)
coin_list_service: CoinListService = CoinListService(
    redis_client=redis_client,
    http_session=http_session,
    config=settings.endpoints
)
market_data_service: MarketDataService = MarketDataService(
    redis_client=redis_client,
    http_session=http_session,
    config=settings.endpoints
)
price_service: PriceService = PriceService(
    redis_client=redis_client,
    http_session=http_session,
    coin_list_service=coin_list_service,
    config=settings.endpoints
)
news_service: NewsService = NewsService(
    http_session=http_session,
    config=settings.news
)
ai_content_service: AIContentService = AIContentService(
    http_session=http_session,
    openai_client=openai_client,
    config=settings.api_keys
)
crypto_center_service: CryptoCenterService = CryptoCenterService(
    redis_client=redis_client,
    news_service=news_service,
    ai_content_service=ai_content_service
)
mining_service: MiningService = MiningService(
    market_data_service=market_data_service
)
mining_game_service: MiningGameService = MiningGameService(
    redis_client=redis_client,
    admin_service=admin_service,
    settings=settings
)
quiz_service: QuizService = QuizService(
    ai_content_service=ai_content_service,
    fallback_questions=settings.fallback_quiz
)

# --- Словарь для передачи зависимостей в middleware и хэндлеры ---
# Это позволяет не импортировать каждый сервис по отдельности в каждом файле
workflow_data = {
    "bot": bot,
    "dp": dp,
    "redis_client": redis_client,
    "http_session": http_session,
    "scheduler": scheduler,
    "settings": settings,
    "admin_service": admin_service,
    "asic_service": asic_service,
    "coin_list_service": coin_list_service,
    "crypto_center_service": crypto_center_service,
    "market_data_service": market_data_service,
    "mining_game_service": mining_game_service,
    "mining_service": mining_service,
    "news_service": news_service,
    "parser_service": parser_service,
    "price_service": price_service,
    "quiz_service": quiz_service,
    "security_service": security_service,
    "stop_word_service": stop_word_service,
    "user_service": user_service,
    "ai_content_service": ai_content_service,
}
