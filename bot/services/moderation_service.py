# ===============================================================
# Файл: bot/services/moderation_service.py (НОВЫЙ ФАЙЛ)
# Описание: Сервисный слой для всей логики модерации.
# Инкапсулирует взаимодействие с API Telegram, UserService и AIService.
# Хэндлеры вызывают методы этого сервиса, а не выполняют логику сами.
# ===============================================================
import logging
from datetime import timedelta, datetime
from typing import Optional, Tuple

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest

from bot.services.user_service import UserService
from bot.services.ai_service import AIService
from bot.utils.helpers import sanitize_html

logger = logging.getLogger(__name__)

class ModerationService:
    """
    Сервис, инкапсулирующий всю бизнес-логику, связанную с модерацией.
    """
    def __init__(self, bot: Bot, user_service: UserService, ai_service: AIService):
        self.bot = bot
        self.user_service = user_service
        self.ai_service = ai_service

    async def ban_user(
        self,
        admin_id: int,
        target_user_id: int,
        target_chat_id: int,
        reason: str,
        spam_message_text: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Основной метод для бана пользователя.
        Выполняет все проверки и действия.
        
        :return: (Успех, Сообщение для администратора)
        """
        # 1. Проверка прав бота в целевом чате
        try:
            bot_member = await self.bot.get_chat_member(target_chat_id, self.bot.id)
            if not bot_member.status == ChatMemberStatus.ADMINISTRATOR or not bot_member.can_restrict_members:
                return False, f"❌ Я не администратор в чате <code>{target_chat_id}</code> или у меня нет права банить."
            can_delete_messages = bot_member.can_delete_messages
        except Exception as e:
            logger.error(f"Не удалось получить статус бота в чате {target_chat_id}: {e}")
            return False, f"❌ Не удалось проверить мой статус в чате <code>{target_chat_id}</code>."

        # 2. Проверка, не является ли цель администратором
        try:
            target_member = await self.bot.get_chat_member(target_chat_id, target_user_id)
            if target_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                return False, "😅 Нельзя забанить администратора чата."
        except TelegramBadRequest as e:
            if "user not found" not in e.message.lower():
                logger.error(f"Ошибка при проверке участника {target_user_id} в чате {target_chat_id}: {e}")
                return False, f"❌ Ошибка API при проверке цели: {e.message}"
        
        # 3. Основное действие: бан
        try:
            await self.bot.ban_chat_member(
                chat_id=target_chat_id, 
                user_id=target_user_id, 
                revoke_messages=can_delete_messages
            )
        except Exception as e:
            logger.error(f"Не удалось забанить пользователя {target_user_id}: {e}", exc_info=True)
            return False, f"❌ Не удалось забанить пользователя. Ошибка: {e}"

        # 4. Пост-действия: обучение AI, обновление БД, уведомления
        if spam_message_text:
            await self.ai_service.learn_from_spam(spam_message_text)
        
        await self.user_service.update_user_status(user_id=target_user_id, chat_id=target_chat_id, is_banned=True)
        logger.info(f"Admin {admin_id} banned {target_user_id} in chat {target_chat_id}. Reason: {reason}")

        # 5. Отправка уведомлений
        await self._notify_parties_about_ban(
            target_chat_id, target_user_id, reason, can_delete_messages
        )

        return True, f"✅ Пользователь <code>{target_user_id}</code> успешно забанен в чате <code>{target_chat_id}</code>."

    async def _notify_parties_about_ban(
        self, target_chat_id: int, target_user_id: int, reason: str, can_delete: bool
    ):
        """Отправляет уведомления в чат и забаненному пользователю."""
        # Уведомление в ЛС забаненному
        try:
            chat_info = await self.bot.get_chat(target_chat_id)
            await self.bot.send_message(
                target_user_id,
                f"❗️ Вы были забанены в чате «<b>{sanitize_html(chat_info.title)}</b>».\n\n"
                f"<b>Причина:</b> {sanitize_html(reason)}"
            )
        except Exception:
            logger.warning(f"Не удалось уведомить пользователя {target_user_id} о бане.")

        # Публичное уведомление в чате
        try:
            user_info = await self.bot.get_chat(target_user_id)
            target_link = f"<a href='tg://user?id={user_info.id}'>{sanitize_html(user_info.full_name or f'User {user_info.id}')}</a>"
        except Exception:
            target_link = f"Пользователь с ID <code>{target_user_id}</code>"
        
        deletion_info = "<i>Последние сообщения пользователя были удалены.</i>" if can_delete else "<i>У меня нет прав на удаление сообщений.</i>"
        
        public_text = (
            f"Пользователь {target_link} заблокирован.\n\n"
            f"<b>Причина:</b> {sanitize_html(reason)}\n\n"
            f"{deletion_info}"
        )
        await self.bot.send_message(target_chat_id, public_text)

    async def mute_user(
        self, admin_id: int, target_user_id: int, chat_id: int, duration: timedelta, reason: str
    ) -> Tuple[bool, str]:
        """Мутит пользователя в чате."""
        mute_end_timestamp = datetime.now() + duration
        try:
            await self.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target_user_id,
                permissions=types.ChatPermissions(), # Пустые права = мут
                until_date=mute_end_timestamp
            )
            
            # Логика уведомления
            admin_info = await self.bot.get_chat(admin_id)
            target_info = await self.bot.get_chat(target_user_id)
            admin_link = f"<a href='tg://user?id={admin_info.id}'>{sanitize_html(admin_info.full_name)}</a>"
            target_link = f"<a href='tg://user?id={target_info.id}'>{sanitize_html(target_info.full_name)}</a>"
            
            public_text = (
                f"🔇 Пользователь {target_link} был ограничен в правах администратором {admin_link} "
                f"до {mute_end_timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC.\n\n"
                f"<b>Причина:</b> {sanitize_html(reason)}"
            )
            await self.bot.send_message(chat_id, public_text)
            logger.info(f"Admin {admin_id} muted {target_user_id} in {chat_id} for {duration}. Reason: {reason}")
            
            return True, f"Пользователь {target_user_id} замучен."
        except Exception as e:
            logger.error(f"Failed to mute {target_user_id} in {chat_id}: {e}", exc_info=True)
            return False, f"Ошибка при муте: {e}"
