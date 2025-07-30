# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ 7)
# Описание: Добавлена конфигурация для Throttling Middleware.
# =================================================================================

import json
from pathlib import Path
from typing import List, Dict, Any

from pydantic import BaseModel, Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Вспомогательные модели для JSON-конфигураций ---

class GameTariff(BaseModel):
    cost_per_hour: float
    unlock_price: float

class GameSettings(BaseModel):
    mining_duration_seconds: int
    min_withdrawal_amount: float
    market_commission_rate: float
    default_electricity_tariff: str
    electricity_tariffs: Dict[str, GameTariff]

class CryptoCenterSettings(BaseModel):
    news_context_limit: int
    alpha_cache_ttl_seconds: int
    feed_cache_ttl_seconds: int

class ThrottlingSettings(BaseModel):
    """Настройки для Throttling Middleware."""
    rate_limit: float
    user_rate_limit: float
    chat_rate_limit: float

# --- Главный класс настроек ---

class Settings(BaseSettings):
    """Главный класс настроек. Загружает переменные из .env и Render."""
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / '.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )

    # --- Переменные из Environment ---
    BOT_TOKEN: SecretStr
    GEMINI_API_KEY: SecretStr
    ADMIN_USER_IDS: str
    ADMIN_CHAT_ID: int
    NEWS_CHAT_ID: int
    REDIS_URL: str

    @computed_field
    @property
    def admin_ids_list(self) -> List[int]:
        """Парсит строку ADMIN_USER_IDS в список чисел."""
        return [int(item.strip()) for item in self.ADMIN_USER_IDS.split(',')]

    # --- Настройки, загружаемые из JSON-файлов ---
    game: GameSettings = Field(default_factory=lambda: GameSettings(**json.load(open(BASE_DIR / "data/game_config.json"))))
    crypto_center: CryptoCenterSettings = Field(default_factory=lambda: CryptoCenterSettings(**json.load(open(BASE_DIR / "data/crypto_center_config.json"))))
    throttling: ThrottlingSettings = Field(default_factory=lambda: ThrottlingSettings(**json.load(open(BASE_DIR / "data/throttling_config.json")))) # <<< ИЗМЕНЕНИЕ ЗДЕСЬ

settings = Settings()