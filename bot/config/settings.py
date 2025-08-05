# bot/config/settings.py
# =================================================================================
# Файл: bot/config/settings.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Финальная, самодостаточная система конфигурации.
# Адаптирована под реальную структуру JSON-файлов проекта с использованием псевдонимов (alias).
# Реализована интеллектуальная загрузка для объединения связанных конфигов.
# =================================================================================

import json
from pathlib import Path
from typing import List, Dict, Any

from loguru import logger
from pydantic import BaseModel, Field, RedisDsn, HttpUrl, SecretStr, ConfigDict, ValidationError

# --- Определения моделей для частей конфигурации ---

class AIConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    provider: str = "gemini"
    api_key: SecretStr
    model_name: str = Field(..., alias="default_model_name", description="Имя модели для использования")

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
    feeds: Dict[str, HttpUrl] # Feeds будут добавлены из отдельного файла

class EndpointsConfig(BaseModel):
    coingecko_api_base: HttpUrl
    coingecko_api_coins_list: HttpUrl
    coingecko_api_simple_price: HttpUrl
    coingecko_api_coins_markets: HttpUrl
    coingecko_api_trending: HttpUrl
    blockchain_info_hashrate: HttpUrl
    mempool_space_difficulty: HttpUrl

# --- Главная модель настроек ---

class Settings(BaseModel):
    # --- Параметры из app_config.json ---
    token: SecretStr = Field(..., alias='BOT_TOKEN')
    admin_ids: List[int] = Field(..., alias='ADMIN_IDS')
    dsn: RedisDsn = Field(..., alias='REDIS_DSN')
    host: str = Field(..., alias='REDIS_HOST')
    port: int = Field(..., alias='REDIS_PORT')
    db: int = Field(0, ge=0, le=15, alias='REDIS_DB')
    password: SecretStr | None = Field(None, alias='REDIS_PASSWORD')
    log_level: str = "INFO"

    # --- Вложенные параметры из других файлов ---
    throttling: ThrottlingConfig
    feature_flags: FeatureFlags
    endpoints: EndpointsConfig
    price_service: PriceServiceConfig
    coin_list_service: CoinListServiceConfig
    news_service: NewsServiceConfig
    ai: AIConfig

    class Config:
        populate_by_name = True
        extra = 'ignore'

def _load_json_file(path: Path) -> Dict[str, Any]:
    """Вспомогательная функция для безопасной загрузки JSON."""
    if not path.exists():
        logger.warning(f"Файл конфигурации не найден: {path}, пропуск.")
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Не удалось прочитать или декодировать файл {path}: {e}")
        raise SystemExit(f"Критическая ошибка конфигурации в файле: {path.name}")

def load_settings(base_path: str = "data") -> Settings:
    """
    Загружает все файлы конфигурации, интеллектуально объединяет их
    в один словарь и валидирует с помощью модели Settings.
    """
    logger.info(f"Загрузка конфигураций из директории: {base_path}")
    
    base_dir = Path(base_path)
    
    # 1. Загружаем основные файлы
    app_config = _load_json_file(base_dir / "app_config.json")
    throttling_config = _load_json_file(base_dir / "throttling_config.json")
    feature_flags_config = _load_json_file(base_dir / "feature_flags.json")
    endpoints_config = _load_json_file(base_dir / "endpoints_config.json")
    price_service_config = _load_json_file(base_dir / "price_service_config.json")
    coin_list_config = _load_json_file(base_dir / "coin_list_config.json")
    ai_config = _load_json_file(base_dir / "ai_config.json")

    # 2. Особая обработка для NewsService
    news_service_config = _load_json_file(base_dir / "news_service_config.json")
    news_feeds = _load_json_file(base_dir / "news_feeds.json")
    if news_feeds:
        news_service_config['feeds'] = news_feeds # Добавляем ленты в конфиг сервиса

    # 3. Собираем единый словарь для валидации
    combined_config: Dict[str, Any] = {
        **app_config, # Распаковываем ключи из app_config на верхний уровень
        "throttling": throttling_config,
        "feature_flags": feature_flags_config,
        "endpoints": endpoints_config,
        "price_service": price_service_config,
        "coin_list_service": coin_list_config,
        "news_service": news_service_config,
        "ai": ai_config,
    }

    try:
        settings_instance = Settings.model_validate(combined_config)
        logger.info("Все конфигурации успешно загружены и валидированы.")
        return settings_instance
    except ValidationError as e:
        logger.critical(f"Критическая ошибка валидации настроек. Проверьте ваши .json файлы и переменные окружения. Ошибки:\n{e}")
        raise SystemExit("Не удалось инициализировать настройки из-за ошибок валидации.")

# Создаем единственный глобальный экземпляр настроек
settings = load_settings()
