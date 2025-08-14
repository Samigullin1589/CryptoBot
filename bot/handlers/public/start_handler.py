import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.main_menu_keyboards import get_main_menu_keyboard

router = Router(name="public_start")
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    """
    Показываем главное меню сразу по /start.
    """
    text = "👋 Добро пожаловать! Выберите раздел:"
    try:
        await message.answer(text, reply_markup=get_main_menu_keyboard())
    except Exception as e:
        logger.error("Failed to send main menu on /start: %s", e, exc_info=True)
        # На крайний случай хотя бы текст
        try:
            await message.answer(text)
        except Exception:
            pass