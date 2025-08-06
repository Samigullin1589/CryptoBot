# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ ПОЛНАЯ)
# Описание: Единая, строго типизированная и самодостаточная система конфигурации.
# ИСПРАВЛЕНИЕ: Добавлены поля для AsicService.
# =================================================================================

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger
from dotenv import load_dotenv
from pydantic import (BaseModel, Field, RedisDsn, HttpUrl, SecretStr,
                      ValidationError, field_validator, ConfigDict)
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

# --- Определения моделей для всех частей конфигурации ---

class AIConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    provider: str = "gemini"
    model_name: str = "gemini-1.5-pro-latest"
    flash_model_name: str = "gemini-1.5-flash-latest"
    default_temperature: float = 0.5
    max_retries: int = 5

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
    default_vs_currency: str = "usd"

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
    news_limit_per_source: int = 5

class EndpointsConfig(BaseModel):
    coingecko_api_base: HttpUrl = "https://api.coingecko.com/api/v3"
    coins_list_endpoint: str = "/coins/list"
    coins_markets_endpoint: str = "/coins/markets"
    simple_price_endpoint: str = "/simple/price"
    blockchain_info_hashrate: HttpUrl = "https://api.blockchain.info/q/hashrate"
    mempool_space_difficulty: HttpUrl = "https://mempool.space/api/v1/difficulty-adjustment"
    whattomine_api: Optional[HttpUrl] = "https://whattomine.com/asics.json"
    asicminervalue_url: Optional[HttpUrl] = "https://www.asicminervalue.com/"
    minerstat_api: Optional[HttpUrl] = "https://api.minerstat.com/v2"
    cryptocompare_news_api_url: Optional[HttpUrl] = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"

class ThreatFilterConfig(BaseModel):
    enabled: bool = True
    toxicity_threshold: float = 0.75

# ИСПРАВЛЕНО: Добавлены пороговые значения для нечеткого поиска
class AsicServiceConfig(BaseModel):
    update_interval_hours: int = 6
    fallback_file_path: str = "data/fallback_asics.json"
    merge_score_cutoff: int = 90
    enrich_score_cutoff: int = 95

class CryptoCenterServiceConfig(BaseModel):
    news_context_limit: int = 20
    alpha_cache_ttl_seconds: int = 1800
    feed_cache_ttl_seconds: int = 600

class QuizServiceConfig(BaseModel):
    fallback_questions_path: str = "data/quiz_fallback.json"

class MiningEventServiceConfig(BaseModel):
    config_path: str = "data/events_config.json"
    default_multiplier: float = 1.0

class AchievementServiceConfig(BaseModel):
    config_path: str = "data/achievements.json"

class MarketDataServiceConfig(BaseModel):
    update_interval_seconds: int = 60
    top_n_coins: int = 100
    default_vs_currency: str = "usd"

class MiningGameServiceConfig(BaseModel):
    session_duration_minutes: int = 60

# --- Главная модель настроек ---

class Settings(BaseSettings):
    BOT_TOKEN: SecretStr
    ADMIN_USER_IDS: Any
    REDIS_URL: RedisDsn
    GEMINI_API_KEY: SecretStr
    ADMIN_CHAT_ID: Optional[int] = None
    NEWS_CHAT_ID: Optional[int] = None
    OPENAI_API_KEY: Optional[SecretStr] = None
    CRYPTOCOMPARE_API_KEY: Optional[SecretStr] = None
    PERSPECTIVE_API_KEY: Optional[SecretStr] = None

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
    crypto_center: CryptoCenterServiceConfig = Field(default_factory=CryptoCenterServiceConfig)
    quiz: QuizServiceConfig = Field(default_factory=QuizServiceConfig)
    events: MiningEventServiceConfig = Field(default_factory=MiningEventServiceConfig)
    achievements: AchievementServiceConfig = Field(default_factory=AchievementServiceConfig)
    market_data: MarketDataServiceConfig = Field(default_factory=MarketDataServiceConfig)
    game: MiningGameServiceConfig = Field(default_factory=MiningGameServiceConfig)
    
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    @field_validator('ADMIN_USER_IDS', mode='before')
    @classmethod
    def parse_admin_ids(cls, v: Any) -> List[int]:
        if isinstance(v, str):
            return [int(item.strip()) for item in v.split(',') if item.strip()]
        if isinstance(v, list):
            return v
        raise ValueError("ADMIN_USER_IDS должен быть строкой с ID через запятую или списком чисел.")

def _load_json_config_data() -> Dict[str, Any]:
    base_dir = Path("data")
    config_files = { "app": "app_config.json", "throttling": "throttling_config.json", "feature_flags": "feature_flags.json", "endpoints": "endpoints_config.json", "price_service": "price_service_config.json", "coin_list_service": "coin_list_config.json", "ai": "ai_config.json", "news_service": "news_service_config.json", "threat_filter": "threat_filter_config.json", "asic_service": "asic_service_config.json", "crypto_center": "crypto_center_config.json", "quiz": "quiz_config.json", "events": "events_config.json", "achievements": "achievements_config.json", "market_data": "market_data_config.json", "game": "game_config.json" }
    loaded_data = {}
    for key, filename in config_files.items():
        path = base_dir / filename
        if not path.exists():
            logger.warning(f"Файл конфигурации не найден: {path}, будут использованы значения по умолчанию.")
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                json_content = json.load(f)
                if key == "app":
                    if "log_level" in json_content:
                        loaded_data["log_level"] = json_content["log_level"]
                else:
                    loaded_data[key] = json_content
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Не удалось прочитать или декодировать JSON {path}: {e}")
            raise SystemExit(f"Критическая ошибка конфигурации в файле: {path.name}")
    news_feeds_path = base_dir / "news_feeds.json"
    if news_feeds_path.exists():
        try:
            feeds_data = json.loads(news_feeds_path.read_text(encoding='utf-8'))
            if "news_service" not in loaded_data:
                loaded_data["news_service"] = {}
            loaded_data["news_service"]["feeds"] = feeds_data
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Не удалось обработать {news_feeds_path}: {e}")
    return loaded_data

def load_settings() -> Settings:
    logger.info("Загрузка и валидация конфигураций...")
    json_data = _load_json_config_data()
    try:
        settings_instance = Settings(**json_data)
        logger.info("Все конфигурации успешно загружены и валидированы.")
        return settings_instance
    except ValidationError as e:
        logger.critical(f"Критическая ошибка валидации настроек. Проверьте .env и *.json файлы.\n{e}")
        raise SystemExit("Ошибки валидации конфигурации.")

settings: Settings = load_settings()
