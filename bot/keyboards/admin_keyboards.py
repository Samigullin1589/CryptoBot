# =================================================================================
# Файл: bot/keyboards/admin_keyboards.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ПОЛНАЯ И ОКОНЧАТЕЛЬНАЯ)
# Описание: Клавиатуры для основной и игровой админ-панели.
# =================================================================================

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

GAME_ADMIN_CALLBACK_PREFIX = "game_admin"

def get_main_admin_keyboard() -> InlineKeyboardMarkup:
    """Основная клавиатура админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Глобальная статистика", callback_data="admin:stats"))
    builder.row(InlineKeyboardButton(text="🎮 Управление Игрой", callback_data=f"{GAME_ADMIN_CALLBACK_PREFIX}:menu"))
    builder.row(InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="admin:mailing_start"))
    return builder.as_markup()

def get_game_admin_menu_keyboard(stats: dict) -> InlineKeyboardMarkup:
    """Клавиатура главного меню управления игрой."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"Активные сессии: {stats.get('active_sessions', 'N/A')}", callback_data="do_nothing"))
    builder.row(InlineKeyboardButton(text=f"Общий баланс в игре: {stats.get('total_balance', 0.0):,.2f} монет", callback_data="do_nothing"))
    builder.row(InlineKeyboardButton(text=f"Заявок на вывод: {stats.get('pending_withdrawals', 'N/A')}", callback_data="do_nothing"))
    builder.row(InlineKeyboardButton(text="💰 Изменить баланс пользователя", callback_data=f"{GAME_ADMIN_CALLBACK_PREFIX}:balance_start"))
    builder.row(InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="admin:menu"))
    return builder.as_markup()

def get_back_to_game_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой "Назад" в меню управления игрой."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"{GAME_ADMIN_CALLBACK_PREFIX}:menu"))
    return builder.as_markup()

def get_confirm_mailing_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения рассылки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить всем", callback_data="admin:mailing_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:mailing_cancel")
    )
    return builder.as_markup()