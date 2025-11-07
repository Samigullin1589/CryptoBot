# bot/services/antispam_learning/cache.py
"""
Кэш для оптимизации производительности системы антиспама.
"""
import time
from typing import List, Optional

from loguru import logger


class SpamPhraseCache:
    """
    Локальный кэш топ спам-фраз.
    
    Уменьшает количество обращений к Redis путем локального кэширования
    наиболее частых спам-фраз с автоматическим обновлением.
    """
    
    # Константы
    DEFAULT_TTL = 300  # 5 минут
    MIN_TTL = 60  # Минимум 1 минута
    MAX_TTL = 3600  # Максимум 1 час
    
    def __init__(self, ttl_seconds: int = DEFAULT_TTL):
        """
        Инициализирует кэш фраз.
        
        Args:
            ttl_seconds: Время жизни кэша в секундах
        
        Raises:
            ValueError: Если TTL вне допустимого диапазона
        """
        if not self.MIN_TTL <= ttl_seconds <= self.MAX_TTL:
            raise ValueError(
                f"TTL должен быть в диапазоне "
                f"[{self.MIN_TTL}, {self.MAX_TTL}] секунд"
            )
        
        self._phrases: List[str] = []
        self._expiry_time: float = 0.0
        self._ttl_seconds = ttl_seconds
        self._hit_count = 0
        self._miss_count = 0
        
        logger.debug(f"🔧 SpamPhraseCache инициализирован (TTL: {ttl_seconds}s)")
    
    def get(self) -> Optional[List[str]]:
        """
        Получает закэшированные фразы если кэш валиден.
        
        Returns:
            Список фраз или None если кэш устарел
        """
        if self.is_valid():
            self._hit_count += 1
            logger.debug(
                f"✅ Cache HIT: {len(self._phrases)} фраз "
                f"(hits: {self._hit_count}, misses: {self._miss_count})"
            )
            # Возвращаем копию для защиты от модификации
            return self._phrases.copy()
        
        self._miss_count += 1
        logger.debug(
            f"❌ Cache MISS "
            f"(hits: {self._hit_count}, misses: {self._miss_count})"
        )
        return None
    
    def set(self, phrases: List[str]) -> None:
        """
        Сохраняет фразы в кэш.
        
        Args:
            phrases: Список фраз для кэширования
        """
        if not phrases:
            logger.warning("⚠️ Попытка кэширования пустого списка фраз")
            return
        
        self._phrases = phrases.copy()
        self._expiry_time = time.monotonic() + self._ttl_seconds
        
        logger.info(
            f"📦 Кэш обновлен: {len(phrases)} фраз, "
            f"истекает через {self._ttl_seconds}s"
        )
    
    def is_valid(self) -> bool:
        """
        Проверяет валидность кэша.
        
        Returns:
            True если кэш актуален и не пуст
        """
        has_data = bool(self._phrases)
        not_expired = time.monotonic() < self._expiry_time
        
        return has_data and not_expired
    
    def invalidate(self) -> None:
        """Принудительно инвалидирует кэш."""
        phrases_count = len(self._phrases)
        self._expiry_time = 0.0
        self._phrases = []
        
        logger.info(f"🔄 Кэш инвалидирован ({phrases_count} фраз удалено)")
    
    def get_hit_rate(self) -> float:
        """
        Вычисляет hit rate кэша.
        
        Returns:
            Hit rate в процентах (0-100)
        """
        total = self._hit_count + self._miss_count
        if total == 0:
            return 0.0
        
        return (self._hit_count / total) * 100
    
    def size(self) -> int:
        """Возвращает размер кэша."""
        return len(self._phrases)
    
    def get_ttl_remaining(self) -> float:
        """
        Возвращает оставшееся время жизни кэша.
        
        Returns:
            Секунды до истечения (или 0 если истек)
        """
        remaining = self._expiry_time - time.monotonic()
        return max(0.0, remaining)
    
    def get_stats(self) -> dict:
        """
        Возвращает статистику кэша.
        
        Returns:
            Словарь со статистикой
        """
        return {
            "size": self.size(),
            "valid": self.is_valid(),
            "hits": self._hit_count,
            "misses": self._miss_count,
            "hit_rate": self.get_hit_rate(),
            "ttl_remaining": self.get_ttl_remaining(),
        }