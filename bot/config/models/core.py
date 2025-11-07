# bot/config/models/core.py
from typing import List

from pydantic import BaseModel, ConfigDict


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


class LoggingConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    json_enabled: bool = False
    service_name: str = "ai-bot"
    debug_loggers: List[str] = []