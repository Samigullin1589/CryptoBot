# bot/utils/ui_helpers.py
# =================================================================================
# Файл: bot/utils/ui_helpers.py (ВЕРСИЯ "Distinguished Engineer" - ПРОДАКШН)
# Описание: Универсальные и отказоустойчивые вспомогательные функции для
# работы с интерфейсом пользователя в aiogram.
# =================================================================================

import logging
from typing import Union

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

async def edit_or_send_message(
    event: Union[CallbackQuery, Message],
    text: str,
    keyboard: InlineKeyboardMarkup = None,
    **kwargs
) -> Message:
    """
    Универсальная, отказоустойчивая функция для отправки или редактирования сообщения.

    Она заменяет собой необходимость иметь отдельные функции для Message и CallbackQuery.
    Пытается отредактировать существующее сообщение. Если это невозможно
    (например, это не callback-запрос или сообщение не изменилось),
    отправляет новое сообщение или просто убирает "часики" с кнопки.

    :param event: Объект CallbackQuery или Message, вызвавший действие.
    :param text: Текст для отправки/редактирования.
    :param keyboard: Клавиатура для сообщения.
    :param kwargs: Дополнительные параметры для send_message или edit_text.
    :return: Отправленное или отредактированное сообщение.
    """
    if isinstance(event, CallbackQuery):
        # Если это CallbackQuery, всегда есть message для редактирования
        try:
            # Пытаемся отредактировать сообщение
            return await event.message.edit_text(
                text=text,
                reply_markup=keyboard,
                **kwargs
            )
        except TelegramBadRequest as e:
            # Эта ошибка возникает, если текст и клавиатура не изменились.
            # В этом случае мы просто отвечаем на callback, чтобы убрать "часики".
            if "message is not modified" in e.message:
                await event.answer()
                return event.message
            # Если ошибка другая (например, сообщение слишком старое для редактирования),
            # логируем ее и отправляем новое сообщение как ответ.
            logger.error(f"Не удалось отредактировать сообщение (ID: {event.message.message_id}): {e}. Отправляем новое.")
            await event.answer() # Убираем "часики" в любом случае
            return await event.message.answer(
                text=text,
                reply_markup=keyboard,
                **kwargs
            )
    elif isinstance(event, Message):
        # Если это обычное сообщение, просто отправляем ответ
        return await event.answer(
            text=text,
            reply_markup=keyboard,
            **kwargs
        )

