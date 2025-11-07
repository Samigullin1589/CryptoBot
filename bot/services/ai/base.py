# bot/services/ai/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AIProvider(ABC):
    @abstractmethod
    async def generate_text(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        pass

    @abstractmethod
    async def generate_json(
        self, 
        prompt: str, 
        json_schema: Dict[str, Any],
        temperature: float = 0.1
    ) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass