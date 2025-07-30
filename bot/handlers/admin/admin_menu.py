# ===============================================================
# Файл: bot/handlers/admin/admin_menu.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Управляет навигацией по админ-панели.
# Полностью интегрирован с PrivilegeFilter, FSM и AdminService.
# ===============================================================
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.filters.access_filters import PrivilegeFilter, UserRole
from bot.services.admin_service import AdminService
from bot.states.admin_states import AdminStates
from bot.texts.admin_texts import ADMIN_MENU_TEXT, SUPER_ADMIN_ONLY_TEXT

admin_router = Router(name=__name__)
# --- УЛУЧШЕНИЕ: Применяем фильтр ко всем хэндлерам в этом роутере ---
admin_router.message.filter(PrivilegeFilter(min_role=UserRole.ADMIN))
admin_router.callback_query.filter(PrivilegeFilter(min_role=UserRole.ADMIN))

logger = logging.getLogger(__name__)

# --- Основной обработчик входа в админ-панель ---

@admin_router.message(Command("admin"))
async def admin_start_handler(message: Message, state: FSMContext, admin_service: AdminService):
    """Обработчик команды /admin. Отображает главное меню."""
    await state.set_state(AdminStates.main_menu)
    # ActionTrackingMiddleware уже залогировал команду /admin
    
    menu_text, menu_keyboard = await admin_service.get_main_menu_content(message.from_user.id)
    await message.answer(menu_text, reply_markup=menu_keyboard)

# --- Обработчик возврата в главное меню ---

@admin_router.callback_query(F.data == "admin:main_menu")
async def admin_menu_callback(call: CallbackQuery, state: FSMContext, admin_service: AdminService):
    """Возвращает пользователя в главное меню админки."""
    await state.set_state(AdminStates.main_menu)
    await call.answer()
    
    menu_text, menu_keyboard = await admin_service.get_main_menu_content(call.from_user.id)
    
    try:
        await call.message.edit_text(menu_text, reply_markup=menu_keyboard)
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение для admin_menu: {e}")
        # Удаляем старое и отправляем новое, если редактирование не удалось
        await call.message.delete()
        await call.message.answer(menu_text, reply_markup=menu_keyboard)

# --- Функции управления системой (для SUPER_ADMIN) ---

@admin_router.callback_query(F.data == "admin_system:clear_asic_cache", PrivilegeFilter(min_role=UserRole.SUPER_ADMIN))
async def clear_asic_cache_callback(call: CallbackQuery, admin_service: AdminService):
    """Обрабатывает нажатие кнопки 'Очистить кэш ASIC'."""
    await call.answer("⏳ Очищаю кэш...", show_alert=False)
    
    try:
        # --- УЛУЧШЕНИЕ: Вызываем сервис без лишних зависимостей ---
        deleted_count = await admin_service.clear_asic_cache()
        
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