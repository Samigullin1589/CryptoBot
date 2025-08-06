# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "Distinguished Engineer" - АВГУСТ 2025)
# Описание: Единая, строго типизированная и самодостаточная система конфигурации.
# ИСПРАВЛЕНИЕ: Устранена причина ImportError. Структура унифицирована.
# Все настройки загружаются из .env и JSON-файлов в единую модель.
# =================================================================================

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger
from dotenv import load_dotenv
from pydantic import (BaseModel, Field, RedisDsn, HttpUrl, SecretStr,
                      ValidationError, field_validator)
from pydantic_settings import BaseSettings, SettingsConfigDict

# Гарантированно загружаем переменные из .env файла в самом начале
load_dotenv()

# --- Определения моделей для частей конфигурации (из JSON-файлов) ---

class AIConfig(BaseModel):
    provider: str = "gemini"
    model_name: str = "gemini-1.5-flash-latest"

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
    update_interval_hours: int = 24
    fallback_file_path: str = "data/fallback_coins.json"
    search_score_cutoff: int = 85

class NewsFeeds(BaseModel):
    main_rss_feeds: List[HttpUrl] = []
    alpha_rss_feeds: List[HttpUrl] = []

class NewsServiceConfig(BaseModel):
    cache_ttl_seconds: int = 3600
    feeds: NewsFeeds = Field(default_factory=NewsFeeds)

class EndpointsConfig(BaseModel):
    coingecko_api_base: HttpUrl = "https://api.coingecko.com/api/v3"
    blockchain_info_hashrate: HttpUrl = "https://api.blockchain.info/q/hashrate"
    mempool_space_difficulty: HttpUrl = "https://mempool.space/api/v1/difficulty-adjustment"
    whattomine_api: Optional[HttpUrl] = None
    minerstat_api: Optional[HttpUrl] = None

class ThreatFilterConfig(BaseModel):
    enabled: bool = True
    toxicity_threshold: float = 0.75

class AsicServiceConfig(BaseModel):
    update_interval_hours: int = 6
    fallback_file_path: str = "data/fallback_asics.json"

# --- Главная модель настроек ---

class Settings(BaseSettings):
    """
    Главный класс настроек. Pydantic автоматически загружает данные
    из переменных окружения. Остальные настройки подтягиваются из JSON.
    """
    # 1. Поля из ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (префикс не нужен)
    BOT_TOKEN: SecretStr
    ADMIN_USER_IDS: List[int]
    REDIS_URL: RedisDsn
    GEMINI_API_KEY: SecretStr
    ADMIN_CHAT_ID: Optional[int] = None
    NEWS_CHAT_ID: Optional[int] = None
    
    # Необязательные ключи API
    OPENAI_API_KEY: Optional[SecretStr] = None
    CRYPTOCOMPARE_API_KEY: Optional[SecretStr] = None
    PERSPECTIVE_API_KEY: Optional[SecretStr] = None

    # 2. Вложенные конфигурации, загружаемые из JSON-файлов
    log_level: str = "INFO"
    ai: AIConfig = Field(default_factory=AIConfig)
    throttling: ThrottlingConfig = Field(default_factory=ThrottlingConfig)
    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags)
    price_service: PriceServiceConfig = Field(default_factory=PriceServiceConfig)
    coin_list_service: CoinListServiceConfig = Field(default_factory=CoinListServiceConfig)
    news_service: NewsServiceConfig = Field(default_factory=NewsServiceConfig)
    endpoints: EndpointsConfig = Field(default_factory=EndpointsConfig)
    threat_filter: ThreatFilterConfig = Field(default_factory=ThreatFilterConfig)
    asic_service: AsicServiceConfig = Field(default_factory=AsicServiceConfig)
    
    # Модель конфигурации для pydantic-settings
    model_config = SettingsConfigDict(
        env_file='.env', 
        env_file_encoding='utf-8', 
        extra='ignore'
    )

    @field_validator('ADMIN_USER_IDS', mode='before')
    @classmethod
    def parse_admin_ids(cls, v: Any) -> List[int]:
        """Парсит ID администраторов из строки с запятыми."""
        if isinstance(v, str):
            return [int(item.strip()) for item in v.split(',') if item.strip()]
        if isinstance(v, list):
            return v
        raise ValueError("ADMIN_USER_IDS должен быть строкой с ID через запятую или списком чисел.")

def _load_json_config_data() -> Dict[str, Any]:
    """Вспомогательная функция для загрузки всех JSON-конфигов в один словарь."""
    base_dir = Path("data")
    config_files = {
        "throttling": "throttling_config.json",
        "feature_flags": "feature_flags.json",
        "endpoints": "endpoints_config.json",
        "price_service": "price_service_config.json",
        "coin_list_service": "coin_list_config.json",
        "ai": "ai_config.json",
        "news_service": "news_service_config.json",
        "threat_filter": "threat_filter_config.json",
        "asic_service": "asic_service_config.json",
        "app": "app_config.json", # Для log_level
    }
    
    loaded_data = {}
    for key, filename in config_files.items():
        path = base_dir / filename
        if not path.exists():
            logger.warning(f"Файл конфигурации не найден: {path}, будут использованы значения по умолчанию.")
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                json_content = json.load(f)
                if key == "app": # Особый случай для log_level
                    if "log_level" in json_content:
                        loaded_data["log_level"] = json_content["log_level"]
                else:
                    loaded_data[key] = json_content
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Не удалось прочитать или декодировать JSON {path}: {e}")
            raise SystemExit(f"Критическая ошибка конфигурации в файле: {path.name}")

    # Обработка вложенных конфигов, как в оригинале
    news_feeds_path = base_dir / "news_feeds.json"
    if news_feeds_path.exists():
        feeds_data = json.loads(news_feeds_path.read_text(encoding='utf-8'))
        if "news_service" not in loaded_data:
            loaded_data["news_service"] = {}
        loaded_data["news_service"]["feeds"] = feeds_data
        
    return loaded_data

def load_settings() -> Settings:
    """
    Главная функция для создания объекта настроек.
    1. Загружает переменные окружения (автоматически через Pydantic).
    2. Загружает данные из JSON-файлов.
    3. Объединяет все в единый объект `Settings`.
    """
    logger.info("Загрузка и валидация конфигураций...")
    json_data = _load_json_config_data()
    
    try:
        settings_instance = Settings(**json_data)
        logger.info("Все конфигурации успешно загружены и валидированы.")
        return settings_instance
    except ValidationError as e:
        logger.critical(f"Критическая ошибка валидации настроек. Проверьте .env и *.json файлы.\n{e}")
        raise SystemExit("Ошибки валидации конфигурации.")

# Создаем единственный глобальный экземпляр настроек для всего приложения
settings: Settings = load_settings()
