# bot/config/settings.py
# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Финальная, самодостаточная система конфигурации.
# Адаптирована под реальную структуру JSON-файлов проекта.
# Загружает все конфиги, объединяет и валидирует их в единую модель.
# =================================================================================

import json
import os
from pathlib import Path
from typing import List, Dict, Any

from loguru import logger
from pydantic import BaseModel, Field, RedisDsn, HttpUrl, SecretStr, ConfigDict, ValidationError

# --- Определения моделей для частей конфигурации ---
# Эти модели не используются напрямую для загрузки файлов, а служат
# для структурирования и валидации финального объекта Settings.

class AIConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    provider: str = "gemini"
    api_key: SecretStr
    model_name: str = Field(..., description="Имя модели для использования")

class ThrottlingConfig(BaseModel):
    rate_limit: float = 0.5
    key_prefix: str = "throttling"

class FeatureFlags(BaseModel):
    maintenance_mode: bool = False
    enable_game: bool = True
    enable_threat_protection: bool = True

class PriceServiceConfig(BaseModel):
    cache_ttl_seconds: int = 300
    top_n_coins: int = 100

class CoinListServiceConfig(BaseModel):
    update_interval_hours: int
    fallback_file_path: str

class NewsServiceConfig(BaseModel):
    cache_ttl_seconds: int = 3600
    feeds: Dict[str, HttpUrl]

# --- Главная модель настроек ---
# Объединяет в себе ВСЕ параметры из всех конфигурационных файлов.
# Это позволяет иметь единый, типизированный и валидированный источник истины.

class Settings(BaseModel):
    # --- Параметры из app_config.json (предположительно) ---
    token: SecretStr = Field(..., alias='BOT_TOKEN') # Используем alias, если ключ в JSON другой
    admin_ids: List[int]
    dsn: RedisDsn = Field(..., alias='REDIS_DSN')
    host: str = Field(..., alias='REDIS_HOST')
    port: int = Field(..., alias='REDIS_PORT')
    db: int = Field(0, ge=0, le=15, alias='REDIS_DB')
    password: SecretStr | None = Field(None, alias='REDIS_PASSWORD')
    log_level: str = "INFO"

    # --- Параметры из других файлов ---
    throttling: ThrottlingConfig
    feature_flags: FeatureFlags
    endpoints: EndpointsConfig # EndpointsConfig будет загружен как вложенный словарь
    price_service: PriceServiceConfig
    coin_list_service: CoinListServiceConfig
    news_service: NewsServiceConfig
    ai: AIConfig

    class Config:
        # Позволяет Pydantic использовать псевдонимы (aliases)
        populate_by_name = True
        # Позволяет игнорировать лишние поля в JSON, которые не определены в модели
        extra = 'ignore'

class EndpointsConfig(BaseModel):
    # Эта модель остается вложенной, так как endpoints.json, скорее всего, имеет такую структуру
    coingecko_api_base: HttpUrl
    coingecko_api_coins_list: HttpUrl
    coingecko_api_simple_price: HttpUrl
    coingecko_api_coins_markets: HttpUrl
    coingecko_api_trending: HttpUrl
    blockchain_info_hashrate: HttpUrl
    mempool_space_difficulty: HttpUrl


def load_settings(base_path: str = "data") -> Settings:
    """
    Загружает все файлы конфигурации из указанной директории,
    объединяет их в один словарь и валидирует с помощью модели Settings.
    """
    logger.info(f"Загрузка конфигураций из директории: {base_path}")
    
    # Список файлов для загрузки. Порядок важен, если ключи пересекаются.
    config_files = {
        "app": "app_config.json",
        "throttling": "throttling_config.json",
        "feature_flags": "feature_flags.json",
        "endpoints": "endpoints_config.json",
        "price_service": "price_service_config.json",
        "coin_list_service": "coin_list_config.json",
        "news_service": "news_service_config.json",
        "ai": "ai_config.json",
    }
    
    combined_config: Dict[str, Any] = {}

    for name, filename in config_files.items():
        path = Path(base_path) / filename
        if not path.exists():
            logger.warning(f"Файл конфигурации не найден: {path}, пропуск.")
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Если файл не для app, вкладываем его содержимое под соответствующим ключом
                if name != "app":
                    combined_config[name] = data
                else:
                    # Содержимое app_config.json добавляем на верхний уровень
                    combined_config.update(data)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Не удалось прочитать или декодировать файл {path}: {e}")
            raise SystemExit(f"Критическая ошибка конфигурации в файле: {filename}")

    try:
        settings_instance = Settings.model_validate(combined_config)
        logger.info("Все конфигурации успешно загружены и валидированы.")
        return settings_instance
    except ValidationError as e:
        # ИСПРАВЛЕНИЕ: Безопасное логирование ошибки валидации
        logger.critical(f"Критическая ошибка валидации настроек. Проверьте ваши .json файлы. Ошибки: {e}")
        raise SystemExit("Не удалось инициализировать настройки из-за ошибок валидации.")

# Создаем единственный глобальный экземпляр настроек,
# который будет импортироваться во всем приложении.
settings = load_settings()
