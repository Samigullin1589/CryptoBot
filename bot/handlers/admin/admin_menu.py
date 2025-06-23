import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config.settings import settings
from bot.keyboards.admin_keyboards import get_admin_menu_keyboard
from bot.texts.admin_texts import ADMIN_MENU_TEXT

# Создаем новый роутер специально для админских команд
admin_router = Router()
logger = logging.getLogger(__name__)

# Применяем фильтр ко всему роутеру: все обработчики в этом файле
# (и других, подключенных к этому роутеру) будут доступны только админу.
@admin_router.message(Command("admin"))
async def admin_start_handler(message: Message):
    """Обработчик команды /admin."""
    # Проверяем, что команду отправил админ
    if message.from_user.id == settings.admin_chat_id:
        await message.answer(ADMIN_MENU_TEXT, reply_markup=get_admin_menu_keyboard())
    else:
        # Можно ничего не отвечать, чтобы не привлекать внимание
        logger.warning(f"User {message.from_user.id} tried to access admin panel.")