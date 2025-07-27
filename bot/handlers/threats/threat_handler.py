# ===============================================================
# Файл: bot/handlers/threats/threat_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Заменяет spam_handler.py. Этот "тонкий" хэндлер
# ловит сообщения, помеченные ThreatFilter, и передает их
# в ModerationService для комплексной обработки.
# ===============================================================
import logging
from typing import List

from aiogram import Router, Bot
from aiogram.types import Message

from bot.filters.threat_filter import ThreatFilter
from bot.config.settings import AppSettings
from bot.services.moderation_service import ModerationService

threat_router = Router()
logger = logging.getLogger(__name__)

# Применяем наш кастомный фильтр ко всем сообщениям в этом роутере.
# Фильтр также передает в хэндлер результаты своего анализа (score, reasons).
@threat_router.message(ThreatFilter())
async def handle_threat_message(
    message: Message,
    bot: Bot,
    settings: AppSettings,
    moderation_service: ModerationService,
    threat_score: float,
    reasons: List[str]
):
    """
    Обрабатывает сообщение, определенное как угроза.
    - Удаляет исходное сообщение.
    - Вызывает ModerationService для уведомления администраторов.
    
    :param message: Заблокированное сообщение.
    :param bot: Экземпляр бота.
    :param settings: Настройки приложения.
    :param moderation_service: Сервис для логики модерации.
    :param threat_score: Итоговый балл угрозы от ThreatFilter.
    :param reasons: Список причин блокировки от ThreatFilter.
    """
    logger.warning(
        f"Threat detected from user {message.from_user.id} in chat {message.chat.id}. "
        f"Score: {threat_score:.2f}. Reasons: {reasons}"
    )
    
    # Сначала пытаемся уведомить администраторов
    try:
        await moderation_service.process_detected_threat(
            message=message,
            threat_score=threat_score,
            reasons=reasons,
            admin_chat_id=settings.api_keys.admin_chat_id
        )
    except Exception as e:
        logger.error(f"Could not process threat notification: {e}", exc_info=True)

    # Затем удаляем исходное спам-сообщение
    try:
        await message.delete()
    except Exception as e:
        logger.error(f"Could not delete threat message {message.message_id} in chat {message.chat.id}: {e}")
