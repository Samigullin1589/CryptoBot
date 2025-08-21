# bot/services/stop_word_service.py
# Дата обновления: 21.08.2025
# Версия: 2.0.0
# Описание: Специализированный сервис для управления списком стоп-слов
# с кэшированием для высокой производительности.

from typing import List, Set

from async_lru import alru_cache
from loguru import logger
from redis.asyncio import Redis

from bot.utils.dependencies import get_redis_client
from bot.utils.keys import KeyFactory


class StopWordService:
    """
    Сервис, отвечающий за управление базой данных стоп-слов.
    Предоставляет CRUD-операции и кэшированный доступ к списку слов.
    """

    def __init__(self):
        """
        Инициализирует сервис, получая зависимости из централизованного источника.
        """
        self.redis: Redis = get_redis_client()
        self.keys = KeyFactory
        logger.info("Сервис StopWordService инициализирован.")

    @alru_cache(maxsize=1)
    async def get_stop_words_set(self) -> Set[str]:
        """
        Получает набор стоп-слов из Redis.
        Результат кэшируется в памяти для максимальной производительности.
        Кэш автоматически сбрасывается при добавлении/удалении слов.
        """
        try:
            words = await self.redis.smembers(self.keys.stop_words())
            # Декодируем байты в строки
            return {word.decode('utf-8') for word in words}
        except Exception as e:
            logger.exception(f"Не удалось получить стоп-слова из Redis: {e}")
            return set()

    async def add_stop_word(self, word: str) -> bool:
        """
        Добавляет новое стоп-слово в базу данных (в нижнем регистре).
        Сбрасывает in-memory кэш для обеспечения актуальности данных.

        :param word: Слово для добавления.
        :return: True, если слово было успешно добавлено, False - если оно уже существовало или является пустым.
        """
        normalized_word = word.lower().strip()
        if not normalized_word:
            return False
        
        try:
            # SADD возвращает 1, если элемент был добавлен, и 0, если уже существовал.
            added_count = await self.redis.sadd(self.keys.stop_words(), normalized_word)
            
            if added_count:
                logger.info(f"Стоп-слово '{normalized_word}' добавлено в базу.")
                # Принудительно сбрасываем кэш, так как данные изменились
                self.get_stop_words_set.cache_clear()
                return True
            
            logger.info(f"Стоп-слово '{normalized_word}' уже существует в базе.")
            return False
        except Exception as e:
            logger.exception(f"Ошибка при добавлении стоп-слова '{normalized_word}': {e}")
            return False

    async def remove_stop_word(self, word: str) -> bool:
        """
        Удаляет стоп-слово из базы данных.
        Сбрасывает in-memory кэш для обеспечения актуальности данных.

        :param word: Слово для удаления.
        :return: True, если слово было успешно удалено, False - если его не было в списке.
        """
        normalized_word = word.lower().strip()
        if not normalized_word:
            return False
            
        try:
            # SREM возвращает 1, если элемент был удален, и 0, если не найден.
            removed_count = await self.redis.srem(self.keys.stop_words(), normalized_word)
            
            if removed_count:
                logger.info(f"Стоп-слово '{normalized_word}' удалено из базы.")
                # Принудительно сбрасываем кэш
                self.get_stop_words_set.cache_clear()
                return True
            
            logger.warning(f"Попытка удалить несуществующее стоп-слово: '{normalized_word}'.")
            return False
        except Exception as e:
            logger.exception(f"Ошибка при удалении стоп-слова '{normalized_word}': {e}")
            return False

    async def get_all_stop_words_list(self) -> List[str]:
        """
        Возвращает текущий список всех стоп-слов, отсортированный по алфавиту.
        Использует кэшированный метод для получения данных.
        """
        words_set = await self.get_stop_words_set()
        return sorted(list(words_set))