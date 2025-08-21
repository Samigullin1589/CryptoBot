# src/bot/containers.py
# =================================================================================
# Файл: bot/containers.py
# Версия: "Distinguished Engineer" — МАКСИМАЛЬНАЯ
# Описание:
#   • Центральный DI-контейнер, адаптированный под новую, вложенную конфигурацию.
#   • Инициализирует Redis-клиент напрямую из DSN (REDIS_URL).
#   • Прокидывает в каждый сервис только его собственный, изолированный
#     блок настроек (например, settings.price_service), а не весь объект целиком.
#     Это улучшает инкапсуляцию и упрощает тестирование.
#   • Полностью совместим с вашим расширенным файлом settings.py.
# =================================================================================

from dependency_injector import containers, providers
from redis.asyncio import Redis

from bot.config.settings import Settings, settings
from bot.services.achievement_service import AchievementService
from bot.services.admin_service import AdminService
from bot.services.asic_service import AsicService
from bot.services.coin_alias_service import CoinAliasService
from bot.services.coin_list_service import CoinListService
from bot.services.crypto_center_service import CryptoCenterService
from bot.services.market_data_service import MarketDataService
from bot.services.mining_game_service import MiningGameService
from bot.services.news_service import NewsService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.services.user_service import UserService
from bot.utils.http_client import HttpClient


class Container(containers.DeclarativeContainer):
    """
    Основной контейнер приложения.
    """
    # --- Wiring ---
    # Указываем модули для "проброса" зависимостей.
    wiring_config = containers.WiringConfiguration(
        modules=[
            "bot.main",
            "bot.middlewares.dependencies_middleware",
            "bot.handlers.public.start_handler",
            "bot.handlers.public.price_handler",
            "bot.handlers.public.market_handler",
            "bot.handlers.public.market_info_handler",
            "bot.handlers.public.news_handler",
            "bot.handlers.public.quiz_handler",
            "bot.handlers.public.achievements_handler",
            "bot.handlers.public.asic_handler",
            "bot.handlers.public.crypto_center_handler",
            "bot.handlers.public.game_handler",
            "bot.handlers.game.mining_game_handler",
            "bot.handlers.admin.admin_handler",
            "bot.handlers.admin.cache_handler",
            "bot.handlers.admin.stats_handler",
            "bot.jobs.scheduled_tasks",
        ]
    )

    # --- Конфигурация ---
    # Предоставляем полный объект настроек
    config: providers.Provider[Settings] = providers.Object(settings)

    # --- Клиенты ---
    # Используем Singleton, чтобы во всем приложении был один экземпляр.
    # Инициализируем Redis из DSN-строки, как и положено.
    redis_client = providers.Singleton(
        Redis.from_url,
        url=config.provided.REDIS_URL.get_secret_value(),
        decode_responses=True,
    )

    http_client = providers.Singleton(HttpClient, config=config.provided.endpoints)

    # --- Сервисы ---
    # Каждый сервис получает только свой, строго типизированный блок конфигурации.
    # Это лучшая практика, так как сервис не знает о существовании других настроек.

    user_service = providers.Singleton(
        UserService,
        redis_client=redis_client,
    )

    coin_list_service = providers.Singleton(
        CoinListService,
        redis_client=redis_client,
        http_client=http_client,
        config=config.provided.coin_list_service,
    )

    coin_alias_service = providers.Singleton(
        CoinAliasService,
        redis_client=redis_client,
        coin_list_service=coin_list_service,
    )

    market_data_service = providers.Singleton(
        MarketDataService,
        redis_client=redis_client,
        http_client=http_client,
        config=config.provided.market_data,
    )

    price_service = providers.Singleton(
        PriceService,
        redis_client=redis_client,
        http_client=http_client,
        market_data_service=market_data_service,
        coin_alias_service=coin_alias_service,
        config=config.provided.price_service,
    )

    news_service = providers.Singleton(
        NewsService,
        redis_client=redis_client,
        http_client=http_client,
        config=config.provided.news_service,
    )

    quiz_service = providers.Singleton(
        QuizService,
        redis_client=redis_client,
        http_client=http_client,
        config=config.provided.quiz,
    )

    achievement_service = providers.Singleton(
        AchievementService,
        redis_client=redis_client,
        config=config.provided.achievements,
    )

    asic_service = providers.Singleton(
        AsicService,
        redis_client=redis_client,
        http_client=http_client,
        config=config.provided.asic_service,
    )

    crypto_center_service = providers.Singleton(
        CryptoCenterService,
        redis_client=redis_client,
        http_client=http_client,
        news_service=news_service,
        config=config.provided.crypto_center,
    )

    mining_game_service = providers.Singleton(
        MiningGameService,
        redis_client=redis_client,
        config=config.provided.game,
    )

    admin_service = providers.Singleton(
        AdminService,
        redis_client=redis_client,
        # Админскому сервису может потребоваться доступ ко всем настройкам
        config=config,
    )