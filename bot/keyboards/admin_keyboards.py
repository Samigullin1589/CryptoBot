# ===============================================================
# Файл: bot/keyboards/admin_keyboards.py (НОВЫЙ ФАЙЛ)
# Описание: Генераторы клавиатур для админ-панели.
# ===============================================================
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from bot.filters.access_filters import UserRole

def get_admin_menu_keyboard(user_role: UserRole) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin:stats_menu")
    # Кнопки ниже доступны только для SUPER_ADMIN
    if user_role >= UserRole.SUPER_ADMIN:
        builder.button(text="⚙️ Система", callback_data="admin:system_menu")
        builder.button(text="📮 Рассылка", callback_data="admin:broadcast")
    builder.adjust(1)
    return builder.as_markup()

def get_stats_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Общая", callback_data="admin_stats:general")
    builder.button(text="💎 Игровая", callback_data="admin_stats:mining")
    builder.button(text="📈 Команды", callback_data="admin_stats:commands")
    builder.button(text="⬅️ Назад", callback_data="admin:main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_system_actions_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Очистить кэш ASIC", callback_data="admin_system:clear_asic_cache")
    builder.button(text="⬅️ Назад", callback_data="admin:main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_back_to_admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню админа", callback_data="admin:main_menu")
    return builder.as_markup()