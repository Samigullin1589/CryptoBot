# bot/services/advanced_security/inspectors/image_inspector.py
"""
Инспектор для анализа изображений.
"""
from typing import Optional

from aiogram import Bot
from aiogram.types import Message
from loguru import logger

from bot.services.advanced_security.inspectors.base import BaseInspector
from bot.services.advanced_security.models import InspectionResult


class ImageInspector(BaseInspector):
    """
    Инспектор изображений.
    
    Использует Vision API для анализа изображений на:
    - Рекламу
    - Спам
    - Нежелательный контент
    """
    
    def __init__(self, config, vision_service: Optional[any] = None):
        """
        Инициализация инспектора изображений.
        
        Args:
            config: Конфигурация безопасности
            vision_service: Опциональный сервис анализа изображений
        """
        super().__init__(config)
        self.vision_service = vision_service
    
    async def inspect(
        self,
        message: Message,
        bot: Bot
    ) -> InspectionResult:
        """
        Анализирует изображение в сообщении.
        
        Args:
            message: Сообщение с потенциальным изображением
            bot: Экземпляр бота для скачивания файла
            
        Returns:
            Результат проверки
        """
        result = InspectionResult()
        
        # Проверяем доступность сервиса и наличие фото
        if not self.vision_service or not message.photo:
            return result
        
        try:
            # Выбираем самое большое фото
            largest_photo = max(
                message.photo,
                key=lambda p: (p.width or 0) * (p.height or 0)
            )
            
            # Скачиваем файл
            file_info = await bot.get_file(largest_photo.file_id)
            
            if not file_info.file_path:
                logger.warning("Не удалось получить путь к файлу изображения")
                return result
            
            # Загружаем содержимое
            file_download = await bot.download_file(file_info.file_path)
            
            if not file_download:
                logger.warning("Не удалось скачать изображение")
                return result
            
            # Читаем байты
            image_bytes = file_download.read()
            
            # Анализируем через Vision API
            is_spam, details = await self.vision_service.analyze(image_bytes)
            
            if is_spam:
                explanation = details.get("explanation", "Image detected as spam/advertising")
                
                result.add_reason(
                    f"image_spam:{explanation[:50]}",
                    self.config.IMAGE_SPAM_SCORE
                )
                
                result.metadata.update({
                    "image_spam": True,
                    "vision_details": details
                })
                
                logger.warning(
                    f"ImageInspector: обнаружен спам в изображении "
                    f"(score: {self.config.IMAGE_SPAM_SCORE})"
                )
        
        except Exception as e:
            logger.error(
                f"Ошибка при анализе изображения: {e}",
                exc_info=True
            )
        
        return result