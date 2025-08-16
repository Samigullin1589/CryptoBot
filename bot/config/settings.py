# =================================================================================
# Файл: bot/config/settings.py
# Версия: "Distinguished Engineer" — МАКСИМАЛЬНАЯ, СЛИТО И РАСШИРЕНО
# Описание:
#   Единая, строго типизированная система конфигурации для бота (aiogram 3 + Redis).
#   Совмещает твой вариант + мои дополнения:
#     • Полный набор сервисных конфигов (новости, цены, рынок, игра, достижения и т.д.)
#     • Безопасные валидаторы (ADMIN_USER_IDS), строгие типы (Pydantic v2)
#     • Доп. endpoint для курса валют (currency_rate_api)
#     • Расширяемая секция логирования/телеметрии
#     • Гибкая AI-конфигурация (Gemini по умолчанию, OpenAI — опционально)
#     • Совместимость с ранее залогированными сообщениями и DI-контейнером
# =================================================================================

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, RedisDsn, SecretStr, ValidationError, field_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


# ----------------------------- AI / LLM ---------------------------------------

class AIConfig(BaseModel):
    """
    Общие настройки генеративных моделей.
    По умолчанию используем Gemini; OpenAI — опционально (если установлен пакет и задан ключ).
    """
    model_config = ConfigDict(protected_namespaces=())

    provider: str = "gemini"  # "gemini" | "openai" | "none"
    model_name: str = "gemini-1.5-pro-latest"
    flash_model_name: str = "gemini-1.5-flash-latest"
    default_temperature: float = 0.5
    max_retries: int = 5
    history_max_size: int = 10


# ----------------------------- Throttling / Flags -----------------------------

class ThrottlingConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    user_rate_limit: float = 2.0
    chat_rate_limit: float = 1.0
    key_prefix: str = "throttling"


class FeatureFlags(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    maintenance_mode: bool = False
    enable_game: bool = True
    enable_threat_protection: bool = True


# ----------------------------- Price / Coins / News ---------------------------

class PriceServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    cache_ttl_seconds: int = 90
    top_n_coins: int = 100
    default_vs_currency: str = "usd"


class CoinListServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    update_interval_hours: int = 24
    fallback_file_path: str = "data/fallback_coins.json"
    search_score_cutoff: int = 90


class NewsFeeds(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    main_rss_feeds: List[HttpUrl] = [
        "https://forklog.com/feed",
        "https://beincrypto.ru/feed/",
        "https://cointelegraph.com/rss",
    ]
    alpha_rss_feeds: List[HttpUrl] = []


class NewsServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    cache_ttl_seconds: int = 3600
    feeds: NewsFeeds = Field(default_factory=NewsFeeds)
    news_limit_per_source: int = 5


# ----------------------------- Endpoints --------------------------------------

class EndpointsConfig(BaseModel):
    """
    Все внешние API, которые использует проект.
    Добавлен currency_rate_api для получения курсов валют.
    """
    model_config = ConfigDict(protected_namespaces=())

    coingecko_api_base: HttpUrl = "https://api.coingecko.com/api/v3"
    coingecko_api_pro_base: HttpUrl = "https://pro-api.coingecko.com/api/v3"
    cryptocompare_api_base: HttpUrl = "https://min-api.cryptocompare.com"
    cryptocompare_price_endpoint: str = "/data/pricemulti"

    coins_list_endpoint: str = "/coins/list"
    coins_markets_endpoint: str = "/coins/markets"
    simple_price_endpoint: str = "/simple/price"

    fear_and_greed_api: HttpUrl = "https://api.alternative.me/fng/"
    mempool_space_difficulty: HttpUrl = "https://mempool.space/api/v1/difficulty-adjustment"
    mempool_space_tip_height: HttpUrl = "https://mempool.space/api/blocks/tip/height"
    blockchain_info_hashrate: HttpUrl = "https://blockchain.info/q/hashrate"

    whattomine_api: Optional[HttpUrl] = "https://whattomine.com/asics.json"
    asicminervalue_url: Optional[HttpUrl] = "https://www.asicminervalue.com/"
    minerstat_api: Optional[HttpUrl] = "https://api.minerstat.com/v2"

    # Новый эндпоинт для курсов валют (USD-база по умолчанию)
    currency_rate_api: Optional[HttpUrl] = "https://api.exchangerate-api.com/v4/latest/USD"


# ----------------------------- Security / Threats -----------------------------

class ThreatFilterConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = True
    toxicity_threshold: float = 0.75  # 0..1


# ----------------------------- ASIC / Market / Crypto Center ------------------

class AsicServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    update_interval_hours: int = 6
    fallback_file_path: str = "data/fallback_asics.json"
    merge_score_cutoff: int = 90
    enrich_score_cutoff: int = 95


class CryptoCenterServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    news_context_limit: int = 20
    alpha_cache_ttl_seconds: int = 1800
    feed_cache_ttl_seconds: int = 600


# ----------------------------- Quiz / Events / Achievements -------------------

class QuizServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    fallback_questions_path: str = "data/quiz_fallback.json"


class MiningEventServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    config_path: str = "data/events_config.json"
    default_multiplier: float = 1.0


class AchievementServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    config_path: str = "data/achievements.json"


# ----------------------------- Market Data ------------------------------------

class MarketDataServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    update_interval_seconds: int = 60
    top_n_coins: int = 100
    default_vs_currency: str = "usd"
    primary_provider: str = "cryptocompare"
    fallback_provider: str = "coingecko"


# ----------------------------- Mining Game ------------------------------------

class ElectricityTariff(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    cost_per_kwh: float
    unlock_price: float


class MiningGameServiceConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    session_duration_minutes: int = 60
    market_commission_rate: float = 0.05
    min_withdrawal_amount: float = 1000.0

    default_electricity_tariff: str = "Бытовой"

    # ВАЖНО: Pydantic приведёт вложенные dict'ы к ElectricityTariff-моделям.
    electricity_tariffs: Dict[str, ElectricityTariff] = Field(
        default_factory=lambda: {
            "Бытовой": {"cost_per_kwh": 0.10, "unlock_price": 0},
            "Промышленный": {"cost_per_kwh": 0.07, "unlock_price": 5_000},
            "Зеленый": {"cost_per_kwh": 0.05, "unlock_price": 25_000},
        }
    )


# ----------------------------- Logging / Telemetry (доп.) ---------------------

class LoggingConfig(BaseModel):
    """
    Дополнительная секция для гибкого логирования (необязательно).
    Если в коде не используется — просто игнорируется.
    """
    model_config = ConfigDict(protected_namespaces=())

    json_enabled: bool = False
    # Префикс для структурированных логов, если нужен
    service_name: str = "ai-bot"
    # Список логгеров, которым повышаем уровень (например, отладка HTTP)
    debug_loggers: List[str] = []


# ----------------------------- Settings (root) --------------------------------

class Settings(BaseSettings):
    """
    Главный контейнер настроек. Все значения читаются из .env / окружения.
    Используем env_nested_delimiter='__', чтобы прокидывать вложенные поля.
    """
    # --- обязательные ключи/URL ---
    BOT_TOKEN: SecretStr
    REDIS_URL: RedisDsn
    GEMINI_API_KEY: SecretStr

    # --- опциональные ключи провайдеров/сервисов ---
    OPENAI_API_KEY: Optional[SecretStr] = None
    COINGECKO_API_KEY: Optional[SecretStr] = None
    CRYPTOCOMPARE_API_KEY: Optional[SecretStr] = None

    # --- телеграм-идентификаторы ---
    admin_ids: Any = Field(alias="ADMIN_USER_IDS")
    ADMIN_CHAT_ID: Optional[int] = None
    NEWS_CHAT_ID: Optional[int] = None

    # --- процесс / хостинг ---
    IS_WEB_PROCESS: bool = False
    PORT: int = 10000

    # --- логирование ---
    log_level: str = "INFO"
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # --- доменные секции ---
    ai: AIConfig = Field(default_factory=AIConfig)
    throttling: ThrottlingConfig = Field(default_factory=ThrottlingConfig)
    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags)

    price_service: PriceServiceConfig = Field(default_factory=PriceServiceConfig)
    coin_list_service: CoinListServiceConfig = Field(default_factory=CoinListServiceConfig)
    news_service: NewsServiceConfig = Field(default_factory=NewsServiceConfig)
    endpoints: EndpointsConfig = Field(default_factory=EndpointsConfig)
    threat_filter: ThreatFilterConfig = Field(default_factory=ThreatFilterConfig)
    asic_service: AsicServiceConfig = Field(default_factory=AsicServiceConfig)
    crypto_center: CryptoCenterServiceConfig = Field(default_factory=CryptoCenterServiceConfig)
    quiz: QuizServiceConfig = Field(default_factory=QuizServiceConfig)
    events: MiningEventServiceConfig = Field(default_factory=MiningEventServiceConfig)
    achievements: AchievementServiceConfig = Field(default_factory=AchievementServiceConfig)
    market_data: MarketDataServiceConfig = Field(default_factory=MarketDataServiceConfig)
    game: MiningGameServiceConfig = Field(default_factory=MiningGameServiceConfig)

    # --- валидаторы ---

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> List[int]:
        """
        ADMIN_USER_IDS в .env:
          - "123,456,789"
          - либо JSON-массив [123,456]
        """
        if isinstance(v, list):
            try:
                return [int(x) for x in v]
            except Exception:
                raise TypeError("ADMIN_USER_IDS: список должен содержать целые числа.")
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            # Разрешаем как "1,2,3", так и с пробелами
            return [int(item.strip()) for item in s.split(",") if item.strip()]
        raise TypeError("ADMIN_USER_IDS должен быть строкой с ID через запятую или списком.")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",  # например: PRICE_SERVICE__CACHE_TTL_SECONDS=120
    )


# ----------------------------- load & announce --------------------------------

try:
    settings = Settings()
    # Базовое логирование поднимем сразу, чтобы видеть ранние сообщения
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    logging.info("Конфигурация успешно загружена и валидирована.")
except ValidationError as e:
    logging.critical(
        "КРИТИЧЕСКАЯ ОШИБКА ВАЛИДАЦИИ НАСТРОЕК. Проверьте .env и переменные окружения.\n%s",
        e,
    )
    raise SystemExit("Ошибки валидации конфигурации.")