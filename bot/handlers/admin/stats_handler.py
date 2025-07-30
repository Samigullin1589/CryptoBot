# ===============================================================
# Файл: bot/handlers/admin/stats_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: Единый динамический обработчик для отображения статистики,
# полностью соответствующий архитектуре "тонкий хэндлер".
# ===============================================================
import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.filters.access_filters import PrivilegeFilter, UserRole
from bot.services.admin_service import AdminService
from bot.states.admin_states import AdminStates
# --- УЛУЧШЕНИЕ: Импортируем клавиатуру напрямую ---
from bot.keyboards.admin_keyboards import get_back_to_admin_menu_keyboard

stats_router = Router(name=__name__)
logger = logging.getLogger(__name__)

# Применяем фильтр ко всему роутеру
stats_router.callback_query.filter(PrivilegeFilter(min_role=UserRole.ADMIN))


@stats_router.callback_query(F.data.startswith("admin_stats:"), AdminStates.main_menu)
async def show_statistics_page(call: CallbackQuery, state: FSMContext, admin_service: AdminService):
    """
    Единый динамический обработчик для всех страниц статистики.
    """
    # --- УЛУЧШЕНИЕ: Синхронизируем парсинг с форматом клавиатуры ---
    stats_type = call.data.split(":")[-1]
    
    logger.info(f"Admin {call.from_user.id} requested statistics page: '{stats_type}'")
    # --- УЛУЧШЕНИЕ: Удален ручной вызов трекинга, т.к. работает Middleware ---
    
    await call.answer(f"Загружаю статистику: {stats_type}...")
    
    # Устанавливаем состояние, чтобы показать, где находится админ
    await state.set_state(AdminStates.stats_menu)

    try:
        text, keyboard = await admin_service.get_stats_page_content(stats_type)
        await call.message.edit_text(text, reply_markup=keyboard)
    except KeyError:
        logger.warning(f"Unknown stats_type '{stats_type}' requested by {call.from_user.id}")
        await call.message.edit_text(
            "⚠️ Неизвестный раздел статистики. Пожалуйста, вернитесь в меню.",
            # --- УЛУЧШЕНИЕ: Хэндлер сам создает клавиатуру ---
            reply_markup=get_back_to_admin_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error getting stats page '{stats_type}': {e}", exc_info=True)
        await call.message.edit_text(
            f"❌ Произошла ошибка при загрузке статистики: {e}",
            reply_markup=get_back_to_admin_menu_keyboard()
        )