# ===============================================================
# Файл: bot/utils/ui_helpers.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Вспомогательные функции для работы с UI в aiogram.
# ===============================================================
import logging
from typing import Union, Tuple
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.keyboards.keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)

async def show_main_menu(message: Message):
    """Отображает главное меню, пытаясь отредактировать сообщение или отправляя новое."""
    try:
        await message.edit_text("Главное меню:", reply_markup=get_main_menu_keyboard())
    except (TelegramBadRequest, AttributeError):
        await message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())

async def show_main_menu_from_callback(call: CallbackQuery):
    """Корректно обрабатывает возврат в главное меню из callback query."""
    try:
        await call.message.edit_text(
            "Главное меню:",
            reply_markup=get_main_menu_keyboard()
        )
    except TelegramBadRequest as e:
        logger.warning(f"Не удалось отредактировать сообщение для показа главного меню: {e}.")
    finally:
        await call.answer()

async def get_message_and_chat_id(update: Union[CallbackQuery, Message]) -> Tuple[Message, int]:
    """
    Извлекает объекты сообщения и ID чата из CallbackQuery или Message.
    Автоматически отвечает на CallbackQuery, чтобы убрать "часики".
    """
    if isinstance(update, CallbackQuery):
        await update.answer()
        return update.message, update.message.chat.id
    return update, update.chat.id
