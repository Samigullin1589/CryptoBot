# bot/services/image_guard_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Сервис для многоуровневой защиты от спам-изображений, использующий
# перцептивное хэширование, AI-анализ (OCR) и систему эскалации нарушений.

import asyncio
import contextlib
import io
import re
from typing import Iterable, List, Optional, Tuple

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, PhotoSize, User
from loguru import logger
from PIL import Image, ImageOps
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.services.ai_content_service import AIContentService
from bot.utils.dependencies import get_bot_instance, get_redis_client
from bot.utils.keys import KeyFactory
from bot.utils.models import ImageVerdict

# Скомпилированное рег. выражение для поиска спам-паттернов в тексте
_SPAM_RX = re.compile("|".join(settings.SECURITY.IMAGE_SPAM_PATTERNS), re.IGNORECASE)


def dhash(image: Image.Image) -> int:
    """Вычисляет 64-битный перцептивный dHash для изображения."""
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

def hamming_distance(hash1: int, hash2: int) -> int:
    """Вычисляет расстояние Хэмминга между двумя 64-битными хэшами."""
    return (hash1 ^ hash2).bit_count()


class ImageGuardService:
    """
    Анализирует изображения на спам, используя комбинацию перцептивных хэшей,
    OCR через AI и эвристический анализ текста.
    """

    def __init__(self, ai_service: AIContentService):
        self.redis: Redis = get_redis_client()
        self.bot: Bot = get_bot_instance()
        self.ai_service = ai_service
        self.config = settings.SECURITY
        self.keys = KeyFactory
        logger.info("Сервис ImageGuardService инициализирован.")

    async def check_message_with_photo(self, message: Message) -> ImageVerdict:
        """
        Основной метод проверки сообщения с фото.
        Возвращает вердикт с решением и причиной.
        """
        if not message.from_user or not (message.photo or (message.document and message.document.mime_type and "image" in message.document.mime_type)):
            return ImageVerdict(action="allow")

        img_bytes = await self._download_photo(message)
        if not img_bytes:
            return ImageVerdict(action="allow", reason="download_failed")

        # Уровень 1: Проверка по базе хэшей известных спам-изображений
        image_hash = await asyncio.to_thread(dhash, Image.open(io.BytesIO(img_bytes)))
        is_known_spam, reason = await self._is_known_spam_hash(image_hash)
        if is_known_spam:
            return await self._escalate_punishment(message, reason)

        # Уровень 2: Анализ текста (подпись + OCR)
        full_text = (message.caption or "").strip()
        ocr_text = await self.ai_service.analyze_image("Извлеки весь текст с картинки.", img_bytes)
        if isinstance(ocr_text, dict) and ocr_text.get("extracted_text"):
             full_text = f"{full_text}\n{ocr_text['extracted_text']}".strip()

        if self._text_looks_like_spam(full_text):
            # Если текст подозрительный, добавляем хэш в базу для будущих проверок
            await self.mark_hash_as_spam(image_hash)
            return await self._escalate_punishment(message, "suspicious_text_on_image")

        return ImageVerdict(action="allow")

    async def mark_photo_as_spam(self, message: Message) -> str:
        """Админский метод: добавить хэш изображения в черный список."""
        img_bytes = await self._download_photo(message)
        if not img_bytes:
            return "Не удалось скачать фото для анализа."
        
        image_hash = await asyncio.to_thread(dhash, Image.open(io.BytesIO(img_bytes)))
        if image_hash is None:
            return "Не удалось вычислить хэш изображения."
            
        await self.mark_hash_as_spam(image_hash)
        return "Хэш изображения успешно добавлен в базу спама."
    
    async def mark_hash_as_spam(self, image_hash: Optional[int]):
        """Добавляет хэш в соответствующий бакет в Redis."""
        if image_hash is None:
            return
        try:
            prefix = image_hash >> (64 - self.config.PHASH_PREFIX_BITS)
            bucket_key = self.keys.image_hash_bucket(prefix)
            pipe = self.redis.pipeline()
            pipe.sadd(bucket_key, str(image_hash))
            pipe.expire(bucket_key, self.config.PHASH_TTL_SECONDS)
            await pipe.execute()
        except Exception as e:
            logger.error(f"Не удалось добавить хэш {image_hash} в Redis: {e}")

    async def _is_known_spam_hash(self, image_hash: Optional[int]) -> Tuple[bool, str]:
        """Проверяет, похож ли хэш на один из известных спам-хэшей."""
        if image_hash is None:
            return False, "hash_calculation_failed"
        try:
            prefix = image_hash >> (64 - self.config.PHASH_PREFIX_BITS)
            bucket_key = self.keys.image_hash_bucket(prefix)
            
            candidate_hashes = await self.redis.smembers(bucket_key)
            if not candidate_hashes:
                return False, "no_matches"

            for ch_str in candidate_hashes:
                distance = hamming_distance(image_hash, int(ch_str))
                if distance <= self.config.PHASH_DISTANCE:
                    return True, f"similar_hash(dist={distance})"
            return False, "no_similar_hashes"
        except Exception as e:
            logger.error(f"Ошибка при проверке хэша изображения в Redis: {e}")
            return False, "redis_error"

    def _text_looks_like_spam(self, text: str) -> bool:
        """Применяет эвристики для определения спама в тексте."""
        if not text:
            return False
        if _SPAM_RX.search(text):
            return True
        
        # Подсчет дополнительных признаков спама
        money_marks = len(re.findall(r"[💰💵🪙\$€₽₿₮]", text))
        links = len(re.findall(r"https?://|t\.me/", text, re.IGNORECASE))
        mentions = len(re.findall(r"@\w{4,}", text))
        
        # Простая система очков
        score = (money_marks * 2) + (links * 1.5) + mentions
        return score >= self.config.IMAGE_TEXT_SPAM_SCORE

    async def _escalate_punishment(self, message: Message, reason: str) -> ImageVerdict:
        """Определяет меру наказания на основе количества нарушений."""
        if not message.from_user:
            return ImageVerdict("delete", reason)
            
        try:
            key = self.keys.user_spam_image_count(message.from_user.id)
            violations_count = await self.redis.incr(key)
            await self.redis.expire(key, self.config.WINDOW_SECONDS)
        except Exception as e:
            logger.error(f"Не удалось обновить счетчик нарушений для user_id={message.from_user.id}: {e}")
            violations_count = 1

        if violations_count >= self.config.IMAGE_SPAM_AUTOBAN_THRESHOLD:
            return ImageVerdict("ban", f"{reason} (нарушение #{violations_count})")
        
        return ImageVerdict("delete", f"{reason} (нарушение #{violations_count})")

    async def _download_photo(self, message: Message) -> Optional[bytes]:
        """Скачивает изображение из сообщения в байты."""
        photo_size = None
        if message.photo:
            photo_size = max(message.photo, key=lambda p: p.file_size or 0)
        elif message.document:
            photo_size = message.document

        if not photo_size:
            return None

        try:
            buffer = io.BytesIO()
            await self.bot.download(photo_size, destination=buffer)
            return buffer.getvalue()
        except Exception as e:
            logger.error(f"Не удалось скачать фото file_id={photo_size.file_id}: {e}")
            return None