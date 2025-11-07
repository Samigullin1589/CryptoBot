# bot/config/settings.py
import logging
from typing import Any, List, Optional

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bot.config.models import (
    AIConfig,
    AchievementServiceConfig,
    AsicServiceConfig,
    CoinListServiceConfig,
    CryptoCenterServiceConfig,
    EndpointsConfig,
    FeatureFlags,
    LoggingConfig,
    MarketDataServiceConfig,
    MiningEventServiceConfig,
    MiningGameServiceConfig,
    NewsServiceConfig,
    PriceServiceConfig,
    QuizServiceConfig,
    ThreatFilterConfig,
    ThrottlingConfig,
)


class Settings(BaseSettings):
    BOT_TOKEN: SecretStr
    REDIS_URL: str

    GEMINI_API_KEY: Optional[SecretStr] = None
    OPENAI_API_KEY: Optional[SecretStr] = None
    COINGECKO_API_KEY: Optional[SecretStr] = None
    CRYPTOCOMPARE_API_KEY: Optional[SecretStr] = None

    admin_ids: Any = Field(alias="ADMIN_IDS")
    ADMIN_CHAT_ID: Optional[int] = None
    NEWS_CHAT_ID: Optional[int] = None

    IS_WEB_PROCESS: bool = False
    PORT: int = 10000

    log_level: str = "INFO"
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

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

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_dsn(cls, v: Any) -> str:
        if isinstance(v, str) and not v.startswith(("redis://", "rediss://", "unix://")):
            return f"redis://{v}"
        return v

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> List[int]:
        if isinstance(v, list):
            try:
                return [int(x) for x in v]
            except Exception:
                raise TypeError("ADMIN_IDS: список должен содержать целые числа.")
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            return [int(item.strip()) for item in s.split(",") if item.strip()]
        raise TypeError("ADMIN_IDS должен быть строкой с ID через запятую или списком.")

    @property
    def bot_token(self) -> str:
        return self.BOT_TOKEN.get_secret_value()

    @property
    def redis_url(self) -> str:
        return self.REDIS_URL

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )


try:
    settings = Settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    logging.info("✅ Конфигурация успешно загружена и валидирована.")
except ValidationError as e:
    logging.critical(
        "❌ КРИТИЧЕСКАЯ ОШИБКА ВАЛИДАЦИИ НАСТРОЕК. Проверьте .env и переменные окружения.\n%s",
        e,
    )
    raise SystemExit("Ошибки валидации конфигурации.")