# ======================================================================================
# File: bot/handlers/start_handler.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   /start приветствие + кнопка открытия главного меню.
# ======================================================================================

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

router = Router(name="start_public")


def _menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Открыть меню", callback_data="menu:open")],
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    text = (
        "<b>Привет!</b>\n"
        "Я помогу с котировками, новостями и инструментами для крипто.\n"
        "Открой меню — там всё основное."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=_menu_kb())