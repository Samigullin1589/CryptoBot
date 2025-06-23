import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from bot.config.settings import settings
from bot.filters.admin_filter import IsAdmin # Импортируем наш новый фильтр
from bot.keyboards.admin_keyboards import get_admin_menu_keyboard
from bot.texts.admin_texts import ADMIN_MENU_TEXT

admin_router = Router()
logger = logging.getLogger(__name__)

# Применяем фильтр ко всему роутеру.
# Теперь все обработчики в этом файле будут доступны только админу.
admin_router.message.filter(IsAdmin())
admin_router.callback_query.filter(IsAdmin())


@admin_router.message(Command("admin"))
async def admin_start_handler(message: Message):
    """
    Обработчик команды /admin. Проверка на админа теперь происходит в фильтре.
    """
    await message.answer(ADMIN_MENU_TEXT, reply_markup=get_admin_menu_keyboard())

# Этот обработчик нам понадобится на следующем шаге для кнопки "Назад"
@admin_router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(call: CallbackQuery):
    """
    Возвращает в главное меню админки.
    """
    await call.message.edit_text(ADMIN_MENU_TEXT, reply_markup=get_admin_menu_keyboard())