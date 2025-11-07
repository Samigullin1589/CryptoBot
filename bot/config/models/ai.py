# bot/config/models/ai.py
from pydantic import BaseModel, ConfigDict


class AIConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider: str = "openai"

    model_name: str = "gemini-1.5-pro-latest"
    flash_model_name: str = "gemini-1.5-flash-latest"

    openai_model: str = "gpt-4o-mini"

    default_temperature: float = 0.5
    max_retries: int = 5
    history_max_size: int = 10

    request_timeout: int = 30