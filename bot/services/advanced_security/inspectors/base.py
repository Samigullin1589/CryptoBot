# bot/services/advanced_security/inspectors/base.py
"""
Базовый класс для всех инспекторов.
"""
from abc import ABC, abstractmethod
from typing import Any

from bot.services.advanced_security.models import InspectionResult


class BaseInspector(ABC):
    """
    Базовый класс для инспекторов безопасности.
    
    Каждый инспектор анализирует определенный аспект сообщения
    и возвращает результат проверки с оценкой угрозы.
    """
    
    def __init__(self, config: Any):
        """
        Инициализация инспектора.
        
        Args:
            config: Конфигурация безопасности
        """
        self.config = config
    
    @abstractmethod
    async def inspect(self, *args, **kwargs) -> InspectionResult:
        """
        Выполняет проверку.
        
        Returns:
            Результат проверки с оценкой и причинами
        """
        pass