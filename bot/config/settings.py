# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ПОЛНАЯ И ИСПРАВЛЕННАЯ)
# Описание: Конфигурация бота с использованием Pydantic. Включает все
# необходимые модели, в том числе исправленную игровую конфигурацию.
# =================================================================================

import logging
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем базовый путь проекта
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class LogLevel(str, Enum):
    """Уровни логирования."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class AppSettings(BaseModel):
    """Общие настройки приложения."""
    log_level: LogLevel = LogLevel.INFO
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

class RedisSettings(BaseModel):
    """Настройки подключения к Redis."""
    host: str = "127.0.0.1"
    port: int = 6379
    db: int = 0

class TelegramSettings(BaseModel):
    """Настройки Telegram."""
    admin_ids: List[int]

class ApiKeySettings(BaseModel):
    """Настройки ключей API."""
    bot_token: SecretStr
    gemini_api_key: SecretStr

class AdminPanelSettings(BaseModel):
    """Настройки админ-панели."""
    admin_chat_id: int

# --- МОДЕЛИ ИГРОВОЙ КОНФИГУРАЦИИ (ИСПРАВЛЕНИЕ ОШИБКИ) ---

class GameTariff(BaseModel):
    """
    Модель, описывающая тариф на электроэнергию.
    Именно этой модели не хватало, что приводило к ошибке импорта.
    """
    cost_per_hour: float  # Стоимость киловатт-часа
    unlock_price: float   # Цена разблокировки тарифа

class DefaultTariff(str, Enum):
    """Перечисление для тарифа по умолчанию."""
    standard = "Стандартный"

class GameSettings(BaseModel):
    """Все настройки, связанные с игрой 'Виртуальный Майнинг'."""
    mining_duration_seconds: int = 3600  # 1 час
    min_withdrawal_amount: float = 1000.0
    market_commission_rate: float = 0.05  # 5%
    default_electricity_tariff: DefaultTariff = DefaultTariff.standard
    electricity_tariffs: Dict[str, GameTariff] = {
        "Стандартный": GameTariff(cost_per_hour=0.1, unlock_price=0),
        "Льготный": GameTariff(cost_per_hour=0.07, unlock_price=5000),
        "Промышленный": GameTariff(cost_per_hour=0.04, unlock_price=25000)
    }

class FeatureFlags(BaseModel):
    """Флаги для включения/отключения функционала."""
    enable_mining_game: bool = True
    enable_crypto_center: bool = True
    enable_threat_filter: bool = True

class Settings(BaseSettings):
    """Главный класс настроек, собирающий все компоненты."""
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / '.env',
        env_nested_delimiter='__',
        env_file_encoding='utf-8',
    )

    app: AppSettings = Field(default_factory=AppSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    telegram: TelegramSettings
    api_keys: ApiKeySettings
    admin: AdminPanelSettings
    game: GameSettings = Field(default_factory=GameSettings)
    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags)

# Создаем глобальный экземпляр настроек
settings = Settings()