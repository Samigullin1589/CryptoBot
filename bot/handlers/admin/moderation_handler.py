# ===============================================================
# Файл: bot/handlers/admin/moderation_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: "Тонкий" обработчик для команд модерации.
# Принимает команды, валидирует их и вызывает ModerationService.
# ===============================================================
import logging
from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.types import Message

from bot.filters.access_filters import PrivilegeFilter, UserRole
from bot.services.moderation_service import ModerationService
from bot.states.moderation_states import ModerationStates
from bot.keyboards.admin_keyboards import get_back_to_admin_menu_keyboard
from bot.utils.ui_helpers import get_message_and_chat_id

moderation_router = Router()
logger = logging.getLogger(__name__)

# --- Обработка действий из интерактивных уведомлений об угрозах ---

@moderation_router.callback_query(F.data.startswith("threat_action:"))
async def handle_threat_action_callback(call: types.CallbackQuery, moderation_service: ModerationService):
    """Обрабатывает нажатия на кнопки в уведомлении об угрозе."""
    await call.answer()
    parts = call.data.split(":")
    action, chat_id_str, user_id_str = parts[1], parts[2], parts[3]
    chat_id, user_id = int(chat_id_str), int(user_id_str)
    
    response_text = await moderation_service.process_threat_action(
        action=action,
        admin_id=call.from_user.id,
        target_user_id=user_id,
        target_chat_id=chat_id,
        original_message=call.message
    )
    
    # --- ИСПРАВЛЕНО: Используем тройные кавычки для многострочного f-string ---
    await call.message.edit_text(
        f"""{call.message.text}

---
✅ <b>Действие выполнено:</b> {response_text}""",
        reply_markup=None
    )
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---


# --- Команды модерации ---

GROUP_ONLY_FILTER = F.chat.type.in_({'group', 'supergroup'})

@moderation_router.message(Command("ban", "бан", prefix="!/"), PrivilegeFilter(min_role=UserRole.ADMIN))
async def handle_ban_command(message: Message, moderation_service: ModerationService):
    """Команда для бана пользователя."""
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return

    reason = "Нарушение правил чата."
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        reason = args[1]
    
    result_text = await moderation_service.ban_user(
        admin_id=message.from_user.id,
        target_user_id=message.reply_to_message.from_user.id,
        target_chat_id=message.chat.id,
        reason=reason,
        original_message=message.reply_to_message
    )
    # Отправляем публичное уведомление в чат
    await message.answer(result_text)
    # Удаляем команду администратора
    await message.delete()

@moderation_router.message(Command("warn", "пред", prefix="!/"), PrivilegeFilter(min_role=UserRole.MODERATOR), GROUP_ONLY_FILTER)
async def handle_warn_command(message: Message, moderation_service: ModerationService):
    """Команда для вынесения предупреждения пользователю."""
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return

    reason = "Нарушение правил."
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        reason = args[1]

    result_text = await moderation_service.warn_user(
        admin_id=message.from_user.id,
        target_user_id=message.reply_to_message.from_user.id,
        target_chat_id=message.chat.id,
        reason=reason
    )
    await message.answer(result_text)
    await message.delete()
    await message.reply_to_message.delete()

# --- Управление стоп-словами ---

@moderation_router.message(Command("add_stop_word", prefix="!/"), PrivilegeFilter(min_role=UserRole.ADMIN))
async def handle_add_stop_word_command(message: Message, moderation_service: ModerationService):
    """Добавляет новое стоп-слово."""
    word = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    if not word:
        await message.reply("⚠️ Укажите слово. Например: <code>!add_stop_word казино</code>")
        return
        
    result = await moderation_service.add_stop_word(word)
    await message.reply(result)

@moderation_router.message(Command("del_stop_word", prefix="!/"), PrivilegeFilter(min_role=UserRole.ADMIN))
async def handle_delete_stop_word_command(message: Message, moderation_service: ModerationService):
    """Удаляет стоп-слово."""
    word = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    if not word:
        await message.reply("⚠️ Укажите слово для удаления.")
        return
        
    result = await moderation_service.remove_stop_word(word)
    await message.reply(result)

@moderation_router.message(Command("list_stop_words", prefix="!/"), PrivilegeFilter(min_role=UserRole.MODERATOR))
async def handle_list_stop_words_command(message: Message, moderation_service: ModerationService):
    """Показывает список всех стоп-слов."""
    result = await moderation_service.list_stop_words()
    await message.reply(result)
