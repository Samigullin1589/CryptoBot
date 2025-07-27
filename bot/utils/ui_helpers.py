# ===============================================================
# Файл: bot/utils/ui_helpers.py (НОВЫЙ ФАЙЛ)
# Описание: Хелперы, специфичные для взаимодействия с UI Telegram.
# ===============================================================

import logging
from typing import Union, Tuple

from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)

async def get_message_and_chat_id(update: Union[CallbackQuery, Message]) -> Tuple[Message, int]:
    """
    Извлекает объект сообщения и ID чата из CallbackQuery или Message.
    Автоматически отвечает на CallbackQuery, чтобы убрать "часики".
    
    :param update: Входящее событие.
    :return: Кортеж (объект Message, ID чата).
    """
    if isinstance(update, CallbackQuery):
        # Отвечаем на колбэк, чтобы пользователь видел реакцию
        await update.answer()
        return update.message, update.message.chat.id
    return update, update.chat.id

async def safe_send_message(
    message: Message, 
    text: str, 
    reply_markup: InlineKeyboardMarkup
) -> Message:
    """
    Отображает сообщение, пытаясь сначала отредактировать существующее,
    а в случае неудачи — отправляет новое.
    Это полезно для предотвращения "прыгания" чата.
    
    :param message: Объект сообщения, которое нужно отредактировать или на которое ответить.
    :param text: Текст для отправки.
    :param reply_markup: Клавиатура.
    :return: Отправленное или отредактированное сообщение.
    """
    try:
        # Пытаемся отредактировать, если это возможно
        return await message.edit_text(text, reply_markup=reply_markup)
    except (TelegramBadRequest, AttributeError) as e:
        # TelegramBadRequest: если сообщение не изменилось или его нельзя редактировать
        # AttributeError: если message - это не Message, а, например, User
        logger.debug(f"Could not edit message: {e}. Sending a new one.")
        # Если не получилось, отправляем новое сообщение
        return await message.answer(text, reply_markup=reply_markup)

