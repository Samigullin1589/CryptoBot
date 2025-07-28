# ===============================================================
# Файл: bot/services/moderation_service.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Сервис, инкапсулирующий всю бизнес-логику
# для команд модерации (бан, мут, предупреждение и т.д.).
# ===============================================================
import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from bot.filters.access_filters import UserRole
# --- ИСПРАВЛЕНИЕ: Импортируем новые, специализированные сервисы ---
from bot.services.security_service import SecurityService
from bot.services.stop_word_service import StopWordService
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from bot.services.user_service import UserService
from bot.utils.text_utils import sanitize_html, parse_duration

logger = logging.getLogger(__name__)

class ModerationService:
    """Сервис для выполнения действий модерации."""

    def __init__(
        self,
        bot: Bot,
        user_service: UserService,
        # --- ИСПРАВЛЕНИЕ: Принимаем новые зависимости ---
        security_service: SecurityService,
        stop_word_service: StopWordService
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
    ):
        self.bot = bot
        self.user_service = user_service
        # --- ИСПРАВЛЕНИЕ: Сохраняем новые зависимости ---
        self.security_service = security_service
        self.stop_word_service = stop_word_service
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    async def ban_user(self, admin_id: int, target_user_id: int, target_chat_id: int, reason: str, original_message: Optional[Message] = None) -> str:
        """
        Блокирует пользователя в чате.

        :param admin_id: ID администратора, выполняющего действие.
        :param target_user_id: ID пользователя, которого нужно забанить.
        :param target_chat_id: ID чата, в котором нужно забанить.
        :param reason: Причина бана.
        :param original_message: Исходное спам-сообщение для обучения AI.
        :return: Строка с результатом операции.
        """
        try:
            # Проверка, является ли цель администратором
            target_member = await self.bot.get_chat_member(target_chat_id, target_user_id)
            if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                return "😅 Нельзя забанить администратора чата."

            # Проверка прав бота
            bot_member = await self.bot.get_chat_member(target_chat_id, self.bot.id)
            if not bot_member.can_restrict_members:
                return f"❌ У меня нет права банить пользователей в чате <code>{target_chat_id}</code>."

            # Выполнение бана
            await self.bot.ban_chat_member(chat_id=target_chat_id, user_id=target_user_id, revoke_messages=True)
            
            # Обновление статуса в нашей БД
            await self.user_service.update_user_role(target_user_id, target_chat_id, UserRole.BANNED)
            logger.info(f"Admin {admin_id} banned {target_user_id} in chat {target_chat_id}. Reason: {reason}")
            
            # --- ИСПРАВЛЕНИЕ: Вызываем метод из правильного сервиса ---
            if original_message:
                await self.security_service.learn_from_spam(original_message, "admin_ban")
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

            # Уведомление пользователя о бане (если возможно)
            try:
                chat_info = await self.bot.get_chat(target_chat_id)
                await self.bot.send_message(
                    target_user_id,
                    f"❗️ Вы были забанены в чате «<b>{sanitize_html(chat_info.title)}</b>».\n\n"
                    f"<b>Причина:</b> {sanitize_html(reason)}"
                )
            except Exception:
                logger.warning(f"Failed to notify user {target_user_id} about ban.")
            
            return f"✅ Пользователь <code>{target_user_id}</code> успешно забанен в чате <code>{target_chat_id}</code>."

        except TelegramBadRequest as e:
            if "user not found" in e.message.lower():
                # Если пользователь уже не в чате, все равно можно забанить, чтобы он не вернулся
                 await self.bot.ban_chat_member(chat_id=target_chat_id, user_id=target_user_id, revoke_messages=False)
                 return f"✅ Пользователь <code>{target_user_id}</code> не найден в чате, но был забанен превентивно."
            logger.error(f"Telegram API error while banning user {target_user_id}: {e}")
            return f"❌ Ошибка Telegram при бане: {e.message}"
        except Exception as e:
            logger.exception(f"Unexpected error while banning user {target_user_id}")
            return f"❌ Произошла непредвиденная ошибка при бане пользователя."

    # ... (остальные методы модерации, такие как warn, mute, и т.д.)

    # --- ИСПРАВЛЕНИЕ: Делегируем управление стоп-словами в StopWordService ---
    async def add_stop_word(self, word: str) -> str:
        """Добавляет стоп-слово через сервис."""
        success = await self.stop_word_service.add_stop_word(word)
        if success:
            return f"✅ Слово '<code>{word}</code>' добавлено в стоп-лист."
        else:
            return f"⚠️ Слово '<code>{word}</code>' уже было в стоп-листе."

    async def remove_stop_word(self, word: str) -> str:
        """Удаляет стоп-слово через сервис."""
        success = await self.stop_word_service.remove_stop_word(word)
        if success:
            return f"✅ Слово '<code>{word}</code>' удалено."
        else:
            return f"⚠️ Слово '<code>{word}</code>' не найдено в стоп-листе."

    async def list_stop_words(self) -> str:
        """Получает список стоп-слов через сервис."""
        words = await self.stop_word_service.get_all_stop_words()
        if not words:
            return "🚫 Стоп-лист пуст."
        return "📜 Текущие стоп-слова:\n\n" + "\n".join([f"• <code>{word}</code>" for word in words])
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
