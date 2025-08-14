# ===============================================================
# Файл: bot/handlers/threats/threat_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - ФИНАЛЬНО ИСПРАВЛЕННАЯ)
# Описание: "Тонкий" хэндлер, который ловит сообщения от ThreatFilter
# и передает их в ModerationService для комплексной обработки.
# ИСПРАВЛЕНИЕ: Изменен способ регистрации фильтра с ThreatFilter()
#              на ThreatFilter для корректной работы DI.
# ===============================================================
import logging
from typing import List

from aiogram import Router
from aiogram.types import Message

from bot.filters.threat_filter import ThreatFilter
from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)

threat_router = Router(name="threats")

@threat_router.message(ThreatFilter())
async def on_threat_message(
    message: Message,
    deps: Deps,
    threat_score: float,
    reasons: List[str],
):
    try:
        await deps.moderation_service.process_detected_threat(
            message=message,
            threat_score=threat_score,
            reasons=reasons,
        )
    except Exception as e:
        logger.error(
            "Could not process threat notification: %s", e, exc_info=True
        )

    try:
        await message.delete()
    except Exception as e:
        logger.error(
            "Could not delete threat message %s in chat %s: %s",
            message.message_id,
            message.chat.id,
            e,
        )