# ===============================================================
# Файл: bot/keyboards/threat_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Создает интерактивные клавиатуры для уведомлений
# об угрозах, позволяя администраторам быстро реагировать.
# ===============================================================
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_threat_notification_keyboard(user_id: int, chat_id: int, message_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для уведомления администратора об угрозе.

    :param user_id: ID пользователя, отправившего сообщение.
    :param chat_id: ID чата, где было отправлено сообщение.
    :param message_id: ID спам-сообщения (для возможного обучения).
    :return: Объект инлайн-клавиатуры.
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка для немедленного бана пользователя
    builder.button(
        text="🚫 Забанить",
        callback_data=f"threat_action:ban:{user_id}:{chat_id}"
    )
    
    # Кнопка для помилования (если сработало ложно)
    # Это действие может повышать trust_score пользователя.
    builder.button(
        text="✅ Помиловать",
        callback_data=f"threat_action:pardon:{user_id}:{chat_id}"
    )
    
    # Кнопка, чтобы просто закрыть/проигнорировать уведомление
    builder.button(
        text=" dismissing ",
        callback_data="threat_action:ignore"
    )
    
    builder.adjust(2, 1) # Располагаем кнопки в два столбца, последняя на всю ширину
    return builder.as_markup()

def get_threat_action_result_keyboard(result_text: str) -> InlineKeyboardMarkup:
    """
    Создает "заглушку" после того, как админ нажал на кнопку.
    Например, "✅ Пользователь забанен".
    """
    builder = InlineKeyboardBuilder()
    builder.button(text=result_text, callback_data="do_nothing")
    return builder.as_markup()
