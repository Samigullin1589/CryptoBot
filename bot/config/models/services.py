# bot/config/models/services.py
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class PriceServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    cache_ttl_seconds: int = 90
    top_n_coins: int = 100
    default_vs_currency: str = "usd"


class CoinListServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    update_interval_hours: int = 24
    fallback_file_path: str = "data/fallback_coins.json"
    search_score_cutoff: int = 90


class NewsFeeds(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    main_rss_feeds: List[HttpUrl] = [
        "https://forklog.com/feed",
        "https://beincrypto.ru/feed/",
        "https://cointelegraph.com/rss",
    ]
    alpha_rss_feeds: List[HttpUrl] = []


class NewsServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    cache_ttl_seconds: int = 3600
    feeds: NewsFeeds = Field(default_factory=NewsFeeds)
    news_limit_per_source: int = 5


class EndpointsConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    coingecko_api_base: HttpUrl = "https://api.coingecko.com/api/v3"
    coingecko_api_pro_base: HttpUrl = "https://pro-api.coingecko.com/api/v3"
    cryptocompare_api_base: HttpUrl = "https://min-api.cryptocompare.com"
    cryptocompare_price_endpoint: str = "/data/pricemulti"

    coins_list_endpoint: str = "/coins/list"
    coins_markets_endpoint: str = "/coins/markets"
    simple_price_endpoint: str = "/simple/price"

    fear_and_greed_api: HttpUrl = "https://api.alternative.me/fng/"
    mempool_space_difficulty: HttpUrl = "https://mempool.space/api/v1/difficulty-adjustment"
    mempool_space_tip_height: HttpUrl = "https://mempool.space/api/blocks/tip/height"
    blockchain_info_hashrate: HttpUrl = "https://blockchain.info/q/hashrate"

    whattomine_api: Optional[HttpUrl] = "https://whattomine.com/asics.json"
    asicminervalue_url: Optional[HttpUrl] = "https://www.asicminervalue.com/"
    minerstat_api: Optional[HttpUrl] = "https://api.minerstat.com/v2"

    currency_rate_api: Optional[HttpUrl] = "https://api.exchangerate-api.com/v4/latest/USD"


class AsicServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    update_interval_hours: int = 6
    fallback_file_path: str = "data/fallback_asics.json"
    merge_score_cutoff: int = 90
    enrich_score_cutoff: int = 95
    cache_ttl_seconds: int = 21600


class CryptoCenterServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    news_context_limit: int = 20
    alpha_cache_ttl_seconds: int = 1800
    feed_cache_ttl_seconds: int = 600


class QuizServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    fallback_questions_path: str = "data/quiz_fallback.json"


class MiningEventServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    config_path: str = "data/events_config.json"
    default_multiplier: float = 1.0


class AchievementServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    config_path: str = "data/achievements.json"


class MarketDataServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    update_interval_seconds: int = 60
    top_n_coins: int = 100
    default_vs_currency: str = "usd"
    primary_provider: str = "cryptocompare"
    fallback_provider: str = "coingecko"


class ElectricityTariff(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    cost_per_kwh: float
    unlock_price: float


class MiningGameServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    session_duration_minutes: int = 60
    market_commission_rate: float = 0.05
    min_withdrawal_amount: float = 1000.0

    default_electricity_tariff: str = "Бытовой"

    electricity_tariffs: Dict[str, ElectricityTariff] = Field(
        default_factory=lambda: {
            "Бытовой": {"cost_per_kwh": 0.10, "unlock_price": 0},
            "Промышленный": {"cost_per_kwh": 0.07, "unlock_price": 5_000},
            "Зеленый": {"cost_per_kwh": 0.05, "unlock_price": 25_000},
        }
    )