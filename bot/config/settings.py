# ===============================================================
# Файл: bot/config/settings.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Комплексная реструктуризация и обновление конфигурации.
# Внедрены вложенные классы для модульности, добавлены резервные
# API, актуализированы данные и введены флаги функций для гибкости.
# ===============================================================

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from pydantic import model_validator, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определение базовой директории проекта для корректной работы с путями
BASE_DIR = Path(__file__).parent.parent.parent

def load_fallback_asics() -> List[Dict[str, Any]]:
    """
    Загружает резервный список ASIC-майнеров из JSON-файла.
    Если файл отсутствует, возвращает жестко закодированный список
    актуальных на 2025 год моделей для обеспечения автономной работы.
    """
    file_path = BASE_DIR / "data" / "fallback_asics.json"
    if not file_path.exists():
        # Резервные данные с актуальными на 2025 год ASIC-майнерами
        return [
            {"name": "Antminer S21 Pro", "profitability": 25.5, "power": 3550, "hashrate": "234 TH/s", "algorithm": "SHA-256", "efficiency": "15.1 J/TH"},
            {"name": "WhatsMiner M63S", "profitability": 30.0, "power": 3900, "hashrate": "190 TH/s", "algorithm": "SHA-256", "efficiency": "20.5 J/TH"},
            {"name": "Iceriver KS5L", "profitability": 18.0, "power": 3400, "hashrate": "12 TH/s", "algorithm": "KHeavyHash", "efficiency": "283 J/GH"}
        ]
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- Вложенные классы для структурирования настроек ---

class ApiKeysSettings(BaseSettings):
    """Секретные ключи и токены для доступа к API."""
    bot_token: str = Field(alias='BOT_TOKEN')
    gemini_api_key: str = Field(alias='GEMINI_API_KEY')
    admin_chat_id: int = Field(alias='ADMIN_CHAT_ID')
    news_chat_id: int = Field(alias='NEWS_CHAT_ID')

    # Опциональные ключи для расширенного функционала
    openai_api_key: Optional[str] = Field(alias='OPENAI_API_KEY', default=None)
    cmc_api_key: Optional[str] = Field(alias='CMC_API_KEY', default=None)
    cryptocompare_api_key: Optional[str] = Field(alias='CRYPTOCOMPARE_API_KEY', default=None)
    blockchair_api_key: Optional[str] = Field(alias='BLOCKCHAIR_API_KEY', default=None)
    glassnode_api_key: Optional[str] = Field(alias='GLASSNODE_API_KEY', default=None)

class DatabaseSettings(BaseSettings):
    """Настройки подключения к базам данных и кэшу."""
    redis_url: str = Field(alias='REDIS_URL', default='redis://localhost:6379/0')

class AdminSettings(BaseSettings):
    """Настройки администрирования."""
    admin_user_ids_str: str = Field(alias='ADMIN_USER_IDS', default='')

    @computed_field
    @property
    def ADMIN_USER_IDS(self) -> List[int]:
        """Преобразует строку ID администраторов в список целых чисел."""
        if not self.admin_user_ids_str.strip():
            return []
        try:
            return [int(item.strip()) for item in self.admin_user_ids_str.split(',') if item.strip()]
        except (ValueError, TypeError):
            return []

class DataSourceEndpoints(BaseSettings):
    """URL-адреса для внешних API и источников данных."""
    # Основные и резервные эндпоинты для повышения отказоустойчивости
    coingecko_api_base: str = "https://api.coingecko.com/api/v3"
    coinpaprika_api_base: str = "https://api.coinpaprika.com/v1"
    cryptocompare_api_base: str = "https://min-api.cryptocompare.com"
    minerstat_api_base: str = "https://api.minerstat.com/v2"
    whattomine_asics_url: str = "https://whattomine.com/coins.json"
    asicminervalue_url: str = "https://www.asicminervalue.com/miners"
    fear_and_greed_api_url: str = "https://api.alternative.me/fng/?limit=1"
    cbr_daily_json_url: str = "https://www.cbr-xml-daily.ru/daily_json.js"

    # Эндпоинты для данных по Bitcoin с резервными вариантами
    btc_halving_url: str = "https://mempool.space/api/blocks/tip/height"
    btc_halving_fallback_url: str = "https://blockstream.info/api/blocks/tip/height"
    btc_fees_url: str = "https://mempool.space/api/v1/fees/recommended"
    btc_fees_fallback_url: str = "https://blockstream.info/api/v1/fees/recommended"
    btc_mempool_url: str = "https://mempool.space/api/mempool"
    btc_mempool_fallback_url: str = "https://blockstream.info/api/mempool"

class NewsSettings(BaseSettings):
    """Настройки для агрегации и публикации новостей."""
    # Основные новостные RSS-фиды
    general_rss_feeds: List[str] = [
        "https://forklog.com/feed",
        "https://beincrypto.ru/feed/",
        "https://cointelegraph.com/rss/tag/russia"
    ]
    # Передовые "альфа" источники для глубокого анализа
    alpha_rss_feeds: List[str] = [
        "https://thedefiant.io/feed",
        "https://bankless.substack.com/feed",
        "https://www.theblock.co/rss.xml",
        "https://messari.io/rss",
        "https://blog.l2beat.com/rss"
    ]
    # API для новостного центра с расширенными категориями
    crypto_center_news_api_url: str = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories=Airdrop,Mining,DeFi,L1,L2,Altcoin,RWA,GameFi"
    news_interval_hours: int = 3

class MiningSettings(BaseSettings):
    """Настройки, связанные с майнингом и криптовалютами."""
    asic_cache_update_hours: int = 1
    # Алиасы для удобного поиска тикеров
    ticker_aliases: Dict[str, str] = {
        'бтк': 'BTC', 'биткоин': 'BTC', 'биток': 'BTC',
        'eth': 'ETH', 'эфир': 'ETH', 'эфириум': 'ETH',
        'каспа': 'KAS', 'солана': 'SOL', 'тон': 'TON'
    }
    # Список популярных тикеров, актуальный на 2025 год
    popular_tickers: List[str] = ['BTC', 'ETH', 'SOL', 'TON', 'KAS', 'ARB']
    fallback_asics: List[Dict[str, Any]] = Field(default_factory=load_fallback_asics)

class GameSettings(BaseSettings):
    """Настройки для внутриигровой механики 'симулятора майнинга'."""
    MINING_DURATION_SECONDS: int = 8 * 3600  # 8 часов
    REFERRAL_BONUS_AMOUNT: float = 50.0
    # Разнообразные тарифы на электроэнергию для игровой стратегии
    ELECTRICITY_TARIFFS: Dict[str, Dict[str, float]] = {
        "Домашний 💡": {"cost_per_hour": 0.05, "unlock_price": 0},
        "Промышленный 🏭": {"cost_per_hour": 0.02, "unlock_price": 200},
        "Зеленый 🌱": {"cost_per_hour": 0.08, "unlock_price": 50},
        "Гидроэлектростанция 💧": {"cost_per_hour": 0.015, "unlock_price": 1000}
    }
    DEFAULT_ELECTRICITY_TARIFF: str = "Домашний 💡"

class ModerationSettings(BaseSettings):
    """Настройки модерации контента в чатах."""
    STOP_WORDS: List[str] = [
        "казино", "ставки", "бонус", "фриспин", "депозит",
        "работа", "вакансия", "зарплата", "заработок"
    ]
    # Список ID пользователей, которым разрешено публиковать ссылки
    ALLOWED_LINK_USER_IDS: List[int] = []

class FeatureFlags(BaseSettings):
    """
    Флаги функций для динамического включения/отключения функционала.
    Позволяет тестировать новые возможности на части аудитории.
    """
    ENABLE_ADVANCED_ANALYTICS: bool = Field(alias="FEATURE_ENABLE_ADVANCED_ANALYTICS", default=True)
    ENABLE_GAME_LEADERBOARD: bool = Field(alias="FEATURE_ENABLE_GAME_LEADERBOARD", default=True)
    ENABLE_ZK_PROOFS_INFO: bool = Field(alias="FEATURE_ENABLE_ZK_PROOFS_INFO", default=False)

# --- Основной класс конфигурации ---

class AppSettings(BaseSettings):
    """
    Главный класс, объединяющий все настройки приложения.
    Использует вложенные классы для лучшей организации.
    """
    api_keys: ApiKeysSettings = Field(default_factory=ApiKeysSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    admin: AdminSettings = Field(default_factory=AdminSettings)
    data_sources: DataSourceEndpoints = Field(default_factory=DataSourceEndpoints)
    news: NewsSettings = Field(default_factory=NewsSettings)
    mining: MiningSettings = Field(default_factory=MiningSettings)
    game: GameSettings = Field(default_factory=GameSettings)
    moderation: ModerationSettings = Field(default_factory=ModerationSettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.prod"), # Ищет .env, затем .env.prod
        env_nested_delimiter='__', # Для переменных окружения типа API_KEYS__BOT_TOKEN
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    @model_validator(mode='after')
    def set_allowed_users(self) -> 'AppSettings':
        """
        Автоматически добавляет ID администраторов в список разрешенных
        для публикации ссылок для удобства управления.
        """
        allowed_ids = set(self.moderation.ALLOWED_LINK_USER_IDS)
        
        if self.api_keys.admin_chat_id:
            allowed_ids.add(self.api_keys.admin_chat_id)
        
        for admin_id in self.admin.ADMIN_USER_IDS:
            allowed_ids.add(admin_id)
            
        self.moderation.ALLOWED_LINK_USER_IDS = sorted(list(allowed_ids))
        return self

# Глобальный экземпляр настроек, который будет использоваться во всем приложении
settings = AppSettings()

# Пример доступа к настройкам:
# from bot.config.settings import settings
# token = settings.api_keys.bot_token
# popular = settings.mining.popular_tickers
