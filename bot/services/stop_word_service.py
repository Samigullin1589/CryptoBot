# bot/services/stop_word_service.py
from typing import List, Set

from async_lru import alru_cache
from loguru import logger
from redis.asyncio import Redis

from bot.utils.keys import KeyFactory


class StopWordService:
    """
    Сервис управления стоп-словами.
    
    Предоставляет высокопроизводительный доступ к базе стоп-слов
    с использованием многоуровневого кэширования.
    
    Архитектура:
    - Redis как источник истины
    - In-memory LRU кэш для минимизации обращений к Redis
    - Автоматическая инвалидация кэша при изменениях
    """

    def __init__(self, redis: Redis):
        """
        Инициализирует сервис стоп-слов.
        
        Args:
            redis: Клиент Redis для хранения данных
        """
        self.redis = redis
        self.keys = KeyFactory
        
        logger.info("✅ Сервис StopWordService инициализирован.")

    @alru_cache(maxsize=1)
    async def get_stop_words_set(self) -> Set[str]:
        """
        Получает набор стоп-слов с кэшированием.
        
        Кэш автоматически сбрасывается при модификациях.
        
        Returns:
            Set[str]: Набор стоп-слов в нижнем регистре
        """
        try:
            words = await self.redis.smembers(self.keys.stop_words())
            
            if not words:
                logger.debug("📋 База стоп-слов пуста")
                return set()
            
            decoded_words = self._decode_words(words)
            logger.debug(f"✅ Загружено {len(decoded_words)} стоп-слов из Redis")
            
            return decoded_words
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения стоп-слов из Redis: {e}")
            return set()

    def _decode_words(self, words: Set[bytes]) -> Set[str]:
        """
        Декодирует набор байтовых строк в UTF-8.
        
        Args:
            words: Набор байтовых строк из Redis
            
        Returns:
            Set[str]: Набор декодированных строк
        """
        decoded = set()
        
        for word in words:
            try:
                if isinstance(word, bytes):
                    decoded.add(word.decode('utf-8'))
                else:
                    decoded.add(str(word))
            except UnicodeDecodeError as e:
                logger.warning(f"⚠️ Не удалось декодировать слово: {e}")
                continue
        
        return decoded

    def _normalize_word(self, word: str) -> str:
        """
        Нормализует слово для единообразного хранения.
        
        Args:
            word: Исходное слово
            
        Returns:
            str: Нормализованное слово (lowercase, trimmed)
        """
        return word.lower().strip()

    def _validate_word(self, word: str) -> bool:
        """
        Проверяет валидность слова перед операциями.
        
        Args:
            word: Слово для проверки
            
        Returns:
            bool: True если слово валидно
        """
        if not word or not word.strip():
            logger.warning("⚠️ Попытка операции с пустым словом")
            return False
        
        normalized = self._normalize_word(word)
        
        if len(normalized) < 2:
            logger.warning(f"⚠️ Слово слишком короткое: '{normalized}'")
            return False
        
        return True

    async def add_stop_word(self, word: str) -> bool:
        """
        Добавляет новое стоп-слово в базу.
        
        Args:
            word: Слово для добавления
            
        Returns:
            bool: True если слово добавлено, False если уже существует
        """
        if not self._validate_word(word):
            return False
        
        normalized_word = self._normalize_word(word)
        
        try:
            added_count = await self.redis.sadd(
                self.keys.stop_words(),
                normalized_word
            )
            
            if added_count > 0:
                logger.success(f"✅ Стоп-слово добавлено: '{normalized_word}'")
                self._invalidate_cache()
                return True
            
            logger.info(f"ℹ️ Стоп-слово уже существует: '{normalized_word}'")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления стоп-слова '{normalized_word}': {e}")
            return False

    async def remove_stop_word(self, word: str) -> bool:
        """
        Удаляет стоп-слово из базы.
        
        Args:
            word: Слово для удаления
            
        Returns:
            bool: True если слово удалено, False если не найдено
        """
        if not self._validate_word(word):
            return False
        
        normalized_word = self._normalize_word(word)
        
        try:
            removed_count = await self.redis.srem(
                self.keys.stop_words(),
                normalized_word
            )
            
            if removed_count > 0:
                logger.success(f"✅ Стоп-слово удалено: '{normalized_word}'")
                self._invalidate_cache()
                return True
            
            logger.warning(f"⚠️ Стоп-слово не найдено: '{normalized_word}'")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления стоп-слова '{normalized_word}': {e}")
            return False

    async def add_stop_words_bulk(self, words: List[str]) -> int:
        """
        Массово добавляет стоп-слова.
        
        Args:
            words: Список слов для добавления
            
        Returns:
            int: Количество успешно добавленных слов
        """
        if not words:
            return 0
        
        valid_words = [
            self._normalize_word(word)
            for word in words
            if self._validate_word(word)
        ]
        
        if not valid_words:
            logger.warning("⚠️ Нет валидных слов для добавления")
            return 0
        
        try:
            added_count = await self.redis.sadd(
                self.keys.stop_words(),
                *valid_words
            )
            
            logger.success(f"✅ Массово добавлено {added_count} стоп-слов")
            self._invalidate_cache()
            
            return added_count
            
        except Exception as e:
            logger.error(f"❌ Ошибка массового добавления стоп-слов: {e}")
            return 0

    async def contains_stop_word(self, word: str) -> bool:
        """
        Проверяет наличие слова в базе стоп-слов.
        
        Args:
            word: Слово для проверки
            
        Returns:
            bool: True если слово является стоп-словом
        """
        if not self._validate_word(word):
            return False
        
        normalized_word = self._normalize_word(word)
        stop_words = await self.get_stop_words_set()
        
        return normalized_word in stop_words

    async def get_all_stop_words_list(self) -> List[str]:
        """
        Возвращает отсортированный список всех стоп-слов.
        
        Returns:
            List[str]: Список стоп-слов по алфавиту
        """
        words_set = await self.get_stop_words_set()
        return sorted(list(words_set))

    async def get_stop_words_count(self) -> int:
        """
        Возвращает количество стоп-слов в базе.
        
        Returns:
            int: Количество стоп-слов
        """
        try:
            count = await self.redis.scard(self.keys.stop_words())
            return count
        except Exception as e:
            logger.error(f"❌ Ошибка получения количества стоп-слов: {e}")
            return 0

    async def clear_all_stop_words(self) -> bool:
        """
        Удаляет все стоп-слова из базы.
        
        ВНИМАНИЕ: Необратимая операция!
        
        Returns:
            bool: True если успешно очищено
        """
        try:
            await self.redis.delete(self.keys.stop_words())
            logger.warning("⚠️ Все стоп-слова удалены из базы")
            self._invalidate_cache()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка очистки стоп-слов: {e}")
            return False

    def _invalidate_cache(self) -> None:
        """
        Принудительно сбрасывает кэш стоп-слов.
        
        Вызывается после любых модификаций базы.
        """
        try:
            self.get_stop_words_set.cache_clear()
            logger.debug("🔄 Кэш стоп-слов сброшен")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сброса кэша: {e}")