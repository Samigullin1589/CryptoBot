# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "ГЕНИЙ 3.0" - АВГУСТ 2025)
# Описание: Полная конфигурация, включая AsicServiceConfig и надежную загрузку JSON.
# =================================================================================

import json
from pathlib import Path
from typing import List, Dict, Any

from pydantic import BaseModel, Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем BASE_DIR и директорию для конфигураций
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DATA_DIR = BASE_DIR / "data"

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

# >>>>> НАЧАЛО ИСПРАВЛЕНИЯ 1: Добавлена недостающая конфигурация AsicService <<<<<
class AsicServiceConfig(BaseModel):
    """
    Настройки для AsicService, определяющие пороги нечеткого поиска (rapidfuzz).
    """
    # Порог для объединения данных из разных источников (WhatToMine, AsicMinerValue)
    merge_score_cutoff: int = Field(ge=0, le=100, default=90) 
    # Порог для обогащения данных спецификациями (Minerstat)
    enrich_score_cutoff: int = Field(ge=0, le=100, default=85)
# >>>>> КОНЕЦ ИСПРАВЛЕНИЯ 1 <<<<<


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
    # Используем | None (стандарт 2025) для опциональных ключей
    GEMINI_API_KEY: SecretStr | None = None 
    ADMIN_USER_IDS: str
    ADMIN_CHAT_ID: int
    NEWS_CHAT_ID: int
    REDIS_URL: str

    @computed_field
    @property
    def admin_ids_list(self) -> List[int]:
        """Парсит строку ADMIN_USER_IDS в список чисел."""
        if not self.ADMIN_USER_IDS:
            return []
        try:
            return [int(item.strip()) for item in self.ADMIN_USER_IDS.split(',')]
        except ValueError:
            # Более надежная обработка ошибок конфигурации
            raise ValueError("ADMIN_USER_IDS должен быть списком чисел, разделенных запятыми.")

    # --- Вспомогательная функция для безопасной загрузки JSON (Улучшение надежности) ---
    @staticmethod
    def _load_json_config(file_path: Path) -> Dict[str, Any]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Критическая ошибка: Конфигурационный файл не найден: {file_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Критическая ошибка: Ошибка декодирования JSON в файле: {file_path}")

    # --- Настройки, загружаемые из JSON-файлов ---
    
    game: GameSettings = Field(
        default_factory=lambda: GameSettings(**Settings._load_json_config(CONFIG_DATA_DIR / "game_config.json"))
    )
    crypto_center: CryptoCenterSettings = Field(
        default_factory=lambda: CryptoCenterSettings(**Settings._load_json_config(CONFIG_DATA_DIR / "crypto_center_config.json"))
    )
    throttling: ThrottlingSettings = Field(
        default_factory=lambda: ThrottlingSettings(**Settings._load_json_config(CONFIG_DATA_DIR / "throttling_config.json"))
    )
    
    # >>>>> НАЧАЛО ИСПРАВЛЕНИЯ 2: Интеграция AsicServiceConfig <<<<<
    asic_service: AsicServiceConfig = Field(
        default_factory=lambda: AsicServiceConfig(**Settings._load_json_config(CONFIG_DATA_DIR / "asic_service_config.json"))
    )
    # >>>>> КОНЕЦ ИСПРАВЛЕНИЯ 2 <<<<<

# Глобальный экземпляр настроек
# Примечание: Убедитесь, что эта строка находится в конце файла.
settings = Settings()