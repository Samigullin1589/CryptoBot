# ===============================================================
# Файл: bot/handlers/admin/stats_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Полностью переработанный модуль для отображения
# статистики. Использует единый динамический обработчик,
# интегрирован с FSM и делегирует всю логику сервисному слою.
# ===============================================================
import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.filters.access_filters import PrivilegeFilter, UserRole
from bot.services.admin_service import AdminService
from bot.states.admin_states import AdminStates

stats_router = Router()
logger = logging.getLogger(__name__)

# Применяем фильтр ко всему роутеру, так как все функции
# в этом модуле требуют прав не ниже Администратора.
stats_router.callback_query.filter(PrivilegeFilter(min_role=UserRole.ADMIN))


@stats_router.callback_query(F.data.startswith("admin_stats_"), AdminStates.main_menu)
async def show_statistics_page(call: CallbackQuery, state: FSMContext, admin_service: AdminService):
    """
    Единый динамический обработчик для всех страниц статистики.
    - Извлекает тип статистики из callback_data (e.g., 'general', 'mining').
    - Вызывает AdminService для получения отформатированного контента.
    - Отображает результат пользователю.
    """
    # Извлекаем тип статистики из 'admin_stats_general' -> 'general'
    stats_type = call.data.removeprefix("admin_stats_")
    
    logger.info(f"Admin {call.from_user.id} requested statistics page: '{stats_type}'")
    await admin_service.track_command_usage(f"📊 Статистика: {stats_type}")
    
    # Отвечаем на callback, чтобы убрать "часики"
    await call.answer(f"Загружаю статистику: {stats_type}...")
    
    # Вся логика по получению и форматированию текста и клавиатуры
    # инкапсулирована в сервисном слое.
    # Это позволяет легко добавлять новые страницы статистики.
    try:
        text, keyboard = await admin_service.get_stats_page_content(stats_type)
        await call.message.edit_text(text, reply_markup=keyboard)
    except KeyError:
        logger.warning(f"Unknown stats_type '{stats_type}' requested by {call.from_user.id}")
        await call.message.edit_text(
            "⚠️ Неизвестный раздел статистики. Пожалуйста, вернитесь в меню.",
            reply_markup=await admin_service.get_back_to_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error getting stats page '{stats_type}': {e}", exc_info=True)
        await call.message.edit_text(
            f"❌ Произошла ошибка при загрузке статистики: {e}",
            reply_markup=await admin_service.get_back_to_main_menu_keyboard()
        )

# ПРИМЕЧАНИЕ ДЛЯ РАЗРАБОТЧИКА:
# Чтобы эта система работала, необходимо убедиться, что:
# 1. В `AdminService` есть метод `get_stats_page_content(stats_type: str) -> (str, InlineKeyboardMarkup)`.
#    Этот метод должен содержать логику для `stats_type` == 'general', 'mining', 'commands'.
#
# 2. В `admin_keyboards.py` клавиатура главного меню админки содержит кнопки
#    с callback_data: "admin_stats_general", "admin_stats_mining", "admin_stats_commands".
#
# 3. В `admin_keyboards.py` есть метод для получения клавиатуры "назад",
#    который вызывается из `admin_service`.
