# bot/handlers/admin/stats_handler.py
# =================================================================================
# Файл: bot/handlers/admin/stats_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Единый динамический обработчик для отображения статистики,
# полностью соответствующий архитектуре "тонкий хэндлер".
# =================================================================================
import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.filters.access_filters import PrivilegeFilter, UserRole
from bot.services.admin_service import AdminService
from bot.states.admin_states import AdminStates
from bot.keyboards.admin_keyboards import get_back_to_admin_menu_keyboard
from bot.utils.ui_helpers import edit_or_send_message

stats_router = Router(name=__name__)
logger = logging.getLogger(__name__)

# Применяем фильтр ко всему роутеру
stats_router.callback_query.filter(PrivilegeFilter(min_role=UserRole.ADMIN))


# ИСПРАВЛЕНО: Хэндлер срабатывает из главного меню (состояние AdminStates.main)
@stats_router.callback_query(F.data.startswith("admin_stats:"), AdminStates.main)
async def show_statistics_page(
    callback: CallbackQuery,
    state: FSMContext,
    admin_service: AdminService
):
    """
    Единый динамический обработчик для всех страниц статистики.
    """
    stats_type = callback.data.split(":")[-1]
    
    logger.info(f"Admin {callback.from_user.id} requested statistics page: '{stats_type}'")
    
    await callback.answer(f"Загружаю статистику: {stats_type}...")
    
    # ИСПРАВЛЕНО: Устанавливаем корректное состояние AdminStates.stats_view
    await state.set_state(AdminStates.stats_view)

    try:
        # Вся логика по получению текста и клавиатуры теперь в сервисе
        text, keyboard = await admin_service.get_stats_page_content(stats_type)
        await edit_or_send_message(callback, text, keyboard)

    except KeyError:
        logger.warning(f"Unknown stats_type '{stats_type}' requested by {callback.from_user.id}")
        await edit_or_send_message(
            callback,
            "⚠️ Неизвестный раздел статистики. Пожалуйста, вернитесь в меню.",
            get_back_to_admin_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error getting stats page '{stats_type}': {e}", exc_info=True)
        await edit_or_send_message(
            callback,
            f"❌ Произошла ошибка при загрузке статистики: {e}",
            get_back_to_admin_menu_keyboard()
        )
