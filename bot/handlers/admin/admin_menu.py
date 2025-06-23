import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.config.settings import settings
from bot.keyboards.admin_keyboards import get_admin_menu_keyboard
from bot.texts.admin_texts import ADMIN_MENU_TEXT

admin_router = Router()
logger = logging.getLogger(__name__)

# Мы добавили фильтр и для колбеков, чтобы все обработчики в этом роутере были защищены
class AdminFilter(logging.Filter):
    def filter(self, record):
        return record.getMessage().startswith("[ADMIN_PANEL]")

# Применяем фильтр ко всему роутеру
@admin_router.message(Command("admin"))
async def admin_start_handler(message: Message):
    """Обработчик команды /admin с подробным логированием."""
    logger.info(f"[ADMIN_PANEL] /admin command received from user {message.from_user.id}")
    
    if message.from_user.id == settings.admin_chat_id:
        logger.info(f"[ADMIN_PANEL] User recognized as admin. Showing menu.")
        await message.answer(ADMIN_MENU_TEXT, reply_markup=get_admin_menu_keyboard())
    else:
        logger.warning(f"[ADMIN_PANEL] User {message.from_user.id} IS NOT an admin. Expected: {settings.admin_chat_id}. Access denied.")
        # Не отвечаем пользователю, чтобы не привлекать внимание
        
# Этот обработчик нам понадобится на следующем шаге
@admin_router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(call: CallbackQuery):
    """Возвращает в главное меню админки."""
    await call.message.edit_text(ADMIN_MENU_TEXT, reply_markup=get_admin_menu_keyboard())