# ===============================================================
# Файл: bot/config/settings.py (ПРОДАКШН-ВЕРСИЯ 2025 - ОКОНЧАТЕЛЬНАЯ v11)
# ===============================================================
import json
import logging
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Literal, Optional

from pydantic import Field, model_validator, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger(__name__)

def load_json_data(filename: str, default: Any = None) -> Any:
    file_path = BASE_DIR / "data" / filename
    if not file_path.exists():
        logger.warning(f"Файл с данными не найден: {file_path}. Используется значение по умолчанию.")
        return default or {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки данных из {file_path}: {e}")
        return default or {}

class ApiKeysConfig(BaseSettings):
    bot_token: str = Field(..., alias='BOT_TOKEN')
    redis_url: str = Field(..., alias='REDIS_URL')
    gemini_api_key: str = Field(..., alias='GEMINI_API_KEY')
    cryptocompare_api_key: Optional[str] = Field(None, alias='CRYPTOCOMPARE_API_KEY')
    model_config = SettingsConfigDict(extra='ignore', env_file=".env", env_file_encoding="utf-8")

class AdminConfig(BaseSettings):
    admin_chat_id: int = Field(..., alias='ADMIN_CHAT_ID')
    news_chat_id: int = Field(..., alias='NEWS_CHAT_ID')
    super_admin_ids: List[int] = Field(default=[], alias='SUPER_ADMIN_IDS')
    admin_ids: List[int] = Field(default=[], alias='ADMIN_IDS')
    moderator_ids: List[int] = Field(default=[], alias='MODERATOR_IDS')
    @model_validator(mode='before')
    def parse_admin_ids(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        for key in ['SUPER_ADMIN_IDS', 'ADMIN_IDS', 'MODERATOR_IDS']:
            if isinstance(values.get(key), str):
                values[key] = [int(i.strip()) for i in values[key].split(',') if i.strip()]
        return values
    model_config = SettingsConfigDict(extra='ignore', env_file=".env", env_file_encoding="utf-8")

class EndpointsConfig(BaseModel):
    coingecko_api_base: str = "https://api.coingecko.com/api/v3"
    cryptocompare_api_base: str = "https://min-api.cryptocompare.com"
    fear_and_greed_api_url: str = "https://api.alternative.me/fng/?limit=1"
    btc_halving_url: str = "https://api.blockchair.com/bitcoin/stats"
    btc_network_status_url: str = "https://api.blockchair.com/bitcoin/stats"
    btc_fees_url: str = "https://mempool.space/api/v1/fees/recommended"
    crypto_center_news_api_url: str = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories=Airdrop,Mining,DeFi,L1,L2,Altcoin,RWA,GameFi"

class NewsConfig(BaseModel):
    main_rss_feeds: List[str]
    alpha_rss_feeds: List[str]

class NewsServiceConfig(BaseModel):
    news_limit_per_source: int = 5
    deduplication_ttl_seconds: int = 86400

class ElectricityTariffEnum(str, Enum):
    HOME = "Домашний 💡"
    INDUSTRIAL = "Промышленный 🏭"
    HYDRO = "Гидроэлектростанция 💧"

class TariffInfo(BaseModel):
    cost_per_hour: float
    unlock_price: int

class GameConfig(BaseModel):
    mining_duration_seconds: int = 8 * 3600
    referral_bonus_amount: float = 50.0
    min_withdrawal_amount: int = 1000
    electricity_tariffs: Dict[ElectricityTariffEnum, TariffInfo]
    default_electricity_tariff: ElectricityTariffEnum = ElectricityTariffEnum.HOME

class FeatureFlags(BaseModel):
    enable_ai_consultant: bool = True
    enable_crypto_center: bool = True
    enable_mining_game: bool = True

class SchedulerSettings(BaseSettings):
    asic_update_hours: int = 4
    news_interval_hours: int = 3
    morning_summary_hour: int = 9
    leaderboard_day: Literal['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] = Field('fri', alias='LEADERBOARD_DAY_OF_WEEK')
    leaderboard_hour: int = 18
    model_config = SettingsConfigDict(extra='ignore', env_file=".env", env_file_encoding="utf-8")

class AppConfig(BaseModel):
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    ai_history_limit: int = 10

class AIConfig(BaseModel):
    default_model_name: str = "gemini-1.5-pro-latest"
    flash_model_name: str = "gemini-1.5-flash-latest"
    max_retries: int = 3
    default_temperature: float = 0.6

class AsicServiceConfig(BaseModel):
    merge_score_cutoff: int = 85
    enrich_score_cutoff: int = 90
    search_score_cutoff: int = 80

class ThrottlingConfig(BaseModel):
    trust_score_high_threshold: int = 150
    trust_score_low_threshold: int = 50
    rate_limit_high_trust: float = 0.5
    rate_limit_normal: float = 1.0
    rate_limit_low_trust: float = 2.5

class ThreatFilterConfig(BaseModel):
    min_trigger_score: int = 80
    low_trust_multiplier: float = 1.5
    scores: Dict[str, int] = {}

class CoinListServiceConfig(BaseModel):
    search_score_cutoff: int = 85

class PriceServiceConfig(BaseModel):
    cache_ttl_seconds: int = 120

class MarketDataServiceConfig(BaseModel):
    fng_cache_ttl_seconds: int = 14400
    halving_cache_ttl_seconds: int = 3600
    network_status_cache_ttl_seconds: int = 120

class CryptoCenterServiceConfig(BaseModel):
    alpha_cache_ttl_seconds: int = 14400
    feed_cache_ttl_seconds: int = 900
    news_context_limit: int = 20

class AppSettings(BaseSettings):
    api_keys: ApiKeysConfig = Field(default_factory=ApiKeysConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    endpoints: EndpointsConfig
    news: NewsConfig
    news_service: NewsServiceConfig
    game: GameConfig
    feature_flags: FeatureFlags
    app: AppConfig
    ai: AIConfig
    asic_service: AsicServiceConfig
    throttling: ThrottlingConfig
    threat_filter: ThreatFilterConfig
    coin_list_service: CoinListServiceConfig
    price_service: PriceServiceConfig
    market_data_service: MarketDataServiceConfig
    crypto_center_service: CryptoCenterServiceConfig
    ticker_aliases: Dict[str, str]
    fallback_asics: List[Dict[str, Any]]
    fallback_quiz: List[Dict[str, Any]]

    @model_validator(mode='before')
    def load_configs_from_files(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values['endpoints'] = load_json_data("endpoints.json", EndpointsConfig().model_dump())
        values['news'] = load_json_data("news_feeds.json", {"main_rss_feeds": [], "alpha_rss_feeds": []})
        values['news_service'] = load_json_data("news_service_config.json", NewsServiceConfig().model_dump())
        values['game'] = load_json_data("game_config.json")
        values['feature_flags'] = load_json_data("feature_flags.json", FeatureFlags().model_dump())
        values['app'] = load_json_data("app_config.json", AppConfig().model_dump())
        values['ai'] = load_json_data("ai_config.json", AIConfig().model_dump())
        values['asic_service'] = load_json_data("asic_service_config.json", AsicServiceConfig().model_dump())
        values['throttling'] = load_json_data("throttling_config.json", ThrottlingConfig().model_dump())
        values['threat_filter'] = load_json_data("threat_filter_config.json", ThreatFilterConfig().model_dump())
        values['coin_list_service'] = load_json_data("coin_list_config.json", CoinListServiceConfig().model_dump())
        values['price_service'] = load_json_data("price_service_config.json", PriceServiceConfig().model_dump())
        values['market_data_service'] = load_json_data("market_data_config.json", MarketDataServiceConfig().model_dump())
        values['crypto_center_service'] = load_json_data("crypto_center_config.json", CryptoCenterServiceConfig().model_dump())
        values['ticker_aliases'] = load_json_data("ticker_aliases.json")
        values['fallback_asics'] = load_json_data("fallback_asics.json", [])
        values['fallback_quiz'] = load_json_data("fallback_quiz.json", [])
        return values
    model_config = SettingsConfigDict(env_nested_delimiter='__', case_sensitive=False)

settings = AppSettings()
