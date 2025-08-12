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