# ===============================================================
# Файл: bot/keyboards/admin_keyboards.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Полностью переработанный модуль клавиатур для
# админ-панели. Внедрена динамическая генерация кнопок
# на основе ролей (RBAC) и добавлены новые разделы.
# ===============================================================
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from bot.filters.access_filters import UserRole # Импортируем роли для проверки

def get_admin_menu_keyboard(user_role: UserRole) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для главного меню админ-панели.
    Динамически добавляет кнопки в зависимости от уровня доступа администратора.
    
    :param user_role: Роль пользователя, для которого генерируется клавиатура.
    """
    builder = InlineKeyboardBuilder()
    
    # --- Блок кнопок, доступный для ADMIN и выше ---
    if user_role >= UserRole.ADMIN:
        builder.button(text="📊 Статистика", callback_data="admin_nav:stats")
        builder.button(text="📢 Рассылка", callback_data="admin_nav:broadcast")
    
    # --- Блок кнопок, доступный ТОЛЬКО для SUPER_ADMIN ---
    if user_role >= UserRole.SUPER_ADMIN:
        builder.button(text="⚙️ Системные действия", callback_data="admin_nav:system")
        builder.button(text="👤 Управление пользователями", callback_data="admin_nav:user_management")

    builder.adjust(2) # Располагаем кнопки по две в ряд
    return builder.as_markup()

def get_stats_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для раздела "Статистика".
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Общая", callback_data="admin_stats_general")
    builder.button(text="💎 Майнинг-игра", callback_data="admin_stats_mining")
    builder.button(text="📈 Команды", callback_data="admin_stats_commands")
    builder.button(text="⬅️ Назад в админ-панель", callback_data="admin_nav:main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_system_actions_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для раздела "Системные действия".
    Доступно только для SUPER_ADMIN.
    """
    builder = InlineKeyboardBuilder()
    # Используем команду, а не callback, для большей безопасности критических действий
    builder.button(text="🔥 Очистить кэш ASIC", callback_data="admin_action:force_clear_cache")
    builder.button(text="🔄 Перезагрузить конфиг (TBD)", callback_data="admin_action:reload_config")
    builder.button(text="⬅️ Назад в админ-панель", callback_data="admin_nav:main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_back_to_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает универсальную клавиатуру с кнопкой "Назад в админ-панель".
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в админ-панель", callback_data="admin_nav:main_menu")
    return builder.as_markup()
