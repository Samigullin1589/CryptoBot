# ===============================================================
# Файл: bot/handlers/admin/moderation_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Хэндлеры для команд модерации. Используют RBAC (фильтры
# ролей), делегируют всю логику в ModerationService и отвечают
# только за парсинг команд и отправку ответа.
# ===============================================================
import re
import logging
from datetime import timedelta

from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from bot.services.moderation_service import ModerationService
from bot.services.ai_service import AIService
from bot.filters.access_filters import PrivilegeFilter, UserRole
from bot.utils.helpers import parse_duration, get_command_args

moderation_router = Router()
logger = logging.getLogger(__name__)

# --- Основные команды модерации ---

@moderation_router.message(Command("ban", "бан", prefix="!/"), PrivilegeFilter(min_role=UserRole.ADMIN))
async def handle_ban_user(message: types.Message, moderation_service: ModerationService):
    """
    Универсальная команда бана. Делегирует всю логику в ModerationService.
    Форматы:
    - В группе (ответом): !ban [причина]
    - Из ЛС или в группе: !ban <chat_id> <user_id> [причина]
    """
    args_str = get_command_args(message.text)
    target_user_id: int | None = None
    target_chat_id: int | None = None
    reason = "Нарушение правил чата."
    spam_message_text: str | None = None

    # Пытаемся удалить команду администратора как можно раньше
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить команду админа {message.message_id}: {e}")

    # Режим бана ответом на сообщение
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_chat_id = message.chat.id
        spam_message_text = message.reply_to_message.text or message.reply_to_message.caption
        if args_str:
            reason = args_str
    # Режим бана по ID
    else:
        args = args_str.split() if args_str else []
        if len(args) < 2:
            await message.answer(
                "⚠️ Неверный формат. Используйте:\n"
                "- В группе (ответом): <code>!ban [причина]</code>\n"
                "- Из ЛС или в группе: <code>!ban [chat_id] [user_id] [причина]</code>",
                disable_notification=True
            )
            return
        
        chat_id_str, user_id_str = args[0], args[1]
        if not (chat_id_str.replace('-', '').isdigit() and user_id_str.isdigit()):
            await message.answer("⚠️ Chat ID и User ID должны быть числами.", disable_notification=True)
            return
        
        target_chat_id, target_user_id = int(chat_id_str), int(user_id_str)
        if len(args) > 2:
            reason = " ".join(args[2:])

    # Вызов сервиса для выполнения бана
    success, status_message = await moderation_service.ban_user(
        admin_id=message.from_user.id,
        target_user_id=target_user_id,
        target_chat_id=target_chat_id,
        reason=reason,
        spam_message_text=spam_message_text
    )
    
    # Ответ администратору в ЛС, если команда была не из ЛС или если произошла ошибка
    if message.chat.type != 'private' or not success:
        try:
            await message.bot.send_message(message.from_user.id, status_message)
        except Exception as e:
            logger.error(f"Не удалось отправить статус бана админу {message.from_user.id}: {e}")

@moderation_router.message(Command("warn", "пред", prefix="!/"), PrivilegeFilter(min_role=UserRole.MODERATOR))
async def handle_warn_user(message: types.Message, user_service: UserService):
    """Команда для выдачи предупреждения (доступна модераторам и выше)."""
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return
    
    # ... логика вызова moderation_service.warn_user(...) ...
    await message.reply("Функционал предупреждений в разработке.")


@moderation_router.message(Command("mute", "мут", prefix="!/"), PrivilegeFilter(min_role=UserRole.MODERATOR))
async def handle_mute_user(message: types.Message, moderation_service: ModerationService):
    """Команда для временного ограничения пользователя (доступна модераторам и выше)."""
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return
    
    try:
        await message.delete()
    except Exception: pass
    
    args = get_command_args(message.text).split(maxsplit=1)
    if not args:
        await message.answer("⚠️ Укажите длительность мута. Например: <code>!mute 30m Причина</code>")
        return
        
    duration = parse_duration(args[0])
    if not duration:
        await message.answer("⚠️ Неверный формат времени. Используйте 'm', 'h', 'd'. Например: <code>30m</code>, <code>2h</code>, <code>1d</code>.")
        return
        
    reason = args[1] if len(args) > 1 else "Нарушение правил."
    
    success, status_message = await moderation_service.mute_user(
        admin_id=message.from_user.id,
        target_user_id=message.reply_to_message.from_user.id,
        chat_id=message.chat.id,
        duration=duration,
        reason=reason
    )
    
    if not success:
        await message.answer(f"❌ {status_message}")


# --- Управление стоп-словами (только для админов) ---

@moderation_router.message(Command("add_stop_word", prefix="!/"), PrivilegeFilter(min_role=UserRole.ADMIN))
async def handle_add_stop_word(message: types.Message, ai_service: AIService):
    """Добавляет слово в стоп-лист."""
    word = get_command_args(message.text).lower().strip()
    if not word:
        await message.reply("⚠️ Укажите слово. Например: <code>!add_stop_word казино</code>")
        return
        
    success = await ai_service.add_stop_word(word)
    if success:
        await message.reply(f"✅ Слово '<code>{word}</code>' добавлено в стоп-лист.")
    else:
        await message.reply(f"⚠️ Слово '<code>{word}</code>' уже было в стоп-листе.")

@moderation_router.message(Command("del_stop_word", prefix="!/"), PrivilegeFilter(min_role=UserRole.ADMIN))
async def handle_delete_stop_word(message: types.Message, ai_service: AIService):
    """Удаляет слово из стоп-листа."""
    word = get_command_args(message.text).lower().strip()
    if not word:
        await message.reply("⚠️ Укажите слово для удаления.")
        return
        
    success = await ai_service.remove_stop_word(word)
    if success:
        await message.reply(f"✅ Слово '<code>{word}</code>' удалено.")
    else:
        await message.reply(f"⚠️ Слово '<code>{word}</code>' не найдено в стоп-листе.")

@moderation_router.message(Command("list_stop_words", prefix="!/"), PrivilegeFilter(min_role=UserRole.ADMIN))
async def handle_list_stop_words(message: types.Message, ai_service: AIService):
    """Показывает текущий стоп-лист."""
    words = await ai_service.get_all_stop_words()
    if not words:
        await message.reply("🚫 Стоп-лист пуст.")
        return
        
    text = "📜 Текущие стоп-слова:\n\n" + "\n".join([f"• <code>{word}</code>" for word in sorted(words)])
    await message.reply(text)
