# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "ГЕНИЙ 5.0" - АВГУСТ 2025 - ПРОДАКШН)
# Описание: Полная, самодостаточная конфигурация приложения.
# =================================================================================

import json
from pathlib import Path
from typing import List, Dict, Any
import logging
import sys

# Импортируем HttpUrl для валидации URL-адресов
from pydantic import BaseModel, Field, SecretStr, computed_field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем BASE_DIR и директорию для конфигураций
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DATA_DIR = BASE_DIR / "data"

# --- Вспомогательные модели для JSON-конфигураций ---

class PriceServiceConfig(BaseModel):
    """
    Конфигурация для PriceService.
    """
    cache_ttl_seconds: int = Field(default=60, description="Время жизни кэша цен в секундах")
    tracked_coins: List[str] = Field(description="Список тикеров монет для отслеживания (например, BTC, ETH)")

class EndpointsConfig(BaseModel):
    """
    Конфигурация URL-адресов для внешних источников данных.
    Использует Pydantic HttpUrl для строгой валидации.
    """
    whattomine_api: HttpUrl
    asicminervalue_api: HttpUrl
    minerstat_hardware_api: HttpUrl
    
    # Используем T | None для опциональности (Стандарт 2025).
    coingecko_api_base: HttpUrl | None = None

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
    rate_limit: float
    user_rate_limit: float
    chat_rate_limit: float

class AsicServiceConfig(BaseModel):
    # Пороги для RapidFuzz
    merge_score_cutoff: int = Field(ge=0, le=100, default=90)
    enrich_score_cutoff: int = Field(ge=0, le=100, default=85)

# --- Главный класс настроек ---

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / '.env',
        env_file_encoding='utf-8',
        extra='ignore' # Игнорируем переменные окружения, не описанные в модели
    )

    # --- Переменные из Environment ---
    BOT_TOKEN: SecretStr
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
            # Критическая ошибка конфигурации должна останавливать запуск
            logging.critical("Ошибка конфигурации: ADMIN_USER_IDS должен быть списком чисел, разделенных запятыми.")
            raise ValueError("ADMIN_USER_IDS имеет неверный формат.")

    # --- Вспомогательная функция для безопасной загрузки JSON ---
    # Обеспечивает надежность запуска при отсутствии или повреждении конфигурационных файлов.
    @staticmethod
    def _load_json_config(file_path: Path) -> Dict[str, Any]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.critical(f"Критическая ошибка запуска: Конфигурационный файл не найден: {file_path}")
            raise
        except json.JSONDecodeError:
            logging.critical(f"Критическая ошибка запуска: Ошибка декодирования JSON в файле: {file_path}")
            raise

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
    endpoints: EndpointsConfig = Field(
        default_factory=lambda: EndpointsConfig(**Settings._load_json_config(CONFIG_DATA_DIR / "endpoints_config.json"))
    )
    price_service: PriceServiceConfig = Field(
        default_factory=lambda: PriceServiceConfig(**Settings._load_json_config(CONFIG_DATA_DIR / "price_service_config.json"))
    )

# Глобальный экземпляр настроек. Инициализируется при импорте модуля.
try:
    settings = Settings()
except Exception as e:
    # Перехватываем любую ошибку инициализации и завершаем работу
    logging.critical(f"Не удалось инициализировать настройки приложения: {e}")
    sys.exit(1)