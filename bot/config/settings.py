# =================================================================================
# Файл: bot/config/settings.py (ФИНАЛЬНАЯ ВЕРСИЯ - ЕДИНЫЙ ИСТОЧНИК)
# Описание: Единая, строго типизированная система конфигурации.
#           Определяет Pydantic-модели и создает единственный
#           экземпляр (singleton) настроек для всего приложения.
# ИСПРАВЛЕНИЕ: Объединены файлы settings.py и config.py для устранения
#              циклических импортов.
# =================================================================================

import logging
from typing import List, Dict, Any, Optional
from pydantic import (BaseModel, Field, RedisDsn, HttpUrl, SecretStr,
                      ValidationError, field_validator, ConfigDict)
from pydantic_settings import BaseSettings, SettingsConfigDict

class AIConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    provider: str = "gemini"
    model_name: str = "gemini-1.5-pro-latest"
    flash_model_name: str = "gemini-1.5-flash-latest"
    default_temperature: float = 0.5
    max_retries: int = 5
    history_max_size: int = 10

class ThrottlingConfig(BaseModel):
    user_rate_limit: float = 2.0
    chat_rate_limit: float = 1.0
    key_prefix: str = "throttling"

class FeatureFlags(BaseModel):
    maintenance_mode: bool = False
    enable_game: bool = True
    enable_threat_protection: bool = True

class PriceServiceConfig(BaseModel):
    cache_ttl_seconds: int = 90
    top_n_coins: int = 100
    default_vs_currency: str = "usd"

class CoinListServiceConfig(BaseModel):
    update_interval_hours: int = 24
    fallback_file_path: str = "data/fallback_coins.json"
    search_score_cutoff: int = 90

class NewsFeeds(BaseModel):
    main_rss_feeds: List[HttpUrl] = [
        "https://forklog.com/feed",
        "https://beincrypto.ru/feed/",
        "https://cointelegraph.com/rss"
    ]
    alpha_rss_feeds: List[HttpUrl] = []

class NewsServiceConfig(BaseModel):
    cache_ttl_seconds: int = 3600
    feeds: NewsFeeds = Field(default_factory=NewsFeeds)
    news_limit_per_source: int = 5

class EndpointsConfig(BaseModel):
    coingecko_api_base: HttpUrl = "https://api.coingecko.com/api/v3"
    coingecko_api_pro_base: HttpUrl = "https://pro-api.coingecko.com/api/v3"
    cryptocompare_api_base: HttpUrl = "https://min-api.cryptocompare.com"
    cryptocompare_price_endpoint: str = "/data/pricemulti"
    coins_list_endpoint: str = "/coins/list"
    coins_markets_endpoint: str = "/coins/markets"
    simple_price_endpoint: str = "/simple/price"
    fear_and_greed_api: HttpUrl = "https://api.alternative.me/fng/"
    mempool_space_difficulty: HttpUrl = "https://mempool.space/api/v1/difficulty-adjustment"
    blockchain_info_hashrate: HttpUrl = "https://blockchain.info/q/hashrate"
    whattomine_api: Optional[HttpUrl] = "https://whattomine.com/asics.json"
    asicminervalue_url: Optional[HttpUrl] = "https://www.asicminervalue.com/"
    minerstat_api: Optional[HttpUrl] = "https://api.minerstat.com/v2"

class ThreatFilterConfig(BaseModel):
    enabled: bool = True
    toxicity_threshold: float = 0.75

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
    primary_provider: str = "cryptocompare"
    fallback_provider: str = "coingecko"

class ElectricityTariff(BaseModel):
    cost_per_kwh: float
    unlock_price: float

class MiningGameServiceConfig(BaseModel):
    session_duration_minutes: int = 60
    market_commission_rate: float = 0.05
    min_withdrawal_amount: float = 1000.0
    default_electricity_tariff: str = "Бытовой"
    electricity_tariffs: Dict[str, ElectricityTariff] = {
        "Бытовой": {"cost_per_kwh": 0.1, "unlock_price": 0},
        "Промышленный": {"cost_per_kwh": 0.07, "unlock_price": 5000},
        "Зеленый": {"cost_per_kwh": 0.05, "unlock_price": 25000},
    }

class Settings(BaseSettings):
    BOT_TOKEN: SecretStr
    admin_ids: Any = Field(alias="ADMIN_USER_IDS")
    REDIS_URL: RedisDsn
    GEMINI_API_KEY: SecretStr
    COINGECKO_API_KEY: Optional[SecretStr] = None
    CRYPTOCOMPARE_API_KEY: Optional[SecretStr] = None
    ADMIN_CHAT_ID: Optional[int] = None
    NEWS_CHAT_ID: Optional[int] = None
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
    
    @field_validator('admin_ids', mode='before')
    @classmethod
    def parse_admin_ids(cls, v: Any) -> List[int]:
        if isinstance(v, list): return v
        if isinstance(v, str):
            if not v: return []
            return [int(item.strip()) for item in v.split(',') if item.strip()]
        raise TypeError("ADMIN_USER_IDS должен быть строкой с ID через запятую.")

    model_config = SettingsConfigDict(
        env_file='.env', 
        env_file_encoding='utf-8', 
        extra='ignore',
        env_nested_delimiter='__'
    )

# --- СОЗДАНИЕ ЕДИНСТВЕННОГО ЭКЗЕМПЛЯРА НАСТРОЕК ---
try:
    settings = Settings()
    logging.info("Конфигурация успешно загружена и валидирована.")
except ValidationError as e:
    logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА ВАЛИДАЦИИ НАСТРОЕК. Проверьте ваш .env файл и переменные окружения.\n{e}")
    raise SystemExit("Ошибки валидации конфигурации.")