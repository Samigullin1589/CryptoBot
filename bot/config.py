import logging
from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    """
    Класс конфигурации приложения.
    Использует Pydantic для чтения и валидации переменных из .env файла или окружения.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    bot_token: str = Field(..., alias="BOT_TOKEN")
    redis_url: RedisDsn = Field("redis://localhost:6379/0", alias="REDIS_URL")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    @property
    def logging_level(self) -> int:
        """
        Возвращает числовой уровень логирования для стандартной библиотеки logging.
        """
        return logging.getLevelName(self.log_level.upper())

app_config = AppConfig()