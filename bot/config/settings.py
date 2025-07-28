# ===============================================================
# Файл: bot/config/settings.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Центральный файл для управления всеми настройками
# и секретами бота с использованием Pydantic.
# ===============================================================

import json
from pathlib import Path
from typing import List, Dict, Any, Set

from pydantic import Field, model_validator, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем базовую директорию проекта (корень)
BASE_DIR = Path(__file__).parent.parent.parent

# --- Вложенные классы конфигурации для лучшей организации ---

class ApiKeysConfig(BaseSettings):
    """Секретные ключи для доступа к внешним API."""
    bot_token: str = Field(alias='BOT_TOKEN')
    redis_url: str = Field(alias='REDIS_URL')
    openai_api_key: str = Field(alias='OPENAI_API_KEY', default="")
    gemini_api_key: str = Field(alias='GEMINI_API_KEY')
    cmc_api_key: str = Field(alias='CMC_API_KEY', default="")
    cryptocompare_api_key: str = Field(alias='CRYPTOCOMPARE_API_KEY', default="")
    blockchair_api_key: str = Field(alias='BLOCKCHAIR_API_KEY', default="")
    glassnode_api_key: str = Field(alias='GLASSNODE_API_KEY', default="")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore' # Игнорировать лишние переменные окружения
    )

class AdminConfig(BaseModel):
    """Настройки, связанные с администрированием."""
    admin_chat_id: int
    news_chat_id: int
    admin_user_ids_str: str = Field(alias='ADMIN_USER_IDS', default='')

    @property
    def admin_user_ids(self) -> List[int]:
        if not self.admin_user_ids_str.strip():
            return []
        try:
            return [int(item.strip()) for item in self.admin_user_ids_str.split(',') if item.strip()]
        except (ValueError, TypeError):
            return []

class ApiEndpoints(BaseModel):
    """URL-адреса для внешних API."""
    coingecko_api_base: str = "https://api.coingecko.com/api/v3"
    coinpaprika_api_base: str = "https://api.coinpaprika.com/v1"
    cryptocompare_api_base: str = "https://min-api.cryptocompare.com"
    minerstat_api_base: str = "https://api.minerstat.com/v2"
    blockchair_api_base: str = "https://api.blockchair.com"
    
    # Основные и резервные эндпоинты
    fear_and_greed_api_url: str = "https://api.alternative.me/fng/?limit=1"
    cbr_daily_json_url: str = "https://www.cbr-xml-daily.ru/daily_json.js"
    btc_fees_url: str = "https://mempool.space/api/v1/fees/recommended"
    btc_fees_fallback_url: str = "https://blockstream.info/api/fee-estimates"
    btc_mempool_url: str = "https://mempool.space/api/mempool"
    btc_mempool_fallback_url: str = "https://blockstream.info/api/mempool"

class NewsConfig(BaseModel):
    """Настройки для новостных модулей."""
    # Основные новостные ленты
    main_rss_feeds: List[str] = [
        "https://forklog.com/feed",
        "https://beincrypto.ru/feed/",
        "https://cointelegraph.com/rss/tag/russia"
    ]
    # "Альфа" ленты для AI-анализа
    alpha_rss_feeds: List[str] = [
        "https://thedefiant.io/feed",
        "https://bankless.substack.com/feed",
        "https://www.theblock.co/rss.xml",
        "https://cointelegraph.com/rss/tag/layer-2"
    ]
    # Категории для API CryptoCompare
    crypto_center_news_categories: str = "Airdrop,Mining,DeFi,L1,L2,Altcoin,RWA,GameFi"

class MiningGameConfig(BaseModel):
    """Настройки для игры 'Виртуальный Майнинг'."""
    duration_seconds: int = 8 * 3600  # 8 часов
    referral_bonus_amount: float = 50.0
    electricity_tariffs: Dict[str, Dict[str, float]] = {
        "Домашний 💡": {"cost_per_hour": 0.05, "unlock_price": 0},
        "Промышленный 🏭": {"cost_per_hour": 0.02, "unlock_price": 200},
        "Зеленый 🌱": {"cost_per_hour": 0.08, "unlock_price": 50},
        "Гидроэлектростанция 💧": {"cost_per_hour": 0.01, "unlock_price": 500}
    }
    default_electricity_tariff: str = "Домашний 💡"

class FeatureFlags(BaseModel):
    """Флаги для включения/отключения экспериментальных функций."""
    enable_ai_consultant: bool = True
    enable_crypto_center: bool = True
    enable_mining_game: bool = True

class SchedulerSettings(BaseModel):
    """Настройки для планировщика задач."""
    news_interval_hours: int = 3
    asic_update_hours: int = 1
    morning_summary_hour: int = 9
    leaderboard_day_of_week: str = 'fri'
    leaderboard_hour: int = 18
    health_check_minutes: int = 15

# --- ИСПРАВЛЕНИЕ: Добавлен недостающий класс ---
class ThreatFilterSettings(BaseModel):
    """Настройки для системы предотвращения угроз."""
    sandbox_period_seconds: int = 24 * 3600  # 24 часа
    critical_toxicity_threshold: float = 0.9
    threat_score_threshold: float = 100.0
    low_trust_threshold: int = 50
    high_trust_threshold: int = 150

    class ScoreWeights(BaseModel):
        ai_spam: float = 60.0
        has_link: float = 30.0

    class Multipliers(BaseModel):
        low_trust: float = 1.5
        high_trust_discount_factor: float = 0.25

    score_weights: ScoreWeights = Field(default_factory=ScoreWeights)
    multipliers: Multipliers = Field(default_factory=Multipliers)
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---

# --- Главный класс настроек ---

class AppSettings(BaseSettings):
    """
    Основной класс конфигурации, объединяющий все настройки приложения.
    """
    api_keys: ApiKeysConfig = Field(default_factory=ApiKeysConfig)
    
    admin: AdminConfig
    
    endpoints: ApiEndpoints = Field(default_factory=ApiEndpoints)
    news: NewsConfig = Field(default_factory=NewsConfig)
    game: MiningGameConfig = Field(default_factory=MiningGameConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    threat_filter: ThreatFilterSettings = Field(default_factory=ThreatFilterSettings) # Добавлено поле

    # Общие настройки
    ticker_aliases: Dict[str, str] = {
        'бтк': 'BTC', 'биткоин': 'BTC', 'биток': 'BTC',
        'eth': 'ETH', 'эфир': 'ETH', 'эфириум': 'ETH'
    }
    popular_tickers: List[str] = ['BTC', 'ETH', 'SOL', 'TON', 'KAS', 'ARB']
    
    # Настройки модерации
    stop_words: Set[str] = {
        "казино", "ставки", "бонус", "фриспин", "депозит", "работа",
        "вакансия", "зарплата", "заработок"
    }
    allowed_link_user_ids: List[int] = []

    # Резервные данные
    fallback_asics: List[Dict[str, Any]] = Field(default_factory=lambda: load_json_fallback("fallback_asics.json"))
    fallback_quiz: List[Dict[str, Any]] = Field(default_factory=lambda: load_json_fallback("fallback_quiz.json"))

    @model_validator(mode='after')
    def set_allowed_users(self) -> 'AppSettings':
        """Добавляет ID админов в список разрешенных для постинга ссылок."""
        all_admin_ids = set(self.admin.admin_user_ids)
        if self.admin.admin_chat_id:
            all_admin_ids.add(self.admin.admin_chat_id)
        
        # Используем множество для избежания дубликатов
        self.allowed_link_user_ids = sorted(list(set(self.allowed_link_user_ids) | all_admin_ids))
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter='__' # Позволяет задавать вложенные переменные, например, API_KEYS__BOT_TOKEN
    )

def load_json_fallback(filename: str) -> List[Dict[str, Any]]:
    """Вспомогательная функция для загрузки резервных данных из JSON."""
    file_path = BASE_DIR / "data" / filename
    if not file_path.exists():
        logging.warning(f"Fallback file '{filename}' not found at '{file_path}'.")
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Failed to load fallback file '{filename}': {e}")
        return []

# Создаем единственный экземпляр настроек для всего приложения
settings = AppSettings()
