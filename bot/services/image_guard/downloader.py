# bot/services/image_guard/downloader.py
"""
Загрузка изображений из Telegram.
"""
import io
from typing import Optional

from aiogram import Bot
from aiogram.types import Message, PhotoSize
from loguru import logger


class ImageDownloader:
    """
    Компонент для скачивания изображений из Telegram.
    
    Поддерживает:
    - Фотографии (message.photo)
    - Документы с изображениями (message.document)
    """
    
    def __init__(self, bot: Bot):
        """
        Инициализирует загрузчик изображений.
        
        Args:
            bot: Экземпляр Telegram бота
        """
        self.bot = bot
        logger.debug("🔧 ImageDownloader инициализирован")
    
    async def download_photo(self, message: Message) -> Optional[bytes]:
        """
        Скачивает изображение из сообщения.
        
        Args:
            message: Сообщение с фото или документом
            
        Returns:
            Байты изображения или None при ошибке
        """
        photo_size = self._get_photo_size(message)
        
        if not photo_size:
            logger.debug("⚠️ Фото не найдено в сообщении")
            return None
        
        try:
            buffer = io.BytesIO()
            await self.bot.download(photo_size, destination=buffer)
            
            image_bytes = buffer.getvalue()
            
            logger.debug(
                f"✅ Изображение скачано: {len(image_bytes)} байт "
                f"(file_id: {photo_size.file_id})"
            )
            
            return image_bytes
            
        except Exception as e:
            logger.error(
                f"❌ Ошибка скачивания изображения "
                f"(file_id: {photo_size.file_id}): {e}",
                exc_info=True
            )
            return None
    
    @staticmethod
    def _get_photo_size(message: Message) -> Optional[PhotoSize]:
        """
        Извлекает объект фото из сообщения.
        
        Выбирает самое большое фото по размеру файла.
        
        Args:
            message: Сообщение
            
        Returns:
            PhotoSize или Document с изображением, или None
        """
        # Проверяем наличие фотографий
        if message.photo:
            # Выбираем самое большое фото
            return max(message.photo, key=lambda p: p.file_size or 0)
        
        # Проверяем документ с изображением
        if message.document and message.document.mime_type:
            if "image" in message.document.mime_type:
                return message.document
        
        return None
    
    @staticmethod
    def has_photo(message: Message) -> bool:
        """
        Проверяет наличие фото в сообщении.
        
        Args:
            message: Сообщение
            
        Returns:
            True если есть фото
        """
        if message.photo:
            return True
        
        if message.document and message.document.mime_type:
            return "image" in message.document.mime_type
        
        return False