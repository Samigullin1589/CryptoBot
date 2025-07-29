# ===============================================================
# Файл: bot/config/settings.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Централизованная конфигурация всего приложения
# с использованием Pydantic для валидации и загрузки из .env.
# ===============================================================
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Конфигурационные классы для вложенных настроек ---

class ApiKeysConfig(BaseSettings):
    bot_token: str = Field(..., alias='BOT_TOKEN')
    redis_url: str = Field(..., alias='REDIS_URL')
    openai_api_key: str = Field("", alias='OPENAI_API_KEY')
    gemini_api_key: str = Field(..., alias='GEMINI_API_KEY')
    cmc_api_key: str = Field("", alias='CMC_API_KEY')
    cryptocompare_api_key: str = Field("", alias='CRYPTOCOMPARE_API_KEY')
    blockchair_api_key: str = Field("", alias='BLOCKCHAIR_API_KEY')
    glassnode_api_key: str = Field("", alias='GLASSNODE_API_KEY')

    model_config = SettingsConfigDict(extra='ignore')

class AdminConfig(BaseSettings):
    admin_chat_id: int = Field(..., alias='ADMIN_CHAT_ID')
    news_chat_id: int = Field(..., alias='NEWS_CHAT_ID')
    super_admin_ids_str: str = Field(alias='SUPER_ADMIN_IDS', default='')
    admin_ids_str: str = Field(alias='ADMIN_IDS', default='')
    moderator_ids_str: str = Field(alias='MODERATOR_IDS', default='')

    super_admin_ids: List[int] = []
    admin_ids: List[int] = []
    moderator_ids: List[int] = []
    
    @model_validator(mode='after')
    def parse_admin_ids(self) -> 'AdminConfig':
        self.super_admin_ids = [int(i.strip()) for i in self.super_admin_ids_str.split(',') if i.strip()]
        self.admin_ids = [int(i.strip()) for i in self.admin_ids_str.split(',') if i.strip()]
        self.moderator_ids = [int(i.strip()) for i in self.moderator_ids_str.split(',') if i.strip()]
        return self

    model_config = SettingsConfigDict(extra='ignore')

class EndpointsConfig(BaseSettings):
    coingecko_api_base: str = "https://api.coingecko.com/api/v3"
    coinpaprika_api_base: str = "https://api.coinpaprika.com/v1"
    cryptocompare_api_base: str = "https://min-api.cryptocompare.com"
    minerstat_api_base: str = "https://api.minerstat.com/v2"
    whattomine_asics_url: str = "https://whattomine.com/coins.json"
    asicminervalue_url: str = "https://www.asicminervalue.com/miners"
    fear_and_greed_api_url: str = "https://api.alternative.me/fng/?limit=1"
    
    btc_halving_url_primary: str = "https://api.blockchair.com/bitcoin/stats"
    btc_fees_url_primary: str = "https://mempool.space/api/v1/fees/recommended"
    btc_fees_url_fallback: str = "https://api.blockchair.com/bitcoin/stats"
    btc_network_status_url_primary: str = "https://api.blockchair.com/bitcoin/stats"

class NewsConfig(BaseSettings):
    main_rss_feeds: List[str] = [
        "https://forklog.com/feed", 
        "https://beincrypto.ru/feed/", 
        "https://cointelegraph.com/rss/tag/russia"
    ]
    alpha_rss_feeds: List[str] = [
        "https://thedefiant.io/feed",
        "https://bankless.substack.com/feed",
        "https://www.theblock.co/rss.xml"
    ]
    crypto_center_news_api_url: str = (
        "https://min-api.cryptocompare.com/data/v2/news/"
        "?lang=EN&categories=Airdrop,Mining,DeFi,L1,L2,Altcoin,RWA,GameFi"
    )

class GameConfig(BaseSettings):
    mining_duration_seconds: int = 8 * 3600
    referral_bonus_amount: float = 50.0
    electricity_tariffs: Dict[str, Dict[str, float]] = {
        "Домашний 💡": {"cost_per_hour": 0.05, "unlock_price": 0},
        "Промышленный 🏭": {"cost_per_hour": 0.02, "unlock_price": 200},
        "Гидроэлектростанция 💧": {"cost_per_hour": 0.01, "unlock_price": 500}
    }
    default_electricity_tariff: str = "Домашний 💡"

class FeatureFlags(BaseSettings):
    enable_ai_consultant: bool = True
    enable_crypto_center: bool = True
    enable_mining_game: bool = True

class ActivityRewards(BaseSettings):
    reward_threshold: int = 50
    reward_points: int = 5

class ThreatFilterSettings(BaseSettings):
    sandbox_period_seconds: int = 86400
    critical_confidence_threshold: float = 0.9
    low_trust_threshold: int = 50
    threat_scores: Dict[str, int] = {
        "scam": 90,
        "phishing": 100,
        "insult": 50,
        "has_link": 30,
        "stop_word": 25,
        "velocity_burst": 40
    }
    trust_discount_factor: float = 0.5
    low_trust_multiplier: float = 1.5

class SchedulerSettings(BaseSettings):
    news_interval_hours: int = 3
    asic_update_hours: int = 1
    morning_summary_hour: int = 9
    # --- ИСПРАВЛЕНИЕ: Переименовываем поле для соответствия ---
    leaderboard_day: str = Field('fri', alias='LEADERBOARD_DAY_OF_WEEK')
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
    leaderboard_hour: int = 18
    health_check_minutes: int = 5

class AppConfig(BaseSettings):
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    ai_history_limit: int = 10
    popular_tickers: List[str] = ['BTC', 'ETH', 'SOL', 'TON', 'KAS', 'ARB']

# --- Главный класс настроек, собирающий все вместе ---

class AppSettings(BaseSettings):
    api_keys: ApiKeysConfig = Field(default_factory=ApiKeysConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)
    endpoints: EndpointsConfig = Field(default_factory=EndpointsConfig)
    news: NewsConfig = Field(default_factory=NewsConfig)
    game: GameConfig = Field(default_factory=GameConfig)
    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags)
    activity_rewards: ActivityRewards = Field(default_factory=ActivityRewards)
    threat_filter: ThreatFilterSettings = Field(default_factory=ThreatFilterSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    app: AppConfig = Field(default_factory=AppConfig)

    fallback_asics: List[Dict[str, Any]] = []
    fallback_quiz: List[Dict[str, Any]] = []

    ticker_aliases: Dict[str, str] = {
        'бтк': 'BTC', 'биткоин': 'BTC', 'биток': 'BTC', 
        'eth': 'ETH', 'эфир': 'ETH', 'эфириум': 'ETH'
    }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter='__'
    )

# --- Создаем единственный экземпляр настроек ---
settings = AppSettings()

# --- Загрузка резервных данных ---
BASE_DIR = Path(__file__).parent.parent.parent
logger = logging.getLogger(__name__)

def load_fallback_data(filename: str) -> List[Dict[str, Any]]:
    file_path = BASE_DIR / "data" / filename
    if not file_path.exists():
        logger.error(f"Fallback data file not found: {file_path}")
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading fallback data from {file_path}: {e}")
        return []

settings.fallback_asics = load_fallback_data("fallback_asics.json")
settings.fallback_quiz = load_fallback_data("fallback_quiz.json")
