# bot/config/settings.py
# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Финальная, самодостаточная система конфигурации.
# ИСПРАВЛЕНИЕ: Изменен тип ADMIN_USER_IDS на 'Any' и используется
# @field_validator для гарантированной обработки строки с запятыми ПОСЛЕ
# её успешного считывания, что решает ошибку парсинга.
# =================================================================================

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger
from dotenv import load_dotenv
from pydantic import (BaseModel, Field, RedisDsn, HttpUrl, SecretStr,
                      ConfigDict, ValidationError, field_validator)
from pydantic_settings import BaseSettings, SettingsConfigDict

# Гарантированно загружаем переменные из .env файла или окружения Render
load_dotenv()

# --- Определения моделей для частей конфигурации ---

class AIConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    provider: str = "gemini"
    model_name: str = Field(..., alias="default_model_name")

class ThrottlingConfig(BaseModel):
    rate_limit: float = 0.5
    key_prefix: str = "throttling"

class FeatureFlags(BaseModel):
    maintenance_mode: bool = False
    enable_game: bool = True
    enable_threat_protection: bool = True

class PriceServiceConfig(BaseModel):
    cache_ttl_seconds: int = 300
    top_n_coins: int = 100

class CoinListServiceConfig(BaseModel):
    update_interval_hours: int
    fallback_file_path: str
    search_score_cutoff: int = 85

class NewsFeeds(BaseModel):
    main_rss_feeds: List[HttpUrl]
    alpha_rss_feeds: List[HttpUrl]

class NewsServiceConfig(BaseModel):
    cache_ttl_seconds: int = Field(..., alias="subscription_ttl_seconds")
    feeds: NewsFeeds

class EndpointsConfig(BaseModel):
    coingecko_api_base: Optional[HttpUrl] = None
    coingecko_api_coins_list: Optional[HttpUrl] = None
    coingecko_api_simple_price: Optional[HttpUrl] = None
    coingecko_api_coins_markets: Optional[HttpUrl] = None
    coingecko_api_trending: Optional[HttpUrl] = None
    blockchain_info_hashrate: Optional[HttpUrl] = None
    mempool_space_difficulty: Optional[HttpUrl] = None
    whattomine_api: Optional[HttpUrl] = None
    minerstat_api: Optional[HttpUrl] = None

# --- Главная модель настроек ---

class Settings(BaseSettings):
    """
    Главный класс настроек. Загружает данные из переменных окружения и JSON-файлов.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # 1. Поля из ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
    BOT_TOKEN: SecretStr
    # ИСПРАВЛЕНИЕ: Читаем как 'Any', чтобы избежать ошибки парсинга по умолчанию
    ADMIN_USER_IDS: Any
    REDIS_URL: RedisDsn
    GEMINI_API_KEY: SecretStr
    ADMIN_CHAT_ID: Optional[int] = None
    NEWS_CHAT_ID: Optional[int] = None
    OPENAI_API_KEY: Optional[SecretStr] = None
    CRYPTOCOMPARE_API_KEY: Optional[SecretStr] = None

    # 2. Поля из JSON-файлов
    log_level: str = "INFO"
    throttling: ThrottlingConfig
    feature_flags: FeatureFlags
    endpoints: EndpointsConfig
    price_service: PriceServiceConfig
    coin_list_service: CoinListServiceConfig
    news_service: NewsServiceConfig
    ai: AIConfig

    # ИСПРАВЛЕНИЕ: Используем @field_validator, который сработает ПОСЛЕ чтения строки
    @field_validator('ADMIN_USER_IDS', mode='before')
    @classmethod
    def parse_admin_ids(cls, v: Any) -> List[int]:
        """
        Преобразует строку '1,2,3' в список чисел [1, 2, 3].
        """
        if isinstance(v, str):
            # Если это строка, разделяем ее по запятой и преобразуем в список int
            return [int(item.strip()) for item in v.split(',') if item.strip()]
        if isinstance(v, list):
            # Если это уже список (например, из JSON), просто возвращаем его
            return v
        raise ValueError("ADMIN_USER_IDS должен быть строкой с запятыми или списком")

def _load_json_file(path: Path) -> Dict[str, Any]:
    """Вспомогательная функция для безопасной загрузки JSON."""
    if not path.exists():
        logger.warning(f"Файл конфигурации не найден: {path}, пропуск.")
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Не удалось прочитать или декодировать файл {path}: {e}")
        raise SystemExit(f"Критическая ошибка конфигурации в файле: {path.name}")

def load_settings_from_files() -> Settings:
    """
    Загружает JSON-файлы, переменные окружения и создает финальный объект настроек.
    """
    logger.info("Загрузка конфигураций...")
    base_dir = Path("data")

    # 1. Загружаем все JSON-конфиги
    json_files = {
        "throttling": _load_json_file(base_dir / "throttling_config.json"),
        "feature_flags": _load_json_file(base_dir / "feature_flags.json"),
        "endpoints": _load_json_file(base_dir / "endpoints_config.json"),
        "price_service": _load_json_file(base_dir / "price_service_config.json"),
        "coin_list_service": _load_json_file(base_dir / "coin_list_config.json"),
        "ai": _load_json_file(base_dir / "ai_config.json"),
        "app": _load_json_file(base_dir / "app_config.json"),
        "news_service": _load_json_file(base_dir / "news_service_config.json"),
        "news_feeds": _load_json_file(base_dir / "news_feeds.json"),
    }

    # 2. Объединяем связанные конфиги
    if json_files["news_feeds"]:
        json_files["news_service"]['feeds'] = json_files["news_feeds"]

    # 3. Собираем единый словарь из JSON-данных
    json_data = {
        "log_level": json_files["app"].get("log_level", "INFO"),
        "throttling": json_files["throttling"],
        "feature_flags": json_files["feature_flags"],
        "endpoints": json_files["endpoints"],
        "price_service": json_files["price_service"],
        "coin_list_service": json_files["coin_list_service"],
        "news_service": json_files["news_service"],
        "ai": json_files["ai"],
    }

    try:
        # 4. Инициализируем Settings. Pydantic автоматически подтянет переменные окружения
        # и мы добавим к ним данные из JSON.
        settings_instance = Settings(**json_data)
        logger.info("Все конфигурации успешно загружены и валидированы.")
        return settings_instance
    except ValidationError as e:
        logger.critical(f"Критическая ошибка валидации настроек. Проверьте ваши .json файлы и переменные окружения. Ошибки:\n{e}")
        raise SystemExit("Не удалось инициализировать настройки из-за ошибок валидации.")

# Создаем единственный глобальный экземпляр настроек
settings = load_settings_from_files()
