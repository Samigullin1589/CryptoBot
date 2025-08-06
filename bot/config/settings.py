# bot/config/settings.py
# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "Distinguished Engineer" - ЗАПУСК)
# Описание: Финальная, самодостаточная система конфигурации.
# ИСПРАВЛЕНИЕ: Добавлена недостающая конфигурация ThreatFilterConfig.
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
    provider: str = Field(default="gemini")
    model_name: str = Field(default="gemini-1.5-flash-latest", alias="default_model_name")

class ThrottlingConfig(BaseModel):
    rate_limit: float = Field(default=0.5)
    key_prefix: str = Field(default="throttling")

class FeatureFlags(BaseModel):
    maintenance_mode: bool = Field(default=False)
    enable_game: bool = Field(default=True)
    enable_threat_protection: bool = Field(default=True)

class PriceServiceConfig(BaseModel):
    cache_ttl_seconds: int = Field(default=300)
    top_n_coins: int = Field(default=100)

class CoinListServiceConfig(BaseModel):
    update_interval_hours: int = Field(default=24)
    fallback_file_path: str = Field(default="data/fallback_coins.json")
    search_score_cutoff: int = Field(default=85)

class NewsFeeds(BaseModel):
    main_rss_feeds: List[HttpUrl] = Field(default=[])
    alpha_rss_feeds: List[HttpUrl] = Field(default=[])

class NewsServiceConfig(BaseModel):
    cache_ttl_seconds: int = Field(default=3600, alias="subscription_ttl_seconds")
    feeds: NewsFeeds = Field(default_factory=NewsFeeds)

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

# ИСПРАВЛЕНО: Добавлена недостающая модель конфигурации
class ThreatFilterConfig(BaseModel):
    """Конфигурация для фильтра угроз."""
    enabled: bool = Field(default=True)
    thresholds: Dict[str, float] = Field(default_factory=dict)

# --- Главная модель настроек ---

class Settings(BaseSettings):
    """
    Главный класс настроек. Загружает данные из переменных окружения и JSON-файлов.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # 1. Поля из ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
    BOT_TOKEN: SecretStr
    ADMIN_USER_IDS: Any # Валидируется ниже
    REDIS_URL: RedisDsn
    GEMINI_API_KEY: SecretStr
    ADMIN_CHAT_ID: Optional[int] = None
    NEWS_CHAT_ID: Optional[int] = None
    OPENAI_API_KEY: Optional[SecretStr] = None
    CRYPTOCOMPARE_API_KEY: Optional[SecretStr] = None
    PERSPECTIVE_API_KEY: Optional[SecretStr] = None # Для ThreatFilter

    # 2. Поля из JSON-файлов
    log_level: str = "INFO"
    throttling: ThrottlingConfig
    feature_flags: FeatureFlags
    endpoints: EndpointsConfig
    price_service: PriceServiceConfig
    coin_list_service: CoinListServiceConfig
    news_service: NewsServiceConfig
    ai: AIConfig
    threat_filter: ThreatFilterConfig # ИСПРАВЛЕНО: Добавлено поле

    @field_validator('ADMIN_USER_IDS', mode='before')
    @classmethod
    def parse_admin_ids(cls, v: Any) -> List[int]:
        if isinstance(v, str):
            return [int(item.strip()) for item in v.split(',') if item.strip()]
        if isinstance(v, list):
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
        "threat_filter": _load_json_file(base_dir / "threat_filter_config.json"), # ИСПРАВЛЕНО: Добавлена загрузка
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
        "threat_filter": json_files["threat_filter"], # ИСПРАВЛЕНО: Добавлено в финальный словарь
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
