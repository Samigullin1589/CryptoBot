# ===============================================================
# Файл: bot/keyboards/threat_keyboards.py
# Описание: Создает интерактивные клавиатуры для уведомлений
# об угрозах, позволяя администраторам быстро реагировать.
# ИСПРАВЛЕНИЕ: Переход на использование фабрик CallbackData.
# ===============================================================
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from .callback_factories import ThreatCallback

def get_threat_notification_keyboard(user_id: int, chat_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для уведомления администратора об угрозе.

    :param user_id: ID пользователя, отправившего сообщение.
    :param chat_id: ID чата, где было отправлено сообщение.
    :return: Объект инлайн-клавиатуры.
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="🚫 Забанить",
        callback_data=ThreatCallback(action="ban", user_id=user_id, chat_id=chat_id).pack()
    )
    
    builder.button(
        text="✅ Помиловать",
        callback_data=ThreatCallback(action="pardon", user_id=user_id, chat_id=chat_id).pack()
    )
    
    builder.button(
        text="Проигнорировать",
        callback_data=ThreatCallback(action="ignore", user_id=user_id, chat_id=chat_id).pack()
    )
    
    builder.adjust(2, 1)
    return builder.as_markup()

def get_threat_action_result_keyboard(result_text: str) -> InlineKeyboardMarkup:
    """
    Создает "заглушку" после того, как админ нажал на кнопку.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text=result_text, callback_data="do_nothing")
    return builder.as_markup()