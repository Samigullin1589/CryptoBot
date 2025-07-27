# ===============================================================
# Файл: bot/config/settings.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Центральный файл конфигурации. Использует Pydantic
# для строгой типизации и валидации настроек из .env файла.
# Разделен на логические блоки для чистоты и масштабируемости.
# ===============================================================
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем базовую директорию проекта
BASE_DIR = Path(__file__).parent.parent.parent

def load_fallback_asics() -> List[Dict[str, Any]]:
    """Загружает резервный список ASIC'ов из data/fallback_asics.json."""
    file_path = BASE_DIR / "data" / "fallback_asics.json"
    if not file_path.exists():
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- Вложенные конфигурационные модели ---

class AppConfig(BaseSettings):
    """Общие настройки приложения."""
    log_level: str = "INFO"
    log_format: str = "text"  # "text" или "json"
    ticker_aliases: Dict[str, str] = {
        'бтк': 'BTC', 'биткоин': 'BTC', 'биток': 'BTC', 'eth': 'ETH', 'эфир': 'ETH', 'эфириум': 'ETH'
    }
    popular_tickers: List[str] = ['BTC', 'ETH', 'SOL', 'TON', 'KAS', 'ARB']

class ApiKeysConfig(BaseSettings):
    """Секретные ключи и ID."""
    bot_token: str
    redis_url: str
    admin_chat_id: int
    news_chat_id: Optional[int] = None
    admin_user_ids_str: str = Field(alias='ADMIN_USER_IDS', default='')
    super_admin_user_ids_str: str = Field(alias='SUPER_ADMIN_USER_IDS', default='')
    moderator_user_ids_str: str = Field(alias='MODERATOR_USER_IDS', default='')
    
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    cmc_api_key: Optional[str] = None
    cryptocompare_api_key: Optional[str] = None

class ApiEndpointsConfig(BaseSettings):
    """URL-адреса внешних API."""
    coingecko_api_base: str = "https://api.coingecko.com/api/v3"
    minerstat_api_base: str = "https://api.minerstat.com/v2"
    whattomine_asics_url: str = "https://whattomine.com/coins.json"
    asicminervalue_url: str = "https://www.asicminervalue.com/miners"
    fear_and_greed_api_url: str = "https://api.alternative.me/fng/?limit=1"
    
    # Основные и резервные эндпоинты
    btc_fees_url: str = "https://mempool.space/api/v1/fees/recommended"
    btc_fees_fallback_url: str = "https://api.blockcypher.com/v1/btc/main"
    mempool_stats_url: str = "https://mempool.space/api/mempool"
    mempool_stats_fallback_url: str = "https://api.blockchain.info/charts/mempool-count?format=json"

class NewsConfig(BaseSettings):
    """Настройки для новостных модулей."""
    rss_feeds: List[str] = [
        "https://forklog.com/feed",
        "https://beincrypto.ru/feed/",
        "https://cointelegraph.com/rss/tag/russia",
        "https://www.theblock.co/rss.xml", # L2, DeFi
        "https://thedefiant.io/feed"      # Web3
    ]

class MiningGameConfig(BaseSettings):
    """Настройки для игры 'Виртуальный Майнинг'."""
    session_duration_seconds: int = 8 * 3600  # 8 часов
    referral_bonus_amount: float = 50.0
    electricity_tariffs: Dict[str, Dict[str, float]] = {
        "Домашний 💡": {"cost_per_hour": 0.05, "unlock_price": 0},
        "Промышленный 🏭": {"cost_per_hour": 0.02, "unlock_price": 200},
        "Гидроэлектростанция 💧": {"cost_per_hour": 0.01, "unlock_price": 500}
    }
    default_electricity_tariff: str = "Домашний 💡"

class CryptoCenterConfig(BaseSettings):
    """Настройки для Крипто-Центра."""
    news_api_url: str = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories=Airdrop,Mining,DeFi,L1,L2,Altcoin,RWA,GameFi"
    alpha_rss_feeds: List[str] = [
        "https://thedefiant.io/feed",
        "https://bankless.substack.com/feed",
    ]

class ModerationConfig(BaseSettings):
    """Настройки для модерации и анти-спама."""
    allowed_link_user_ids: List[int] = []

class SchedulerSettings(BaseSettings):
    """Настройки для планировщика задач."""
    asic_update_hours: int = 1
    news_interval_hours: int = 3
    morning_summary_hour: int = 9
    # --- ИСПРАВЛЕНИЕ: Переименовываем поле для соответствия ---
    leaderboard_day: str = Field(default='fri', alias='leaderboard_day_of_week')
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
    leaderboard_hour: int = 18
    health_check_minutes: int = 5

class ThrottlingSettings(BaseSettings):
    """Настройки для анти-флуд системы."""
    default_rate_limit: float = 1.0
    trusted_rate_limit: float = 0.5
    low_trust_rate_limit: float = 2.5
    trusted_user_threshold: int = 150
    low_trust_user_threshold: int = 50

class ActivitySettings(BaseSettings):
    """Настройки для отслеживания активности."""
    throttle_seconds: int = 60
    reward_threshold: int = 50
    reward_points: int = 5

class PriceServiceSettings(BaseSettings):
    """Настройки для сервиса цен."""
    cache_ttl: int = 120
    not_found_cache_ttl: int = 300

class AsicServiceSettings(BaseSettings):
    """Настройки для сервиса ASIC'ов."""
    cache_ttl: int = 3600
    specs_cache_ttl: int = 3600 * 6
    fuzzy_score_cutoff: int = 90

class SecurityServiceSettings(BaseSettings):
    """Настройки для сервиса безопасности."""
    cache_ttl: int = 300
    backoff_max_tries: int = 3

class AIContentServiceSettings(BaseSettings):
    """Настройки для сервиса генерации контента."""
    backoff_max_tries: int = 3
    timeout: int = 90
    model: str = "gemini-1.5-pro-latest"

# --- Основной класс настроек ---

class AppSettings(BaseSettings):
    """Главный класс, объединяющий все конфигурации."""
    app: AppConfig = AppConfig()
    api_keys: ApiKeysConfig = ApiKeysConfig()
    api_endpoints: ApiEndpointsConfig = ApiEndpointsConfig()
    news: NewsConfig = NewsConfig()
    game: MiningGameConfig = MiningGameConfig()
    crypto_center: CryptoCenterConfig = CryptoCenterConfig()
    moderation: ModerationConfig = ModerationConfig()
    scheduler: SchedulerSettings = SchedulerSettings()
    throttling: ThrottlingSettings = ThrottlingSettings()
    activity: ActivitySettings = ActivitySettings()
    price_service: PriceServiceSettings = PriceServiceSettings()
    asic_service: AsicServiceSettings = AsicServiceSettings()
    security_service: SecurityServiceSettings = SecurityServiceSettings()
    ai_content_service: AIContentServiceSettings = AIContentServiceSettings()
    
    fallback_asics: List[Dict[str, Any]] = Field(default_factory=load_fallback_asics, exclude=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter='__'
    )

    @staticmethod
    def _parse_user_ids(id_string: str) -> Set[int]:
        if not id_string.strip():
            return set()
        try:
            return {int(item.strip()) for item in id_string.split(',') if item.strip()}
        except (ValueError, TypeError):
            return set()

    @computed_field
    @property
    def ADMIN_USER_IDS(self) -> Set[int]:
        return self._parse_user_ids(self.api_keys.admin_user_ids_str)

    @computed_field
    @property
    def SUPER_ADMIN_USER_IDS(self) -> Set[int]:
        return self._parse_user_ids(self.api_keys.super_admin_user_ids_str)

    @computed_field
    @property
    def MODERATOR_USER_IDS(self) -> Set[int]:
        return self._parse_user_ids(self.api_keys.moderator_user_ids_str)

# Создаем единственный экземпляр настроек для всего приложения
settings = AppSettings()
