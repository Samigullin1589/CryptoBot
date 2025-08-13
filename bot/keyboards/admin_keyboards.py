# =================================================================================
# Файл: bot/keyboards/admin_keyboards.py (ВЕРСИЯ "ГЕНИЙ 3.0" - АВГУСТ 2025 - ИСПРАВЛЕННАЯ)
# Описание: Полный набор клавиатур для админ-панели, включая RBAC и системные действия.
# ИСПРАВЛЕНИЕ: Удалена устаревшая константа GAME_ADMIN_CALLBACK_PREFIX.
# =================================================================================

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ИСПРАВЛЕНО: Импортируем UserRole из нового, безопасного места
from bot.utils.models import UserRole
from .callback_factories import AdminCallback, GameAdminCallback

# Константы для callback data - стандартная практика для предотвращения ошибок
ADMIN_CB_PREFIX = "admin"
# Используем двоеточие как разделитель для иерархии callback-ов
STATS_CB_PREFIX = f"{ADMIN_CB_PREFIX}:stats"
SYSTEM_CB_PREFIX = f"{ADMIN_CB_PREFIX}:system"

# =================================================================
# 1. Главное меню админки (с учетом ролей)
# =================================================================

def get_admin_menu_keyboard(user_role: UserRole) -> InlineKeyboardMarkup:
    """
    Генерирует главное меню администратора с учетом роли пользователя (RBAC).
    """
    builder = InlineKeyboardBuilder()

    # Кнопки, доступные всем администраторам и модераторам
    builder.button(text="📊 Статистика", callback_data=AdminCallback(action="stats_menu").pack())
    builder.button(text="🎮 Управление Игрой", callback_data=GameAdminCallback(action="menu").pack())
    
    # Кнопки, доступные только Администраторам и Супер-Админам
    if user_role >= UserRole.ADMIN:
        builder.button(text="📢 Рассылка", callback_data=AdminCallback(action="mailing_start").pack())
        builder.button(text="⚙️ Системные действия", callback_data=AdminCallback(action="system_menu").pack())

    # Адаптивная раскладка (по 2 кнопки в ряд)
    builder.adjust(2)
    return builder.as_markup()

# =================================================================
# 2. Меню статистики
# =================================================================

def get_stats_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Меню выбора категории статистики.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Общая (Пользователи)", callback_data=f"{STATS_CB_PREFIX}:general")
    builder.button(text="💎 Игровая (Майнинг)", callback_data=f"{STATS_CB_PREFIX}:mining")
    builder.button(text="📈 Топ действий", callback_data=f"{STATS_CB_PREFIX}:commands")
    
    builder.adjust(1) 
    builder.row(get_back_to_admin_button())
    return builder.as_markup()

# =================================================================
# 3. Меню системных действий
# =================================================================

def get_system_actions_keyboard() -> InlineKeyboardMarkup:
    """
    Меню для выполнения системных операций.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Очистить кэш ASIC", callback_data=f"{SYSTEM_CB_PREFIX}:clear_asic_cache")
    
    builder.adjust(1)
    builder.row(get_back_to_admin_button())
    return builder.as_markup()

# =================================================================
# 4. Утилиты навигации
# =================================================================

def get_back_to_admin_button() -> InlineKeyboardButton:
    """Возвращает стандартную кнопку для возврата в главное админ-меню."""
    return InlineKeyboardButton(text="🔙 Назад в Админ-панель", callback_data=AdminCallback(action="menu").pack())

def get_back_to_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Универсальная клавиатура для возврата в главное админ-меню."""
    builder = InlineKeyboardBuilder()
    builder.add(get_back_to_admin_button())
    return builder.as_markup()

# =================================================================
# 5. Клавиатуры игровой админки и рассылки
# =================================================================

def get_game_admin_menu_keyboard(stats: dict) -> InlineKeyboardMarkup:
    """Клавиатура главного меню управления игрой."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"Активные сессии: {stats.get('active_sessions', 'N/A')}", callback_data="do_nothing"))
    builder.row(InlineKeyboardButton(text=f"Общий баланс: {stats.get('total_balance', 0.0):,.2f} монет", callback_data="do_nothing"))
    builder.row(InlineKeyboardButton(text=f"Заявок на вывод: {stats.get('pending_withdrawals', 'N/A')}", callback_data="do_nothing"))
    
    builder.row(InlineKeyboardButton(text="💰 Изменить баланс пользователя", callback_data=GameAdminCallback(action="balance_start").pack()))
    builder.row(get_back_to_admin_button())
    return builder.as_markup()

def get_back_to_game_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой "Назад" в меню управления игрой."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад к Управлению Игрой", callback_data=GameAdminCallback(action="menu").pack()))
    return builder.as_markup()

def get_confirm_mailing_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения рассылки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить всем", callback_data=f"{ADMIN_CB_PREFIX}:mailing_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"{ADMIN_CB_PREFIX}:mailing_cancel")
    )
    return builder.as_markup()