# =================================================================================
# Файл: bot/config/settings.py (ФИНАЛЬНАЯ ВЕРСИЯ - С РАБОЧИМИ RSS И РЕЗЕРВНЫМ API)
# Описание: Единая, строго типизированная система конфигурации.
# ИСПРАВЛЕНИЕ: Обновлены RSS-ленты, добавлен CryptoCompare как резервный API.
# =================================================================================

import logging
from typing import List, Dict, Any, Optional

from pydantic import (BaseModel, Field, RedisDsn, HttpUrl, SecretStr,
                      ValidationError, field_validator, ConfigDict)
from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Вложенные модели ---

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
    search_score_cutoff: int = 85

class NewsFeeds(BaseModel):
    # ИСПРАВЛЕНО: Заменены неработающие RSS-ссылки на актуальные
    main_rss_feeds: List[HttpUrl] = [
        "https://forklog.com/feed",
        "https://getblock.net/news/rss/", # Замена для Bits.media
        "https://www.rbc.ru/crypto/feed"   # Замена для РБК
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


class ThreatFilterConfig(BaseModel):
    enabled: bool = True
    toxicity_threshold: float = 0.75

class AsicServiceConfig(BaseModel):
    update_interval_hours: int = 6
    fallback_file_path: str = "data/fallback_asics.json"
    merge_score_cutoff: int = 90
    enrich_score_cutoff: int = 95

class CryptoCenterServiceConfig(BaseModel):
    news_context_limit: int