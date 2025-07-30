# ===============================================================
# Файл: bot/handlers/threats/threat_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: "Тонкий" хэндлер, который ловит сообщения от ThreatFilter
# и передает их в ModerationService для комплексной обработки.
# ===============================================================
import logging
from typing import List

from aiogram import Router
from aiogram.types import Message

from bot.filters.threat_filter import ThreatFilter
from bot.services.moderation_service import ModerationService

threat_router = Router(name=__name__)
logger = logging.getLogger(__name__)

@threat_router.message(ThreatFilter())
async def handle_threat_message(
    message: Message,
    moderation_service: ModerationService,
    threat_score: float,
    reasons: List[str]
):
    """
    Обрабатывает сообщение, определенное как угроза.
    - Вызывает ModerationService для наказания и уведомления.
    - Удаляет исходное сообщение.
    """
    logger.warning(
        f"Threat detected from user {message.from_user.id} in chat {message.chat.id}. "
        f"Score: {threat_score:.2f}. Reasons: {reasons}"
    )
    
    # --- УЛУЧШЕНИЕ: Вызов сервиса стал чище ---
    try:
        await moderation_service.process_detected_threat(
            message=message,
            threat_score=threat_score,
            reasons=reasons
        )
    except Exception as e:
        logger.error(f"Could not process threat notification: {e}", exc_info=True)

    try:
        await message.delete()
    except Exception as e:
        logger.error(f"Could not delete threat message {message.message_id} in chat {message.chat.id}: {e}")