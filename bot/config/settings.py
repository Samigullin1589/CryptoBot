# bot/config/settings.py
# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Финальная, самодостаточная система конфигурации.
# Реализована гибридная загрузка: секреты из переменных окружения,
# остальное - из JSON-файов. Модели точно соответствуют структуре данных.
# =================================================================================

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger
from pydantic import BaseModel, Field, RedisDsn, HttpUrl, SecretStr, ConfigDict, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Определения моделей для частей конфигурации ---

class AIConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    provider: str = "gemini"
    # api_key будет загружен из переменных окружения
    model_name: str = Field(..., alias="default_model_name", description="Имя модели для использования")

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
    search_score_cutoff: int = 85 # Добавлено поле из coin_list_config.json

class NewsFeeds(BaseModel):
    # ИСПРАВЛЕНО: Модель для правильной валидации списков URL
    main_rss_feeds: List[HttpUrl]
    alpha_rss_feeds: List[HttpUrl]

class NewsServiceConfig(BaseModel):
    cache_ttl_seconds: int = Field(..., alias="subscription_ttl_seconds")
    feeds: NewsFeeds # Feeds будут добавлены из отдельного файла

class EndpointsConfig(BaseModel):
    # ИСПРАВЛЕНО: Все поля сделаны опциональными для гибкости.
    # Pydantic будет использовать только те, что найдет в файле.
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
    # 1. Поля, загружаемые из ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (стандарт для Render)
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    BOT_TOKEN: SecretStr
    ADMIN_IDS: List[int]
    REDIS_DSN: RedisDsn
    GEMINI_API_KEY: SecretStr

    # 2. Поля, загружаемые из JSON-файлов (заполняются ниже)
    log_level: str = "INFO"
    throttling: ThrottlingConfig
    feature_flags: FeatureFlags
    endpoints: EndpointsConfig
    price_service: PriceServiceConfig
    coin_list_service: CoinListServiceConfig
    news_service: NewsServiceConfig
    ai: AIConfig

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

def load_settings_from_files(base_path: str = "data") -> Settings:
    """
    Загружает JSON-файлы, переменные окружения и создает финальный объект настроек.
    """
    logger.info(f"Загрузка конфигураций из директории: {base_path}")
    
    base_dir = Path(base_path)
    
    # 1. Загружаем JSON-конфиги
    throttling_config = _load_json_file(base_dir / "throttling_config.json")
    feature_flags_config = _load_json_file(base_dir / "feature_flags.json")
    endpoints_config = _load_json_file(base_dir / "endpoints_config.json")
    price_service_config = _load_json_file(base_dir / "price_service_config.json")
    coin_list_config = _load_json_file(base_dir / "coin_list_config.json")
    ai_config_file = _load_json_file(base_dir / "ai_config.json")
    app_config = _load_json_file(base_dir / "app_config.json")

    # 2. Особая обработка для NewsService (объединение двух файлов)
    news_service_config_file = _load_json_file(base_dir / "news_service_config.json")
    news_feeds = _load_json_file(base_dir / "news_feeds.json")
    if news_feeds:
        news_service_config_file['feeds'] = news_feeds

    # 3. Собираем единый словарь из JSON-файлов
    json_data = {
        "log_level": app_config.get("log_level", "INFO"),
        "throttling": throttling_config,
        "feature_flags": feature_flags_config,
        "endpoints": endpoints_config,
        "price_service": price_service_config,
        "coin_list_service": coin_list_config,
        "news_service": news_service_config_file,
        "ai": ai_config_file,
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
