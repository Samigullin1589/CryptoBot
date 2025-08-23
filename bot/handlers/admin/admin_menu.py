# ===============================================================
# Файл: bot/handlers/admin/admin_menu.py (ПРОДАКШН-ВЕРСИЯ 2025 - ПОЛНАЯ НАВИГАЦИЯ)
# Описание: Управляет навигацией по админ-панели.
# ИСПРАВЛЕНИЕ: Внедрение зависимостей унифицировано через deps: Deps.
# ===============================================================
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.filters.access_filters import PrivilegeFilter, UserRole
from bot.states.admin_states import AdminStates
from bot.texts.admin_texts import SUPER_ADMIN_ONLY_TEXT
from bot.keyboards.admin_keyboards import get_stats_menu_keyboard, get_back_to_admin_menu_keyboard, get_system_actions_keyboard
from bot.keyboards.callback_factories import AdminCallback
from bot.utils.dependencies import Deps

admin_router = Router(name=__name__)
# Применяем фильтр ко всем хэндлерам в этом роутере
admin_router.message.filter(PrivilegeFilter(min_role=UserRole.ADMIN))
admin_router.callback_query.filter(PrivilegeFilter(min_role=UserRole.ADMIN))

logger = logging.getLogger(__name__)

# --- Основной обработчик входа в админ-панель ---

@admin_router.message(Command("admin"))
async def admin_start_handler(message: Message, state: FSMContext, deps: Deps):
    """Обработчик команды /admin. Отображает главное меню."""
    await state.set_state(AdminStates.main)
    
    menu_text, menu_keyboard = await deps.admin_service.get_main_menu_content(message.from_user.id)
    await message.answer(menu_text, reply_markup=menu_keyboard)

# --- Обработчик возврата в главное меню ---

@admin_router.callback_query(AdminCallback.filter(F.action == "menu"))
async def admin_menu_callback(call: CallbackQuery, state: FSMContext, deps: Deps):
    """Возвращает пользователя в главное меню админки."""
    await state.set_state(AdminStates.main)
    await call.answer()
    
    menu_text, menu_keyboard = await deps.admin_service.get_main_menu_content(call.from_user.id)
    
    try:
        await call.message.edit_text(menu_text, reply_markup=menu_keyboard)
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение для admin_menu: {e}")
        await call.message.delete()
        await call.message.answer(menu_text, reply_markup=menu_keyboard)

# --- НОВЫЙ ОБРАБОТЧИК ДЛЯ МЕНЮ СТАТИСТИКИ ---
@admin_router.callback_query(AdminCallback.filter(F.action == "stats_menu"), AdminStates.main)
async def admin_stats_menu_handler(call: CallbackQuery, state: FSMContext):
    """
    Показывает меню выбора категорий статистики.
    """
    await call.answer()
    await state.set_state(AdminStates.stats_view)
    text = "<b>📊 Статистика Бота</b>\n\nВыберите категорию для просмотра:"
    await call.message.edit_text(text, reply_markup=get_stats_menu_keyboard())

# --- Функции управления системой (для SUPER_ADMIN) ---
@admin_router.callback_query(AdminCallback.filter(F.action == "system_menu"), AdminStates.main)
async def admin_system_menu_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(AdminStates.main) # Остаемся в главном состоянии, но показываем другое меню
    text = "<b>⚙️ Системные действия</b>\n\nВыберите действие:"
    await call.message.edit_text(text, reply_markup=get_system_actions_keyboard())


@admin_router.callback_query(AdminCallback.filter(F.action == "system:clear_asic_cache"), PrivilegeFilter(min_role=UserRole.SUPER_ADMIN))
async def clear_asic_cache_callback(call: CallbackQuery, deps: Deps):
    """Обрабатывает нажатие кнопки 'Очистить кэш ASIC'."""
    await call.answer("⏳ Очищаю кэш...", show_alert=False)
    
    try:
        deleted_count = await deps.admin_service.clear_asic_cache()
        
        if deleted_count > 0:
            response_text = (f"✅ Успешно удалено <b>{deleted_count}</b> ключей из кэша ASIC.\n\n"
                             "Данные будут полностью перезагружены при следующем запросе.")
        else:
            response_text = "ℹ️ Кэш ASIC уже был пуст. Удалять нечего."
    except Exception as e:
        logger.error(f"Ошибка при очистке кэша по запросу администратора {call.from_user.id}: {e}", exc_info=True)
        response_text = f"❌ Произошла ошибка при очистке кэша: {e}"
    
    await call.message.edit_text(response_text, reply_markup=get_back_to_admin_menu_keyboard())


@admin_router.message(Command("super"), PrivilegeFilter(min_role=UserRole.SUPER_ADMIN))
async def super_admin_only_handler(message: Message):
    """Пример обработчика, доступного ТОЛЬКО для СУПЕР-АДМИНА."""
    await message.answer(SUPER_ADMIN_ONLY_TEXT)