from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_admin_menu_keyboard():
    """Создает клавиатуру для главного меню панели администратора."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Общая статистика", callback_data="admin_stats_general")
    builder.button(text="💎 Статистика майнинга", callback_data="admin_stats_mining")
    builder.button(text="📈 Статистика команд", callback_data="admin_stats_commands")
    builder.adjust(1)
    return builder.as_markup()