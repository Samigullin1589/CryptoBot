# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ 4)
# Описание: Финальная конфигурация, которая корректно обрабатывает
# переменные окружения в виде comma-separated-strings.
# =================================================================================

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from pydantic import BaseModel, Field, SecretStr, field_validator
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

    # --- Переменные из Environment ---
    BOT_TOKEN: SecretStr
    GEMINI_API_KEY: SecretStr
    ADMIN_USER_IDS: List[int] # Поле остается List[int]
    ADMIN_CHAT_ID: int
    NEWS_CHAT_ID: int
    REDIS_URL: str

    # <<< НАЧАЛО ИСПРАВЛЕНИЯ >>>
    @field_validator('ADMIN_USER_IDS', mode='before')
    @classmethod
    def parse_comma_separated_ints(cls, v: Any) -> List[int]:
        """
        Этот валидатор преобразует строку "123,456" в список [123, 456].
        Именно это решает ошибку JSONDecodeError.
        """
        if isinstance(v, str):
            # Разделяем строку по запятым, убираем пробелы и преобразуем в int
            return [int(item.strip()) for item in v.split(',')]
        # Если это уже список (например, из другого источника), оставляем как есть
        return v
    # <<< КОНЕЦ ИСПРАВЛЕНИЯ >>>

    # --- Настройки, загружаемые из JSON-файлов ---
    game: GameSettings = Field(default_factory=lambda: GameSettings(**json.load(open(BASE_DIR / "data/game_config.json"))))
    crypto_center: CryptoCenterSettings = Field(default_factory=lambda: CryptoCenterSettings(**json.load(open(BASE_DIR / "data/crypto_center_config.json"))))

settings = Settings()