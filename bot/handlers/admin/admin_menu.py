# ===============================================================
# Файл: bot/handlers/admin/admin_menu.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Файл переработан для использования FSM и более гибкой
# системы фильтров. Добавлен функционал управления кэшем
# с доступом на уровне SUPER_ADMIN.
# ===============================================================
import logging
import redis.asyncio as redis
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

# Используем более гибкий PrivilegeFilter для гранулярного контроля доступа
from bot.filters.access_filters import PrivilegeFilter, UserRole
from bot.keyboards.admin_keyboards import get_admin_menu_keyboard
from bot.services.admin_service import AdminService
from bot.states.admin_states import AdminStates # Импортируем состояния
from bot.texts.admin_texts import ADMIN_MENU_TEXT, SUPER_ADMIN_ONLY_TEXT

admin_router = Router()
logger = logging.getLogger(__name__)

# --- Основной обработчик входа в админ-панель ---

@admin_router.message(Command("admin"), PrivilegeFilter(min_role=UserRole.ADMIN))
async def admin_start_handler(message: Message, state: FSMContext, admin_service: AdminService):
    """
    Обработчик команды /admin.
    - Проверяет права доступа (АДМИН и выше) через фильтр.
    - Устанавливает состояние FSM для навигации по админ-панели.
    - Логирует вход и отображает главное меню.
    """
    await state.set_state(AdminStates.main_menu)
    await admin_service.track_admin_entry(message.from_user.id)
    
    # Логика формирования меню инкапсулирована в сервисе для большей гибкости
    # Это позволит, например, показывать разное меню для ADMIN и SUPER_ADMIN
    menu_text, menu_keyboard = await admin_service.get_main_menu_content(message.from_user.id)
    
    await message.answer(menu_text, reply_markup=menu_keyboard)

# --- Обработчик возврата в главное меню ---

@admin_router.callback_query(F.data == "admin_menu", PrivilegeFilter(min_role=UserRole.ADMIN))
async def admin_menu_callback(call: CallbackQuery, state: FSMContext, admin_service: AdminService):
    """
    Возвращает пользователя в главное меню админки из любого другого раздела.
    - Сбрасывает состояние на main_menu.
    - Редактирует сообщение, чтобы показать главное меню.
    """
    await state.set_state(AdminStates.main_menu)
    await admin_service.track_command_usage("Админ-меню (возврат)")
    
    # Улучшение UX: отвечаем на callback, чтобы убрать "часики" на кнопке
    await call.answer() 
    
    menu_text, menu_keyboard = await admin_service.get_main_menu_content(call.from_user.id)
    
    # Используем try-except для предотвращения ошибок, если сообщение не может быть отредактировано
    try:
        await call.message.edit_text(menu_text, reply_markup=menu_keyboard)
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение для admin_menu: {e}")
        # Если редактирование не удалось, отправляем новое сообщение
        await call.message.answer(menu_text, reply_markup=menu_keyboard)

# --- Функции управления системой (для SUPER_ADMIN) ---

@admin_router.message(Command("force_clear_cache"), PrivilegeFilter(min_role=UserRole.SUPER_ADMIN))
async def force_clear_cache_handler(message: Message, admin_service: AdminService, redis_client: redis.Redis):
    """
    Принудительно очищает кэш ASIC из Redis.
    Доступно только для SUPER_ADMIN.
    """
    user_id = message.from_user.id
    logger.warning(f"SUPER_ADMIN {user_id} инициировал принудительную очистку кэша ASIC.")
    await admin_service.track_command_usage(f"/force_clear_cache by {user_id}")

    try:
        # Логика очистки кэша делегирована сервису
        deleted_count = await admin_service.clear_asic_cache(redis_client)
        
        if deleted_count > 0:
            response_text = (f"✅ Успешно удалено <b>{deleted_count}</b> ключей из кэша Redis.\n\n"
                             "Данные по ASIC будут полностью перезагружены при следующем запросе.")
        else:
            response_text = "ℹ️ Кэш ASIC уже был пуст. Удалять нечего."
            
        await message.answer(response_text)
            
    except Exception as e:
        logger.error(f"Критическая ошибка при очистке кэша по команде администратора {user_id}: {e}", exc_info=True)
        await message.answer(f"❌ Произошла ошибка при очистке кэша: {e}")


@admin_router.message(Command("super"), PrivilegeFilter(min_role=UserRole.SUPER_ADMIN))
async def super_admin_only_handler(message: Message, admin_service: AdminService):
    """
    Пример обработчика, доступного ТОЛЬКО для СУПЕР-АДМИНА.
    Это стало возможно благодаря применению фильтров на уровне хэндлеров,
    а не всего роутера.
    """
    await admin_service.track_command_usage(f"/super by {message.from_user.id}")
    await message.answer(SUPER_ADMIN_ONLY_TEXT)
