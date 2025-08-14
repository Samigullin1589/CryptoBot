# ===============================================================
# Файл: bot/handlers/admin/moderation_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: "Тонкий" обработчик для команд модерации.
# ИСПРАВЛЕНИЕ: Внедрение зависимостей унифицировано через deps: Deps.
# ===============================================================
import logging
from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.types import Message

from bot.filters.access_filters import PrivilegeFilter, UserRole
from bot.states.moderation_states import ModerationStates
from bot.keyboards.admin_keyboards import get_back_to_admin_menu_keyboard
from bot.utils.ui_helpers import get_message_and_chat_id
from bot.utils.dependencies import Deps

moderation_router = Router()
logger = logging.getLogger(__name__)

# --- Обработка действий из интерактивных уведомлений об угрозах ---

@moderation_router.callback_query(F.data.startswith("threat_action:"))
async def handle_threat_action_callback(call: types.CallbackQuery, deps: Deps):
    """Обрабатывает нажатия на кнопки в уведомлении об угрозе."""
    await call.answer()
    parts = call.data.split(":")
    action = parts[1]

    if action == "ignore":
        await call.message.edit_text(f"{call.message.text}\n\n--- \nДействие проигнорировано.", reply_markup=None)
        return

    user_id_str, chat_id_str = parts[2], parts[3]
    user_id, chat_id = int(user_id_str), int(chat_id_str)

    response_text = "Действие не распознано."
    if action == "ban":
        response_text = await deps.moderation_service.ban_user(
            admin_id=call.from_user.id,
            target_user_id=user_id,
            target_chat_id=chat_id,
            reason="Автоматический бан после обнаружения угрозы"
        )
    elif action == "pardon":
        response_text = f"✅ Пользователь {user_id} помилован."

    await call.message.edit_text(
        f"{call.message.html_text}\n\n--- \n✅ <b>Действие выполнено:</b> {response_text}",
        reply_markup=None
    )


# --- Команды модерации ---

GROUP_ONLY_FILTER = F.chat.type.in_({'group', 'supergroup'})

@moderation_router.message(Command("ban", "бан", prefix="!/"), PrivilegeFilter(min_role=UserRole.ADMIN))
async def handle_ban_command(message: Message, deps: Deps):
    """Команда для бана пользователя."""
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return

    reason = "Нарушение правил чата."
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        reason = args[1]
    
    result_text = await deps.moderation_service.ban_user(
        admin_id=message.from_user.id,
        target_user_id=message.reply_to_message.from_user.id,
        target_chat_id=message.chat.id,
        reason=reason,
        original_message=message.reply_to_message
    )
    await message.answer(result_text)
    await message.delete()

@moderation_router.message(Command("add_stop_word", prefix="!/"), PrivilegeFilter(min_role=UserRole.ADMIN))
async def handle_add_stop_word_command(message: Message, deps: Deps):
    """Добавляет новое стоп-слово."""
    word = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    if not word:
        await message.reply("⚠️ Укажите слово. Например: <code>!add_stop_word казино</code>")
        return
        
    result = await deps.moderation_service.add_stop_word(word)
    await message.reply(result)

@moderation_router.message(Command("del_stop_word", prefix="!/"), PrivilegeFilter(min_role=UserRole.ADMIN))
async def handle_delete_stop_word_command(message: Message, deps: Deps):
    """Удаляет стоп-слово."""
    word = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    if not word:
        await message.reply("⚠️ Укажите слово для удаления.")
        return
        
    result = await deps.moderation_service.remove_stop_word(word)
    await message.reply(result)

@moderation_router.message(Command("list_stop_words", prefix="!/"), PrivilegeFilter(min_role=UserRole.MODERATOR))
async def handle_list_stop_words_command(message: Message, deps: Deps):
    """Показывает список всех стоп-слов."""
    result = await deps.moderation_service.list_stop_words()
    await message.reply(result)