# =================================================================================
# Файл: bot/utils/ui_helpers.py
# Версия: "Distinguished Engineer" - ИСПРАВЛЕНО (28.10.2025)
# Описание: Вспомогательные функции для работы с интерфейсом пользователя.
# ИСПРАВЛЕНИЕ: 
#   1. Добавлен импорт ParseMode
#   2. Добавлен параметр parse_mode во все функции
#   3. parse_mode=ParseMode.HTML используется по умолчанию
# =================================================================================

import logging
from typing import Union, Tuple, Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.enums import ParseMode  # ← ДОБАВЛЕНО

# Импортируем клавиатуру главного меню
from bot.keyboards.keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)


async def edit_or_send_message(
    event: Union[CallbackQuery, Message],
    text: str,
    keyboard: InlineKeyboardMarkup = None,
    parse_mode: Optional[str] = ParseMode.HTML,  # ← ДОБАВЛЕНО (с дефолтом)
    **kwargs
) -> Message:
    """
    Универсальная функция для отправки или редактирования сообщения.
    
    Args:
        event: CallbackQuery или Message
        text: Текст сообщения
        keyboard: Клавиатура (опционально)
        parse_mode: Режим парсинга (по умолчанию HTML)
        **kwargs: Дополнительные параметры
    
    Returns:
        Отправленное или отредактированное сообщение
    
    ИСПРАВЛЕНО: Добавлен параметр parse_mode с дефолтным значением ParseMode.HTML
    """
    if isinstance(event, CallbackQuery):
        try:
            return await event.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode=parse_mode,  # ← ДОБАВЛЕНО
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
                parse_mode=parse_mode,  # ← ДОБАВЛЕНО
                **kwargs
            )
    elif isinstance(event, Message):
        return await event.answer(
            text=text,
            reply_markup=keyboard,
            parse_mode=parse_mode,  # ← ДОБАВЛЕНО
            **kwargs
        )


async def show_main_menu_from_callback(
    call: CallbackQuery,
    parse_mode: Optional[str] = ParseMode.HTML  # ← ДОБАВЛЕНО
):
    """
    Редактирует сообщение из CallbackQuery, отображая главное меню.
    
    Args:
        call: CallbackQuery событие
        parse_mode: Режим парсинга (по умолчанию HTML)
    
    ИСПРАВЛЕНО: Добавлен параметр parse_mode
    """
    text = "👋 Выберите одну из опций в меню ниже."
    keyboard = get_main_menu_keyboard()
    await edit_or_send_message(
        call,
        text,
        keyboard,
        parse_mode=parse_mode  # ← ДОБАВЛЕНО (явно передаём)
    )
    await call.answer()


async def get_message_and_chat_id(
    update: Union[CallbackQuery, Message]
) -> Tuple[Message, int]:
    """
    Извлекает объекты сообщения и ID чата из CallbackQuery или Message.
    
    Args:
        update: CallbackQuery или Message
    
    Returns:
        Кортеж (Message, chat_id)
    """
    if isinstance(update, CallbackQuery):
        await update.answer()
        return update.message, update.message.chat.id
    return update, update.chat.id