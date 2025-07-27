# ===============================================================
# Файл: bot/utils/ui_helpers.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Утилиты для управления пользовательским интерфейсом,
# такие как отображение главного меню.
# ===============================================================
import logging
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.keyboards.keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)

async def show_main_menu(message: Message):
    """
    Отображает главное меню, отправляя новое сообщение.
    Используется после команд, введенных текстом.
    """
    text = "Главное меню:"
    markup = get_main_menu_keyboard()
    await message.answer(text, reply_markup=markup)

async def show_main_menu_from_callback(call: CallbackQuery):
    """
    Отображает главное меню из колбэка, пытаясь отредактировать сообщение.
    Если не получается (например, это фото), удаляет старое и отправляет новое.
    """
    text = "Главное меню:"
    markup = get_main_menu_keyboard()
    try:
        # Пытаемся отредактировать текстовое сообщение
        await call.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        # Если не получилось (например, сообщение не текстовое или не изменилось),
        # удаляем старое и отправляем новое.
        try:
            await call.message.delete()
        except TelegramBadRequest as e:
            logger.warning(f"Could not delete message on main menu transition: {e}")
        await call.message.answer(text, reply_markup=markup)
    finally:
        # Отвечаем на колбэк, чтобы убрать "часики" с кнопки
        await call.answer()
