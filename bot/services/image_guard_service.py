# bot/services/image_guard_service.py
import asyncio
import io
import re
from typing import Optional, Tuple

from aiogram import Bot
from aiogram.types import Message
from loguru import logger
from PIL import Image, ImageOps
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.utils.keys import KeyFactory
from bot.utils.models import ImageVerdict


class ImageHasher:
    """
    Компонент для вычисления перцептивных хэшей изображений.
    
    Использует алгоритм dHash для создания устойчивых к изменениям хэшей.
    """
    
    @staticmethod
    def compute_dhash(image: Image.Image) -> int:
        """
        Вычисляет 64-битный перцептивный dHash.
        
        Args:
            image: PIL изображение
            
        Returns:
            int: 64-битный хэш
        """
        img = ImageOps.exif_transpose(image.convert("L"))
        img = img.resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(img.getdata())
        
        hash_val = 0
        for row in range(8):
            for col in range(8):
                left = pixels[row * 9 + col]
                right = pixels[row * 9 + col + 1]
                hash_val = (hash_val << 1) | (1 if left > right else 0)
        
        return hash_val
    
    @staticmethod
    def hamming_distance(hash1: int, hash2: int) -> int:
        """
        Вычисляет расстояние Хэмминга между хэшами.
        
        Args:
            hash1: Первый хэш
            hash2: Второй хэш
            
        Returns:
            int: Количество различающихся битов
        """
        return (hash1 ^ hash2).bit_count()


class ImageDownloader:
    """
    Компонент для скачивания изображений из Telegram.
    """
    
    def __init__(self, bot: Bot):
        """
        Инициализирует загрузчик изображений.
        
        Args:
            bot: Экземпляр Telegram бота
        """
        self.bot = bot
    
    async def download_photo(self, message: Message) -> Optional[bytes]:
        """
        Скачивает изображение из сообщения.
        
        Args:
            message: Сообщение с фото или документом
            
        Returns:
            Optional[bytes]: Байты изображения или None при ошибке
        """
        photo_size = self._get_photo_size(message)
        
        if not photo_size:
            return None
        
        try:
            buffer = io.BytesIO()
            await self.bot.download(photo_size, destination=buffer)
            return buffer.getvalue()
        except Exception as e:
            logger.error(f"❌ Ошибка скачивания фото file_id={photo_size.file_id}: {e}")
            return None
    
    @staticmethod
    def _get_photo_size(message: Message):
        """
        Извлекает объект фото из сообщения.
        
        Args:
            message: Сообщение
            
        Returns:
            PhotoSize или Document с изображением
        """
        if message.photo:
            return max(message.photo, key=lambda p: p.file_size or 0)
        
        if message.document and message.document.mime_type:
            if "image" in message.document.mime_type:
                return message.document
        
        return None


class SpamTextAnalyzer:
    """
    Компонент для анализа текста на спам-признаки.
    """
    
    def __init__(self):
        """Инициализирует анализатор текста."""
        self.config = settings.security
        self._spam_pattern = self._compile_spam_pattern()
    
    def _compile_spam_pattern(self) -> re.Pattern:
        """
        Компилирует регулярное выражение для поиска спам-паттернов.
        
        Returns:
            re.Pattern: Скомпилированное выражение
        """
        patterns = getattr(self.config, 'image_spam_patterns', [])
        
        if not patterns:
            patterns = [
                r'заработ[ок]',
                r'пассивн[ыо][йе]?\s+доход',
                r'легк[ие][е]?\s+деньг[и]',
                r'миллион',
                r'крипт[оа]валют',
            ]
        
        return re.compile("|".join(patterns), re.IGNORECASE)
    
    def is_spam(self, text: str) -> bool:
        """
        Проверяет текст на спам-признаки.
        
        Args:
            text: Текст для анализа
            
        Returns:
            bool: True если текст похож на спам
        """
        if not text or not text.strip():
            return False
        
        if self._spam_pattern.search(text):
            return True
        
        return self._check_spam_heuristics(text)
    
    def _check_spam_heuristics(self, text: str) -> bool:
        """
        Применяет эвристические правила для определения спама.
        
        Args:
            text: Текст для анализа
            
        Returns:
            bool: True если обнаружены признаки спама
        """
        money_marks = len(re.findall(r"[💰💵🪙\$€₽₿₮]", text))
        links = len(re.findall(r"https?://|t\.me/", text, re.IGNORECASE))
        mentions = len(re.findall(r"@\w{4,}", text))
        
        score = (money_marks * 2) + (links * 1.5) + mentions
        
        threshold = getattr(self.config, 'image_text_spam_score', 5)
        
        return score >= threshold


class SpamHashDatabase:
    """
    Компонент для работы с базой хэшей спам-изображений в Redis.
    """
    
    def __init__(self, redis: Redis):
        """
        Инициализирует базу данных хэшей.
        
        Args:
            redis: Клиент Redis
        """
        self.redis = redis
        self.keys = KeyFactory
        self.config = settings.security
        self.hasher = ImageHasher()
    
    async def is_spam_hash(self, image_hash: int) -> Tuple[bool, str]:
        """
        Проверяет хэш на совпадение с известными спам-хэшами.
        
        Args:
            image_hash: Хэш изображения
            
        Returns:
            Tuple[bool, str]: (является_спамом, причина)
        """
        try:
            prefix_bits = getattr(self.config, 'phash_prefix_bits', 16)
            prefix = image_hash >> (64 - prefix_bits)
            bucket_key = self.keys.image_hash_bucket(prefix)
            
            candidate_hashes = await self.redis.smembers(bucket_key)
            
            if not candidate_hashes:
                return False, "no_matches"
            
            distance_threshold = getattr(self.config, 'phash_distance', 5)
            
            for ch_str in candidate_hashes:
                try:
                    candidate_hash = int(ch_str)
                    distance = self.hasher.hamming_distance(image_hash, candidate_hash)
                    
                    if distance <= distance_threshold:
                        return True, f"similar_hash(dist={distance})"
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ Некорректный хэш в базе: {ch_str}")
                    continue
            
            return False, "no_similar_hashes"
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки хэша в Redis: {e}")
            return False, "redis_error"
    
    async def add_spam_hash(self, image_hash: int) -> bool:
        """
        Добавляет хэш в базу спам-изображений.
        
        Args:
            image_hash: Хэш для добавления
            
        Returns:
            bool: True если успешно добавлено
        """
        try:
            prefix_bits = getattr(self.config, 'phash_prefix_bits', 16)
            ttl_seconds = getattr(self.config, 'phash_ttl_seconds', 2592000)
            
            prefix = image_hash >> (64 - prefix_bits)
            bucket_key = self.keys.image_hash_bucket(prefix)
            
            pipe = self.redis.pipeline()
            pipe.sadd(bucket_key, str(image_hash))
            pipe.expire(bucket_key, ttl_seconds)
            await pipe.execute()
            
            logger.success(f"✅ Хэш {image_hash} добавлен в базу спама")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления хэша {image_hash}: {e}")
            return False


class ViolationTracker:
    """
    Компонент для отслеживания нарушений пользователей.
    """
    
    def __init__(self, redis: Redis):
        """
        Инициализирует трекер нарушений.
        
        Args:
            redis: Клиент Redis
        """
        self.redis = redis
        self.keys = KeyFactory
        self.config = settings.security
    
    async def increment_violations(self, user_id: int) -> int:
        """
        Увеличивает счетчик нарушений пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            int: Текущее количество нарушений
        """
        try:
            key = self.keys.user_spam_image_count(user_id)
            violations = await self.redis.incr(key)
            
            window_seconds = getattr(self.config, 'window_seconds', 86400)
            await self.redis.expire(key, window_seconds)
            
            return violations
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления счетчика для user {user_id}: {e}")
            return 1
    
    def get_punishment(self, violations: int, reason: str) -> ImageVerdict:
        """
        Определяет наказание на основе количества нарушений.
        
        Args:
            violations: Количество нарушений
            reason: Причина нарушения
            
        Returns:
            ImageVerdict: Решение о наказании
        """
        ban_threshold = getattr(self.config, 'image_spam_autoban_threshold', 3)
        
        if violations >= ban_threshold:
            return ImageVerdict(
                action="ban",
                reason=f"{reason} (нарушение #{violations})"
            )
        
        return ImageVerdict(
            action="delete",
            reason=f"{reason} (нарушение #{violations})"
        )


class ImageGuardService:
    """
    Сервис многоуровневой защиты от спам-изображений.
    
    Использует:
    - Перцептивное хэширование для определения дубликатов
    - Анализ текста на спам-паттерны
    - Систему эскалации наказаний
    """
    
    def __init__(
        self,
        redis: Redis,
        vision_service: Optional['ImageVisionService'] = None
    ):
        """
        Инициализирует сервис защиты от спам-изображений.
        
        Args:
            redis: Клиент Redis
            vision_service: Опциональный сервис для OCR
        """
        self.redis = redis
        self.vision_service = vision_service
        
        self.hasher = ImageHasher()
        self.text_analyzer = SpamTextAnalyzer()
        self.hash_db = SpamHashDatabase(redis)
        self.violation_tracker = ViolationTracker(redis)
        
        logger.info("✅ Сервис ImageGuardService инициализирован.")
    
    def set_bot(self, bot: Bot) -> None:
        """
        Устанавливает экземпляр бота для загрузки изображений.
        
        Args:
            bot: Экземпляр Telegram бота
        """
        self.downloader = ImageDownloader(bot)
    
    async def check_message_with_photo(self, message: Message) -> ImageVerdict:
        """
        Проверяет сообщение с фото на спам.
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            ImageVerdict: Решение о действии
        """
        if not self._has_photo(message):
            return ImageVerdict(action="allow")
        
        if not message.from_user:
            return ImageVerdict(action="allow")
        
        if not hasattr(self, 'downloader'):
            logger.warning("⚠️ Bot не установлен, пропускаем проверку")
            return ImageVerdict(action="allow")
        
        img_bytes = await self.downloader.download_photo(message)
        
        if not img_bytes:
            return ImageVerdict(action="allow", reason="download_failed")
        
        image_hash = await self._compute_hash(img_bytes)
        
        if image_hash is None:
            return ImageVerdict(action="allow", reason="hash_failed")
        
        is_spam, reason = await self.hash_db.is_spam_hash(image_hash)
        
        if is_spam:
            return await self._escalate_punishment(message, reason)
        
        text = await self._extract_text(message, img_bytes)
        
        if self.text_analyzer.is_spam(text):
            await self.hash_db.add_spam_hash(image_hash)
            return await self._escalate_punishment(message, "suspicious_text")
        
        return ImageVerdict(action="allow")
    
    async def mark_photo_as_spam(self, message: Message) -> str:
        """
        Помечает изображение как спам (админская функция).
        
        Args:
            message: Сообщение с изображением
            
        Returns:
            str: Результат операции
        """
        if not hasattr(self, 'downloader'):
            return "❌ Бот не инициализирован"
        
        img_bytes = await self.downloader.download_photo(message)
        
        if not img_bytes:
            return "❌ Не удалось скачать изображение"
        
        image_hash = await self._compute_hash(img_bytes)
        
        if image_hash is None:
            return "❌ Не удалось вычислить хэш"
        
        success = await self.hash_db.add_spam_hash(image_hash)
        
        if success:
            return "✅ Изображение добавлено в базу спама"
        
        return "❌ Ошибка добавления в базу"
    
    @staticmethod
    def _has_photo(message: Message) -> bool:
        """
        Проверяет наличие фото в сообщении.
        
        Args:
            message: Сообщение
            
        Returns:
            bool: True если есть фото
        """
        if message.photo:
            return True
        
        if message.document and message.document.mime_type:
            return "image" in message.document.mime_type
        
        return False
    
    async def _compute_hash(self, img_bytes: bytes) -> Optional[int]:
        """
        Вычисляет хэш изображения.
        
        Args:
            img_bytes: Байты изображения
            
        Returns:
            Optional[int]: Хэш или None при ошибке
        """
        try:
            image = Image.open(io.BytesIO(img_bytes))
            return await asyncio.to_thread(self.hasher.compute_dhash, image)
        except Exception as e:
            logger.error(f"❌ Ошибка вычисления хэша: {e}")
            return None
    
    async def _extract_text(self, message: Message, img_bytes: bytes) -> str:
        """
        Извлекает текст из сообщения и изображения.
        
        Args:
            message: Сообщение
            img_bytes: Байты изображения
            
        Returns:
            str: Объединенный текст
        """
        text_parts = []
        
        if message.caption:
            text_parts.append(message.caption.strip())
        
        if self.vision_service:
            try:
                ocr_result = await self.vision_service.extract_text(img_bytes)
                if ocr_result:
                    text_parts.append(ocr_result)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка OCR: {e}")
        
        return "\n".join(text_parts)
    
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
            ImageVerdict: Решение о наказании
        """
        if not message.from_user:
            return ImageVerdict("delete", reason)
        
        violations = await self.violation_tracker.increment_violations(
            message.from_user.id
        )
        
        return self.violation_tracker.get_punishment(violations, reason)