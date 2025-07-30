# ===============================================================
# Файл: bot/services/moderation_service.py (НОВЫЙ ФАЙЛ)
# Описание: Сервис для выполнения действий по модерации.
# ===============================================================
import logging
from typing import List
from aiogram.types import Message

from bot.services.user_service import UserService
from bot.services.admin_service import AdminService
from bot.config.settings import ThreatFilterConfig

logger = logging.getLogger(__name__)

class ModerationService:
    """Оркестрирует действия в ответ на обнаруженную угрозу."""
    def __init__(self, user_service: UserService, admin_service: AdminService, config: ThreatFilterConfig):
        self.user_service = user_service
        self.admin_service = admin_service
        self.config = config

    async def process_detected_threat(
        self,
        message: Message,
        threat_score: float,
        reasons: List[str]
    ):
        """
        1. Наказывает пользователя (снижает рейтинг).
        2. Уведомляет администраторов.
        """
        user = message.from_user
        
        # 1. Наказание: снижаем рейтинг доверия
        penalty = int(threat_score) # Базовое наказание равно баллу угрозы
        await self.user_service.log_violation(
            user_id=user.id,
            chat_id=message.chat.id,
            reason=", ".join(reasons),
            penalty=penalty
        )

        # 2. Уведомление: отправляем алерт в админ-чат
        reasons_text = "\n".join([f" - {r}" for r in reasons])
        admin_alert = (
            f"🚨 <b>Обнаружена угроза!</b> 🚨\n\n"
            f"<b>Пользователь:</b> <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username})\n"
            f"<b>ID:</b> <code>{user.id}</code>\n"
            f"<b>Чат ID:</b> <code>{message.chat.id}</code>\n"
            f"<b>Балл угрозы:</b> <b>{threat_score:.2f}</b> (порог: {self.config.min_trigger_score})\n"
            f"<b>Причины:</b>\n{reasons_text}\n\n"
            f"<i>Исходное сообщение удалено. Рейтинг доверия пользователя снижен на {penalty} пт.</i>"
        )
        await self.admin_service.notify_admins(admin_alert)