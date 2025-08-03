# =================================================================================
# Файл: bot/keyboards/admin_keyboards.py (ВЕРСИЯ "ГЕНИЙ 3.0" - АВГУСТ 2025)
# Описание: Полный набор клавиатур для админ-панели, включая RBAC и системные действия.
# Синхронизирован с AdminService.
# =================================================================================

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импортируем UserRole для реализации RBAC в клавиатурах
# Убедитесь, что этот путь импорта корректен в вашей структуре
from bot.filters.access_filters import UserRole

# Константы для callback data - стандартная практика для предотвращения ошибок
ADMIN_CB_PREFIX = "admin"
# Используем двоеточие как разделитель для иерархии callback-ов
STATS_CB_PREFIX = f"{ADMIN_CB_PREFIX}:stats"
SYSTEM_CB_PREFIX = f"{ADMIN_CB_PREFIX}:system"
GAME_ADMIN_CALLBACK_PREFIX = "game_admin" # Оставляем для совместимости с игровой админкой

# =================================================================
# 1. Главное меню админки (с учетом ролей)
# =================================================================

def get_admin_menu_keyboard(user_role: UserRole) -> InlineKeyboardMarkup:
    """
    Генерирует главное меню администратора с учетом роли пользователя (RBAC).
    Это заменяет get_main_admin_keyboard и соответствует требованиям AdminService.
    """
    builder = InlineKeyboardBuilder()

    # Кнопки, доступные всем администраторам и модераторам
    builder.button(text="📊 Статистика", callback_data=f"{ADMIN_CB_PREFIX}:stats_menu")
    builder.button(text="🎮 Управление Игрой", callback_data=f"{GAME_ADMIN_CALLBACK_PREFIX}:menu")
    
    # Кнопки, доступные только Администраторам и Владельцу
    # ПРИМЕЧАНИЕ: Предполагается, что UserRole.ADMIN и UserRole.OWNER определены в access_filters
    # Адаптируйте этот список, если ваша иерархия ролей отличается.
    if user_role in [UserRole.ADMIN, UserRole.OWNER]:
        builder.button(text="📢 Рассылка", callback_data=f"{ADMIN_CB_PREFIX}:mailing_start")
        builder.button(text="⚙️ Системные действия", callback_data=f"{ADMIN_CB_PREFIX}:system_menu")

    # Адаптивная раскладка (по 2 кнопки в ряд)
    builder.adjust(2)
    return builder.as_markup()

# =================================================================
# 2. Меню статистики (Новая функция, требуется AdminService)
# =================================================================

def get_stats_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Меню выбора категории статистики.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Общая (Пользователи)", callback_data=f"{STATS_CB_PREFIX}:general")
    builder.button(text="💎 Игровая (Майнинг)", callback_data=f"{STATS_CB_PREFIX}:mining")
    builder.button(text="📈 Топ действий", callback_data=f"{STATS_CB_PREFIX}:commands")
    
    # Используем adjust перед добавлением ряда с кнопкой "Назад"
    builder.adjust(1) 
    builder.row(get_back_to_admin_button())
    return builder.as_markup()

# =================================================================
# 3. Меню системных действий (Новая функция, требуется AdminService)
# =================================================================

def get_system_actions_keyboard() -> InlineKeyboardMarkup:
    """
    Меню для выполнения системных операций.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Очистить кэш ASIC", callback_data=f"{SYSTEM_CB_PREFIX}:clear_asic_cache")
    # Можно добавить другие действия: перезагрузка конфигов, диагностика и т.д.
    
    builder.adjust(1)
    builder.row(get_back_to_admin_button())
    return builder.as_markup()

# =================================================================
# 4. Утилиты навигации (Принцип DRY)
# =================================================================

def get_back_to_admin_button() -> InlineKeyboardButton:
    """Возвращает стандартную кнопку для возврата в главное админ-меню."""
    return InlineKeyboardButton(text="🔙 Назад в Админ-панель", callback_data=f"{ADMIN_CB_PREFIX}:menu")

def get_back_to_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Универсальная клавиатура для возврата в главное админ-меню."""
    builder = InlineKeyboardBuilder()
    builder.add(get_back_to_admin_button())
    return builder.as_markup()

# =================================================================
# 5. Существующие клавиатуры (Игровая админка и Рассылка)
#    Интегрируем их в новую структуру.
# =================================================================

def get_game_admin_menu_keyboard(stats: dict) -> InlineKeyboardMarkup:
    """Клавиатура главного меню управления игрой."""
    builder = InlineKeyboardBuilder()
    # Информационные кнопки (callback_data="do_nothing" предотвращает "загрузку" в интерфейсе Telegram)
    builder.row(InlineKeyboardButton(text=f"Активные сессии: {stats.get('active_sessions', 'N/A')}", callback_data="do_nothing"))
    builder.row(InlineKeyboardButton(text=f"Общий баланс: {stats.get('total_balance', 0.0):,.2f} монет", callback_data="do_nothing"))
    builder.row(InlineKeyboardButton(text=f"Заявок на вывод: {stats.get('pending_withdrawals', 'N/A')}", callback_data="do_nothing"))
    
    # Кнопки действий
    builder.row(InlineKeyboardButton(text="💰 Изменить баланс пользователя", callback_data=f"{GAME_ADMIN_CALLBACK_PREFIX}:balance_start"))
    builder.row(get_back_to_admin_button()) # Используем общую кнопку Назад
    return builder.as_markup()

def get_back_to_game_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой "Назад" в меню управления игрой."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад к Управлению Игрой", callback_data=f"{GAME_ADMIN_CALLBACK_PREFIX}:menu"))
    return builder.as_markup()

def get_confirm_mailing_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения рассылки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить всем", callback_data=f"{ADMIN_CB_PREFIX}:mailing_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"{ADMIN_CB_PREFIX}:mailing_cancel")
    )
    return builder.as_markup()