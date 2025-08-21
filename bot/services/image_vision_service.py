# bot/services/image_vision_service.py
# Дата обновления: 20.08.2025
# Версия: 2.0.0
# Описание: Сервис-фасад для анализа изображений с использованием AI.
# Делегирует задачи по распознаванию текста и модерации основному AI-сервису.

import asyncio
from io import BytesIO
from typing import Dict, Any, Optional

from loguru import logger
from PIL import Image

from bot.services.ai_content_service import AIContentService
from bot.utils.models import ImageAnalysisResult


class ImageVisionService:
    """
    Предоставляет унифицированный интерфейс для анализа изображений.
    Основная задача - подготовить данные и передать их в AIContentService
    для распознавания текста (OCR) и вынесения вердикта о спаме.
    """

    def __init__(self, ai_service: AIContentService):
        """
        Инициализирует сервис.

        :param ai_service: Экземпляр AIContentService для выполнения AI-запросов.
        """
        self.ai_service = ai_service
        logger.info("Сервис ImageVisionService инициализирован.")

    async def analyze(self, photo_bytes: bytes) -> ImageAnalysisResult:
        """
        Анализирует изображение на предмет спама и извлекает текст.

        Возвращает объект ImageAnalysisResult с результатами анализа.
        В случае сбоя AI или отсутствия AI-провайдера возвращает
        нейтральный результат (не спам, нет текста).
        """
        if not self.ai_service:
            logger.warning("AIContentService не доступен, анализ изображений пропущен.")
            return ImageAnalysisResult()

        try:
            # Асинхронно выполняем CPU-bound операцию по обработке изображения
            prepared_bytes = await asyncio.to_thread(self._prepare_image, photo_bytes)

            prompt = (
                "Проанализируй это изображение на предмет спама, рекламы или мошенничества. "
                "Извлеки весь читаемый текст. Верни JSON."
            )
            
            # Вызываем основной AI сервис для анализа
            response_data = await self.ai_service.analyze_image(prompt, prepared_bytes)

            if isinstance(response_data, dict):
                return ImageAnalysisResult.model_validate(response_data)
            
            logger.warning(f"AI-сервис вернул неожиданный тип данных для анализа изображения: {type(response_data)}")
            return ImageAnalysisResult(explanation="AI service returned invalid data type.")

        except Exception as e:
            logger.exception(f"Критическая ошибка при анализе изображения: {e}")
            return ImageAnalysisResult(explanation=f"Analysis failed due to an exception: {e}")

    @staticmethod
    def _prepare_image(photo_bytes: bytes) -> bytes:
        """
        Подготавливает изображение для отправки в AI-модель.
        Конвертирует в стандартный формат (JPEG) для лучшей совместимости.
        Эта операция выполняется в отдельном потоке, чтобы не блокировать event loop.
        """
        try:
            img = Image.open(BytesIO(photo_bytes)).convert("RGB")
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=90)
            return buffer.getvalue()
        except Exception as e:
            logger.error(f"Не удалось подготовить изображение: {e}")
            # В случае ошибки возвращаем исходные байты
            return photo_bytes