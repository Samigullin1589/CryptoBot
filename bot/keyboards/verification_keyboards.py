# =================================================================================
# Файл: bot/keyboards/verification_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Клавиатуры для раздела верификации.
# =================================================================================
from typing import Optional
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_verification_info_keyboard(admin_id: Optional[int]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для информационного сообщения о верификации.
    
    :param admin_id: ID главного администратора для связи.
    """
    builder = InlineKeyboardBuilder()
    
    if admin_id:
        # Предполагаем, что главный администратор - первый в списке
        admin_url = f"tg://user?id={admin_id}"
        builder.button(
            text="✍️ Связаться с куратором",
            url=admin_url
        )
        
    return builder.as_markup()