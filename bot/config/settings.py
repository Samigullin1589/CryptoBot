# bot/config/settings.py
# Файл полностью переработан для использования Pydantic V2.
# Это обеспечивает строгую валидацию данных при запуске, повышает надёжность
# и упрощает работу с конфигурациями.

import json
import os
from typing import List, Dict, Type, TypeVar

from loguru import logger
from pydantic import BaseModel, Field, RedisDsn, HttpUrl, SecretStr

# Generic Pydantic model type
T = TypeVar('T', bound=BaseModel)


def _load_model_from_path(model: Type[T], path: str) -> T:
    """
    Загружает и валидирует Pydantic модель из указанного JSON файла.
    Вызывает исключения, если файл не найден, имеет неверный формат или не проходит валидацию.
    """
    if not os.path.exists(path):
        logger.error(f"Файл конфигурации не найден: {path}")
        raise FileNotFoundError(f"Файл конфигурации не найден: {path}")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return model.model_validate(data)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON из {path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Не удалось загрузить или валидировать конфигурацию из {path}: {e}")
        raise


# --- Определения моделей конфигурации ---

class BotConfig(BaseModel):
    """Конфигурация для самого Telegram бота."""
    token: SecretStr  # SecretStr защищает токен от случайного логирования
    admin_ids: List[int]


class RedisConfig(BaseModel):
    """Конфигурация для подключения к Redis."""
    dsn: RedisDsn = Field(..., description="Строка подключения к Redis, например 'redis://user:password@host:port'")
    host: str
    port: int
    db: int = Field(0, ge=0, le=15)
    password: SecretStr | None = None


class AppConfig(BaseModel):
    """Вложенная структура для файла app_config.json."""
    bot: BotConfig
    redis: RedisConfig


class ThrottlingConfig(BaseModel):
    """Конфигурация для middleware ограничения запросов."""
    rate_limit: float = 0.5
    key_prefix: str = "throttling"


class FeatureFlags(BaseModel):
    """Флаги для включения/отключения функционала бота."""
    maintenance_mode: bool = False
    enable_game: bool = True
    enable_threat_protection: bool = True


class EndpointsConfig(BaseModel):
    """API эндпоинты, используемые различными сервисами."""
    coingecko_api_base: HttpUrl
    coingecko_api_coins_list: HttpUrl
    coingecko_api_simple_price: HttpUrl
    coingecko_api_coins_markets: HttpUrl
    coingecko_api_trending: HttpUrl
    blockchain_info_hashrate: HttpUrl
    mempool_space_difficulty: HttpUrl


class PriceServiceConfig(BaseModel):
    """Конфигурация для сервиса цен."""
    cache_ttl_seconds: int = 300
    top_n_coins: int = 100


class CoinListServiceConfig(BaseModel):
    """Конфигурация для сервиса списка монет. ИСПРАВЛЯЕТ ИСХОДНУЮ ОШИБКУ."""
    update_interval_hours: int
    fallback_file_path: str


class NewsServiceConfig(BaseModel):
    """Конфигурация для сервиса новостей."""
    cache_ttl_seconds: int = 3600
    feeds: Dict[str, HttpUrl]


class AIConfig(BaseModel):
    """Конфигурация для AI сервисов (например, Gemini)."""
    provider: str = "gemini"
    api_key: SecretStr
    model_name: str = "gemini-1.5-flash-latest"


class Settings(BaseModel):
    """
    Главный объект настроек, агрегирующий все конфигурации.
    Собирается функцией load_settings.
    """
    app: AppConfig
    throttling: ThrottlingConfig
    feature_flags: FeatureFlags
    endpoints: EndpointsConfig
    price_service: PriceServiceConfig
    coin_list_service: CoinListServiceConfig
    news_service: NewsServiceConfig
    ai: AIConfig
    # Другие модели конфигураций добавляются сюда как атрибуты


def load_settings(base_path: str = "data") -> Settings:
    """
    Загружает все файлы конфигурации из указанной директории,
    валидирует их и возвращает единый, всеобъемлющий объект Settings.
    Эта функция является единственным источником истины для всех настроек бота.
    """
    logger.info(f"Загрузка конфигураций из директории: {base_path}")
    try:
        # Загружаем каждый файл конфигурации в соответствующую Pydantic модель
        app_config = _load_model_from_path(AppConfig, os.path.join(base_path, "app_config.json"))
        throttling_config = _load_model_from_path(ThrottlingConfig, os.path.join(base_path, "throttling_config.json"))
        feature_flags = _load_model_from_path(FeatureFlags, os.path.join(base_path, "feature_flags.json"))
        endpoints_config = _load_model_from_path(EndpointsConfig, os.path.join(base_path, "endpoints_config.json"))
        price_service_config = _load_model_from_path(PriceServiceConfig, os.path.join(base_path, "price_service_config.json"))
        coin_list_service_config = _load_model_from_path(CoinListServiceConfig, os.path.join(base_path, "coin_list_config.json"))
        news_service_config = _load_model_from_path(NewsServiceConfig, os.path.join(base_path, "news_service_config.json"))
        ai_config = _load_model_from_path(AIConfig, os.path.join(base_path, "ai_config.json"))

        # Собираем финальный объект Settings
        settings = Settings(
            app=app_config,
            throttling=throttling_config,
            feature_flags=feature_flags,
            endpoints=endpoints_config,
            price_service=price_service_config,
            coin_list_service=coin_list_service_config,
            news_service=news_service_config,
            ai=ai_config,
        )
        logger.info("Все конфигурации успешно загружены и валидированы.")
        return settings

    except Exception as e:
        logger.critical(f"Критическая ошибка во время инициализации настроек: {e}")
        raise SystemExit(f"Не удалось инициализировать настройки: {e}")
