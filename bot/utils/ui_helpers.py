# =================================================================================
# Файл: bot/utils/ui_helpers.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Вспомогательные функции для работы с интерфейсом пользователя.
# ИСПРАВЛЕНИЕ: Добавлена недостающая функция show_main_menu_from_callback.
# =================================================================================

import logging
from typing import Union, Tuple

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup

# Импортируем клавиатуру главного меню
from bot.keyboards.keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)

async def edit_or_send_message(
    event: Union[CallbackQuery, Message],
    text: str,
    keyboard: InlineKeyboardMarkup = None,
    **kwargs
) -> Message:
    """
    Универсальная функция для отправки или редактирования сообщения.
    """
    if isinstance(event, CallbackQuery):
        try:
            return await event.message.edit_text(
                text=text,
                reply_markup=keyboard,
                **kwargs
            )
        except TelegramBadRequest as e:
            if "message is not modified" in e.message:
                await event.answer()
                return event.message
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            return await event.message.answer(
                text=text,
                reply_markup=keyboard,
                **kwargs
            )
    elif isinstance(event, Message):
        return await event.answer(
            text=text,
            reply_markup=keyboard,
            **kwargs
        )

# ИСПРАВЛЕНО: Добавлена недостающая функция
async def show_main_menu_from_callback(call: CallbackQuery):
    """
    Редактирует сообщение из CallbackQuery, отображая главное меню.
    """
    text = "👋 Выберите одну из опций в меню ниже."
    keyboard = get_main_menu_keyboard()
    await edit_or_send_message(call, text, keyboard)
    await call.answer()


async def get_message_and_chat_id(update: Union[CallbackQuery, Message]) -> Tuple[Message, int]:
    """
    Извлекает объекты сообщения и ID чата из CallbackQuery или Message.
    """
    if isinstance(update, CallbackQuery):
        await update.answer()
        return update.message, update.message.chat.id
    return update, update.chat.id
