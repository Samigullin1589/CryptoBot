# bot/services/ai/providers/base.py
"""
Базовый абстрактный класс для AI провайдеров.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseAIProvider(ABC):
    """
    Базовый класс для всех AI провайдеров.
    
    Определяет единый интерфейс для работы с различными LLM API.
    """
    
    @abstractmethod
    def get_name(self) -> str:
        """Возвращает название провайдера."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Проверяет доступность провайдера."""
        pass
    
    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Генерирует текстовый ответ.
        
        Args:
            prompt: Запрос пользователя
            system_prompt: Системный промпт
            temperature: Температура генерации
        
        Returns:
            Сгенерированный текст
        """
        pass
    
    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        json_schema: Dict[str, Any],
        temperature: float = 0.7
    ) -> str:
        """
        Генерирует JSON ответ.
        
        Args:
            prompt: Запрос с описанием требуемой структуры
            json_schema: Схема JSON
            temperature: Температура генерации
        
        Returns:
            JSON строка
        """
        pass