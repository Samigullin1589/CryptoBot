# bot/services/image_guard/service.py
"""
Главный сервис защиты от спам-изображений.
"""
import asyncio
import io
from typing import Optional

from aiogram import Bot
from aiogram.types import Message
from loguru import logger
from PIL import Image
from redis.asyncio import Redis

from bot.services.image_guard.downloader import ImageDownloader
from bot.services.image_guard.hash_database import SpamHashDatabase
from bot.services.image_guard.hasher import ImageHasher
from bot.services.image_guard.text_analyzer import SpamTextAnalyzer
from bot.services.image_guard.violation_tracker import ViolationTracker
from bot.utils.models import ImageVerdict


class ImageGuardService:
    """
    Сервис многоуровневой защиты от спам-изображений.
    
    Архитектура:
    ┌────────────────────────────────────┐
    │  ImageGuardService (Фасад)        │
    └────────────────────────────────────┘
              ↓          ↓          ↓
    ┌──────────────┐ ┌──────────┐ ┌────────────────┐
    │ Hasher       │ │ Downloader│ │ Text Analyzer │
    │ (dHash)      │ │ (Telegram)│ │ (Patterns)    │
    └──────────────┘ └──────────┘ └────────────────┘
              ↓                    ↓
    ┌─────────────────────┐ ┌──────────────────┐
    │ Hash Database       │ │ Violation Tracker│
    │ (Redis Buckets)     │ │ (Escalation)     │
    └─────────────────────┘ └──────────────────┘
    
    Функции:
    - Перцептивное хэширование (dHash)
    - База дубликатов с bucketing
    - Анализ текста на спам-паттерны
    - OCR через Vision API (опционально)
    - Система эскалации наказаний
    """
    
    def __init__(
        self,
        redis: Redis,
        vision_service: Optional[any] = None
    ):
        """
        Инициализирует сервис защиты от спам-изображений.
        
        Args:
            redis: Клиент Redis
            vision_service: Опциональный сервис для OCR
        """
        self.redis = redis
        self.vision_service = vision_service
        
        # Инициализируем компоненты
        self.hasher = ImageHasher()
        self.text_analyzer = SpamTextAnalyzer()
        self.hash_db = SpamHashDatabase(redis)
        self.violation_tracker = ViolationTracker(redis)
        
        # Downloader будет установлен через set_bot()
        self.downloader: Optional[ImageDownloader] = None
        
        logger.success("✅ Сервис ImageGuardService инициализирован")
    
    def set_bot(self, bot: Bot) -> None:
        """
        Устанавливает экземпляр бота для загрузки изображений.
        
        Args:
            bot: Экземпляр Telegram бота
        """
        self.downloader = ImageDownloader(bot)
        logger.info("✅ Bot установлен для ImageGuardService")
    
    async def check_message_with_photo(self, message: Message) -> ImageVerdict:
        """
        Проверяет сообщение с фото на спам.
        
        Алгоритм:
        1. Проверка наличия фото
        2. Скачивание изображения
        3. Вычисление хэша
        4. Проверка по базе дубликатов
        5. Извлечение и анализ текста
        6. Определение наказания
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            ImageVerdict с решением о действии
        """
        # Проверка предусловий
        if not self._has_photo(message):
            return ImageVerdict(action="allow")
        
        if not message.from_user:
            logger.debug("Сообщение без пользователя, пропуск")
            return ImageVerdict(action="allow")
        
        if not self.downloader:
            logger.warning("⚠️ Bot не установлен, пропускаем проверку")
            return ImageVerdict(action="allow")
        
        # Скачиваем изображение
        img_bytes = await self.downloader.download_photo(message)
        
        if not img_bytes:
            logger.debug("Не удалось скачать изображение")
            return ImageVerdict(action="allow", reason="download_failed")
        
        # Вычисляем хэш
        image_hash = await self._compute_hash(img_bytes)
        
        if image_hash is None:
            logger.warning("Не удалось вычислить хэш")
            return ImageVerdict(action="allow", reason="hash_failed")
        
        # Проверяем по базе дубликатов
        is_duplicate, dup_reason = await self.hash_db.is_spam_hash(image_hash)
        
        if is_duplicate:
            logger.warning(f"🚨 Обнаружен дубликат спам-изображения: {dup_reason}")
            return await self._escalate_punishment(message, dup_reason)
        
        # Извлекаем и анализируем текст
        text = await self._extract_text(message, img_bytes)
        
        if self.text_analyzer.is_spam(text):
            logger.warning("🚨 Обнаружен спам в тексте изображения")
            
            # Добавляем хэш в базу для будущих проверок
            await self.hash_db.add_spam_hash(image_hash)
            
            return await self._escalate_punishment(message, "suspicious_text")
        
        # Все проверки пройдены
        return ImageVerdict(action="allow")
    
    async def mark_photo_as_spam(self, message: Message) -> str:
        """
        Помечает изображение как спам (админская функция).
        
        Args:
            message: Сообщение с изображением
            
        Returns:
            Сообщение о результате операции
        """
        if not self.downloader:
            return "❌ Бот не инициализирован"
        
        if not self._has_photo(message):
            return "❌ В сообщении нет изображения"
        
        # Скачиваем изображение
        img_bytes = await self.downloader.download_photo(message)
        
        if not img_bytes:
            return "❌ Не удалось скачать изображение"
        
        # Вычисляем хэш
        image_hash = await self._compute_hash(img_bytes)
        
        if image_hash is None:
            return "❌ Не удалось вычислить хэш"
        
        # Добавляем в базу
        success = await self.hash_db.add_spam_hash(image_hash)
        
        if success:
            return f"✅ Изображение добавлено в базу спама (hash: {image_hash})"
        
        return "❌ Ошибка добавления в базу"
    
    @staticmethod
    def _has_photo(message: Message) -> bool:
        """
        Проверяет наличие фото в сообщении.
        
        Args:
            message: Сообщение
            
        Returns:
            True если есть фото
        """
        return ImageDownloader.has_photo(message)
    
    async def _compute_hash(self, img_bytes: bytes) -> Optional[int]:
        """
        Вычисляет хэш изображения в отдельном потоке.
        
        Args:
            img_bytes: Байты изображения
            
        Returns:
            Хэш или None при ошибке
        """
        try:
            # Открываем изображение
            image = Image.open(io.BytesIO(img_bytes))
            
            # Вычисляем хэш в thread pool (CPU-intensive)
            hash_value = await asyncio.to_thread(
                self.hasher.compute_dhash,
                image
            )
            
            return hash_value
            
        except Exception as e:
            logger.error(f"❌ Ошибка вычисления хэша: {e}", exc_info=True)
            return None
    
    async def _extract_text(self, message: Message, img_bytes: bytes) -> str:
        """
        Извлекает текст из сообщения и изображения (OCR).
        
        Args:
            message: Сообщение
            img_bytes: Байты изображения
            
        Returns:
            Объединенный текст
        """
        text_parts = []
        
        # Текст из подписи
        if message.caption:
            text_parts.append(message.caption.strip())
        
        # OCR через Vision API
        if self.vision_service:
            try:
                ocr_result = await self.vision_service.extract_text(img_bytes)
                
                if ocr_result and ocr_result.strip():
                    text_parts.append(ocr_result)
                    logger.debug(f"📝 OCR извлек {len(ocr_result)} символов")
            
            except Exception as e:
                logger.warning(f"⚠️ Ошибка OCR: {e}")
        
        combined_text = "\n".join(text_parts)
        
        if combined_text:
            logger.debug(f"📝 Извлечен текст: {len(combined_text)} символов")
        
        return combined_text
    
    async def _escalate_punishment(
        self,
        message: Message,
        reason: str
    ) -> ImageVerdict:
        """
        Определяет наказание на основе истории нарушений.
        
        Args:
            message: Сообщение нарушителя
            reason: Причина нарушения
            
        Returns:
            ImageVerdict с решением о наказании
        """
        if not message.from_user:
            return ImageVerdict("delete", reason)
        
        # Увеличиваем счетчик нарушений
        violations = await self.violation_tracker.increment_violations(
            message.from_user.id
        )
        
        # Определяем наказание
        verdict = self.violation_tracker.get_punishment(violations, reason)
        
        logger.info(
            f"⚖️ Вердикт для user_id={message.from_user.id}: "
            f"action={verdict.action}, violations={violations}"
        )
        
        return verdict
    
    async def get_user_violations(self, user_id: int) -> int:
        """Получает количество нарушений пользователя."""
        return await self.violation_tracker.get_violations(user_id)
    
    async def reset_user_violations(self, user_id: int) -> bool:
        """Сбрасывает нарушения пользователя (для админов)."""
        return await self.violation_tracker.reset_violations(user_id)