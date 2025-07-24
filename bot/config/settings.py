# ===============================================================
# Файл: bot/config/settings.py (ОКОНЧАТЕЛЬНЫЙ FIX)
# Описание: Добавлены явные псевдонимы (alias) для всех переменных окружения,
# чтобы гарантировать их загрузку Pydantic. Обновлены URL и добавлены резервные ASIC.
# ===============================================================
import json
from pathlib import Path
from typing import List, Dict, Any

from pydantic import model_validator, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent.parent

def load_fallback_asics() -> List[Dict[str, Any]]:
    file_path = BASE_DIR / "data" / "fallback_asics.json"
    if not file_path.exists():
        # Резервные данные ASIC на случай отсутствия файла
        return [
            {"name": "Antminer S19 Pro", "profitability": 10.5, "power": 3250, "hashrate": "110 TH/s", "algorithm": "SHA-256", "efficiency": "29.5 J/TH"},
            {"name": "WhatsMiner M30S+", "profitability": 12.0, "power": 3470, "hashrate": "112 TH/s", "algorithm": "SHA-256", "efficiency": "31.0 J/TH"}
        ]
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

class AppSettings(BaseSettings):
    # --- Основные секреты и ID ---
    bot_token: str = Field(alias='BOT_TOKEN')
    redis_url: str = Field(alias='REDIS_URL')
    openai_api_key: str = Field(alias='OPENAI_API_KEY', default="")
    gemini_api_key: str = Field(alias='GEMINI_API_KEY')
    admin_chat_id: int = Field(alias='ADMIN_CHAT_ID')
    admin_user_ids_str: str = Field(alias='ADMIN_USER_IDS', default='')
    news_chat_id: int = Field(alias='NEWS_CHAT_ID')
    cmc_api_key: str = Field(alias='CMC_API_KEY', default="")
    
    cryptocompare_api_key: str = Field(alias='CRYPTOCOMPARE_API_KEY', default="")

    # API Endpoints
    coingecko_api_base: str = "https://api.coingecko.com/api/v3"
    coinpaprika_api_base: str = "https://api.coinpaprika.com/v1"
    cryptocompare_api_base: str = "https://min-api.cryptocompare.com"
    minerstat_api_base: str = "https://api.minerstat.com/v2"
    # Обновленный URL для WhatToMine (исправлен на актуальный формат)
    whattomine_asics_url: str = "https://whattomine.com/coins.json"
    # Обновленный URL для AsicMinerValue с более точным парсингом таблицы
    asicminervalue_url: str = "https://www.asicminervalue.com/miners"
    fear_and_greed_api_url: str = "https://api.alternative.me/fng/?limit=1"
    cbr_daily_json_url: str = "https://www.cbr-xml-daily.ru/daily_json.js"
    btc_halving_url: str = "https://mempool.space/api/blocks/tip/height"
    btc_fees_url: str = "https://mempool.space/api/v1/fees/recommended"
    btc_mempool_url: str = "https://mempool.space/api/mempool"

    # App Settings
    news_rss_feeds: List[str] = ["https://forklog.com/feed", "https://beincrypto.ru/feed/", "https://cointelegraph.com/rss/tag/russia"]
    news_interval_hours: int = 3
    asic_cache_update_hours: int = 1

    ticker_aliases: Dict[str, str] = {'бтк': 'BTC', 'биткоин': 'BTC', 'биток': 'BTC', 'eth': 'ETH', 'эфир': 'ETH', 'эфириум': 'ETH'}
    popular_tickers: List[str] = ['BTC', 'ETH', 'SOL', 'TON', 'KAS']

    # Mining Game Settings
    MINING_DURATION_SECONDS: int = 8 * 3600
    REFERRAL_BONUS_AMOUNT: float = 50.0
    ELECTRICITY_TARIFFS: Dict[str, Dict[str, float]] = {
        "Домашний 💡": {"cost_per_hour": 0.05, "unlock_price": 0},
        "Промышленный 🏭": {"cost_per_hour": 0.02, "unlock_price": 200},
        "Зеленый 🌱": {"cost_per_hour": 0.08, "unlock_price": 50}
    }
    DEFAULT_ELECTRICITY_TARIFF: str = "Домашний 💡"

    # Crypto Center Settings
    crypto_center_news_api_url: str = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories=Airdrop,Mining,DeFi,L1,L2,Altcoin"
    alpha_rss_feeds: List[str] = [
        "https://thedefiant.io/feed",
        "https://bankless.substack.com/feed",
        "https://www.theblock.co/rss.xml"
    ]

    # Moderation Settings
    STOP_WORDS: List[str] = ["казино", "ставки", "бонус", "фриспин", "депозит", "работа", "вакансия", "зарплата", "заработок"]
    ALLOWED_LINK_USER_IDS: List[int] = []

    fallback_asics: List[Dict[str, Any]] = Field(default_factory=load_fallback_asics)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    @computed_field
    @property
    def ADMIN_USER_IDS(self) -> List[int]:
        if not self.admin_user_ids_str.strip():
            return []
        try:
            return [int(item.strip()) for item in self.admin_user_ids_str.split(',') if item.strip()]
        except (ValueError, TypeError):
            return []
    
    @model_validator(mode='after')
    def set_allowed_users(self) -> 'AppSettings':
        if self.admin_chat_id and self.admin_chat_id not in self.ALLOWED_LINK_USER_IDS:
            self.ALLOWED_LINK_USER_IDS.append(self.admin_chat_id)
        
        for admin_id in self.ADMIN_USER_IDS:
            if admin_id not in self.ALLOWED_LINK_USER_IDS:
                self.ALLOWED_LINK_USER_IDS.append(admin_id)
            
        return self

settings = AppSettings()