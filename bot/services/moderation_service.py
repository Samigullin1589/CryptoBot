# ===============================================================
# Файл: bot/services/moderation_service.py (ПРОДАКШН-ВЕРСИЯ 2025 - ПОЛНАЯ РЕАЛИЗАЦИЯ)
# Описание: Сервис, инкапсулирующий всю логику модерации:
#           бан, предупреждения, работа со стоп-словами и
#           уведомление администраторов.
# ===============================================================
import logging
from typing import List, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from bot.services.user_service import UserService
from bot.services.admin_service import AdminService
from bot.services.stop_word_service import StopWordService
from bot.config.settings import ThreatFilterConfig
from bot.utils.models import UserRole
from bot.keyboards.threat_keyboards import get_threat_notification_keyboard

logger = logging.getLogger(__name__)

class ModerationService:
    """Оркестрирует все действия, связанные с модерацией чата."""

    def __init__(self, bot: Bot, user_service: UserService, admin_service: AdminService,
                 stop_word_service: StopWordService, config: ThreatFilterConfig):
        self.bot = bot
        self.user_service = user_service
        self.admin_service = admin_service
        self.stop_word_service = stop_word_service
        self.config = config

    async def ban_user(self, admin_id: int, target_user_id: int, target_chat_id: int,
                       reason: str, original_message: Optional[Message] = None) -> str:
        """Банит пользователя, удаляет его сообщения и уведомляет об этом."""
        try:
            await self.bot.ban_chat_member(chat_id=target_chat_id, user_id=target_user_id)
            logger.info(f"Администратор {admin_id} забанил пользователя {target_user_id} в чате {target_chat_id} по причине: {reason}")
            
            if original_message:
                await original_message.delete()
            
            await self.user_service.update_user_role(target_user_id, UserRole.BANNED)
            return f"✅ Пользователь {target_user_id} успешно забанен. Причина: {reason}"
        except TelegramBadRequest as e:
            logger.error(f"Не удалось забанить пользователя {target_user_id}: {e.message}")
            return f"❌ Не удалось забанить пользователя. Возможно, у меня недостаточно прав."
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при бане пользователя {target_user_id}: {e}", exc_info=True)
            return "❌ Произошла внутренняя ошибка при попытке бана."

    async def process_detected_threat(self, message: Message, threat_score: float, reasons: List[str]):
        """Обрабатывает угрозу, обнаруженную фильтром."""
        user = message.from_user
        if not user: return

        # Логика снижения рейтинга доверия (если она будет реализована в UserService)
        # await self.user_service.log_violation(...)

        reasons_text = "\n".join([f"• {r}" for r in reasons])
        admin_alert = (
            f"🚨 <b>Обнаружена угроза!</b> 🚨\n\n"
            f"<b>Пользователь:</b> <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username})\n"
            f"<b>ID:</b> <code>{user.id}</code>\n"
            f"<b>Чат ID:</b> <code>{message.chat.id}</code>\n"
            f"<b>Балл угрозы:</b> {threat_score:.2f}\n"
            f"<b>Причины:</b>\n{reasons_text}\n\n"
            f"<i>Сообщение удалено.</i>"
        )
        
        keyboard = get_threat_notification_keyboard(user.id, message.chat.id, message.message_id)
        await self.admin_service.notify_admins(admin_alert, reply_markup=keyboard)

    # --- Методы для управления стоп-словами ---
    async def add_stop_word(self, word: str) -> str:
        success = await self.stop_word_service.add_stop_word(word)
        return f"✅ Слово «{word}» добавлено в стоп-лист." if success else f"ℹ️ Слово «{word}» уже было в стоп-листе."

    async def remove_stop_word(self, word: str) -> str:
        success = await self.stop_word_service.remove_stop_word(word)
        return f"✅ Слово «{word}» удалено из стоп-листа." if success else f"⚠️ Слово «{word}» не найдено в стоп-листе."

    async def list_stop_words(self) -> str:
        words = await self.stop_word_service.get_all_stop_words()
        if not words:
            return "🚫 Стоп-лист пуст."
        return "<b>Текущий стоп-лист:</b>\n\n" + ", ".join(f"<code>{word}</code>" for word in words)