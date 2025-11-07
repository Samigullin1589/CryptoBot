# bot/config/models/security.py
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class ThreatFilterConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    enabled: bool = True
    toxicity_threshold: float = 0.75

    warn_threshold: int = 1
    mute_threshold: int = 2
    ban_threshold: int = 3

    window_seconds: int = 21600
    mute_seconds: int = 3600

    deny_domains: List[str] = Field(default_factory=list)
    allow_domains: List[str] = Field(default_factory=list)