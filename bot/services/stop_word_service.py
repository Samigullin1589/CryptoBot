# ===============================================================
# Файл: bot/services/stop_word_service.py (НОВЫЙ ФАЙЛ)
# Описание: Специализированный сервис для управления списком
# стоп-слов. Выделен из AIService для соответствия принципу
# единой ответственности.
# ===============================================================

import logging

import redis.asyncio as redis
from async_lru import alru_cache

logger = logging.getLogger(__name__)


class StopWordService:
    """
    Сервис, отвечающий за управление базой данных стоп-слов.
    """

    def __init__(self, redis_client: redis.Redis):
        """
        Инициализирует сервис.
        :param redis_client: Асинхронный клиент для Redis.
        """
        self.redis = redis_client
        self.stop_words_key = "antispam:stop_words"

    @alru_cache(maxsize=1)
    async def get_stop_words(self) -> set[str]:
        """
        Получает набор стоп-слов из Redis. Результат кешируется для производительности.
        """
        try:
            words = await self.redis.smembers(self.stop_words_key)
            return {word.decode("utf-8") for word in words}
        except Exception as e:
            logger.error(f"Failed to get stop words from Redis: {e}")
            return set()

    async def add_stop_word(self, word: str) -> bool:
        """
        Добавляет новое стоп-слово в базу данных.
        Возвращает True, если слово было добавлено, False - если уже существовало.
        """
        word = word.lower().strip()
        if not word:
            return False

        # Сбрасываем кеш, чтобы при следующем вызове получить актуальный список
        self.get_stop_words.cache_clear()

        added_count = await self.redis.sadd(self.stop_words_key, word)
        logger.info(
            f"Stop word '{word}' was {'added' if added_count else 'already present'}."
        )
        return bool(added_count)

    async def remove_stop_word(self, word: str) -> bool:
        """
        Удаляет стоп-слово из базы данных.
        Возвращает True, если слово было удалено, False - если его не было в списке.
        """
        word = word.lower().strip()
        if not word:
            return False

        self.get_stop_words.cache_clear()

        removed_count = await self.redis.srem(self.stop_words_key, word)
        logger.info(
            f"Stop word '{word}' was {'removed' if removed_count else 'not found'}."
        )
        return bool(removed_count)

    async def get_all_stop_words(self) -> list[str]:
        """Возвращает текущий список всех стоп-слов, отсортированный по алфавиту."""
        words_set = await self.get_stop_words()
        return sorted(list(words_set))
