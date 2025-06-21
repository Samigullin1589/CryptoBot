import logging
from typing import Union

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.keyboards import get_main_menu_keyboard # <-- ИСПРАВЛЕННЫЙ ПУТЬ
from bot.utils.helpers import get_message_and_chat_id

router = Router()
logger = logging.getLogger(__name__)

@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    logger.info(f"User {message.from_user.id} started the bot.")
    await message.answer(
        "👋 Добро пожаловать в CryptoBot! Я ваш помощник в мире криптовалют.\n\n"
        "Выберите одну из опций в меню ниже, чтобы начать.",
        reply_markup=get_main_menu_keyboard()
    )

@router.callback_query(F.data == "back_to_main_menu")
async def handle_back_to_main(update: Union[CallbackQuery, Message], state: FSMContext):
    message, _ = await get_message_and_chat_id(update)
    await state.clear()
    await message.edit_text("Главное меню:", reply_markup=get_main_menu_keyboard())