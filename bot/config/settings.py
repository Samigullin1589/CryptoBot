# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ 3)
# Описание: Финальная, "плоская" структура конфигурации, на 100%
# совместимая с переменными окружения пользователя в Render.
# =================================================================================

import json
import logging
from pathlib import Path
from typing import List, Dict

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

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

class Settings(BaseSettings):
    """
    Главный класс настроек. Загружает переменные из .env и Render.
    """
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / '.env',
        env_file_encoding='utf-8',
        extra='ignore' 
    )

    # --- Переменные из Environment (имена соответствуют Render) ---
    BOT_TOKEN: SecretStr
    GEMINI_API_KEY: SecretStr
    ADMIN_USER_IDS: List[int] # <<< ИСПРАВЛЕНИЕ ЗДЕСЬ
    ADMIN_CHAT_ID: int
    NEWS_CHAT_ID: int
    REDIS_URL: str

    # --- Настройки, загружаемые из JSON-файлов ---
    game: GameSettings = Field(default_factory=lambda: GameSettings(**json.load(open(BASE_DIR / "data/game_config.json"))))
    crypto_center: CryptoCenterSettings = Field(default_factory=lambda: CryptoCenterSettings(**json.load(open(BASE_DIR / "data/crypto_center_config.json"))))

settings = Settings()