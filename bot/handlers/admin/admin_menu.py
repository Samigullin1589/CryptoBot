# ===============================================================
# Файл: bot/handlers/admin/admin_menu.py (БЕЗ ИЗМЕНЕНИЙ)
# Описание: Этот файл уже написан правильно.
# ===============================================================
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.filters.admin_filter import IsAdminFilter
from bot.keyboards.admin_keyboards import get_admin_menu_keyboard
from bot.services.admin_service import AdminService
from bot.texts.admin_texts import ADMIN_MENU_TEXT

admin_router = Router()
logger = logging.getLogger(__name__)

# Применяем фильтр ко всему роутеру.
# Теперь все обработчики в этом файле будут доступны только админу.
admin_router.message.filter(IsAdminFilter())
admin_router.callback_query.filter(IsAdminFilter())


@admin_router.message(Command("admin"))
async def admin_start_handler(message: Message, admin_service: AdminService):
    """
    Обработчик команды /admin. Проверка на админа теперь происходит в фильтре.
    """
    await admin_service.track_command_usage("/admin")
    await message.answer(ADMIN_MENU_TEXT, reply_markup=get_admin_menu_keyboard())


@admin_router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(call: CallbackQuery, admin_service: AdminService):
    """
    Возвращает в главное меню админки.
    """
    await admin_service.track_command_usage("Админ-меню (возврат)")
    await call.message.edit_text(ADMIN_MENU_TEXT, reply_markup=get_admin_menu_keyboard())
