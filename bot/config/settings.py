# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "ГЕНИЙ 3.1" - АВГУСТ 2025)
# Описание: Полная конфигурация, включая EndpointsConfig.
# =================================================================================

import json
from pathlib import Path
from typing import List, Dict, Any

# Импортируем HttpUrl для валидации URL-адресов
from pydantic import BaseModel, Field, SecretStr, computed_field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем BASE_DIR и директорию для конфигураций
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DATA_DIR = BASE_DIR / "data"

# --- Вспомогательные модели для JSON-конфигураций ---

# >>>>> НАЧАЛО ИСПРАВЛЕНИЯ 1: Добавлена конфигурация EndpointsConfig <<<<<
class EndpointsConfig(BaseModel):
    """
    Конфигурация URL-адресов для внешних источников данных (ParserService).
    Используем HttpUrl для автоматической валидации URL.
    """
    whattomine_api: HttpUrl
    asicminervalue_api: HttpUrl
    minerstat_hardware_api: HttpUrl
# >>>>> КОНЕЦ ИСПРАВЛЕНИЯ 1 <<<<<

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

# Убедитесь, что эта модель также присутствует (из предыдущего исправления)
class AsicServiceConfig(BaseModel):
    """
    Настройки для AsicService (rapidfuzz).
    """
    merge_score_cutoff: int = Field(ge=0, le=100, default=90) 
    enrich_score_cutoff: int = Field(ge=0, le=100, default=85)

# --- Главный класс настроек ---

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / '.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )

    # --- Переменные из Environment ---
    BOT_TOKEN: SecretStr
    # Используем современный синтаксис T | None
    GEMINI_API_KEY: SecretStr | None = None 
    ADMIN_USER_IDS: str
    ADMIN_CHAT_ID: int
    NEWS_CHAT_ID: int
    REDIS_URL: str

    @computed_field
    @property
    def admin_ids_list(self) -> List[int]:
        if not self.ADMIN_USER_IDS:
            return []
        try:
            return [int(item.strip()) for item in self.ADMIN_USER_IDS.split(',')]
        except ValueError:
            raise ValueError("ADMIN_USER_IDS должен быть списком чисел, разделенных запятыми.")

    # --- Вспомогательная функция для безопасной загрузки JSON ---
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
    asic_service: AsicServiceConfig = Field(
        default_factory=lambda: AsicServiceConfig(**Settings._load_json_config(CONFIG_DATA_DIR / "asic_service_config.json"))
    )

    # >>>>> НАЧАЛО ИСПРАВЛЕНИЯ 2: Интеграция EndpointsConfig <<<<<
    endpoints: EndpointsConfig = Field(
        default_factory=lambda: EndpointsConfig(**Settings._load_json_config(CONFIG_DATA_DIR / "endpoints_config.json"))
    )
    # >>>>> КОНЕЦ ИСПРАВЛЕНИЯ 2 <<<<<

# Глобальный экземпляр настроек
settings = Settings()