# bot/handlers/common_handlers.py
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

# Обновленный импорт для работы с новой структурой
from bot.utils.keyboards import get_main_menu_keyboard

router = Router()

@router.message(CommandStart())
async def handle_start(message: Message):
    await message.answer("👋 Привет! Я ваш крипто-помощник.", reply_markup=get_main_menu_keyboard())

@router.message(Command('menu'))
async def handle_menu_command(message: Message):
    await message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())

@router.callback_query(F.data == "back_to_main_menu")
async def handle_back_to_main(call: CallbackQuery):
    await call.message.edit_text("Главное меню:", reply_markup=get_main_menu_keyboard())
    await call.answer()
