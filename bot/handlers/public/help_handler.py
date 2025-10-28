# ======================================================================================
# File: bot/handlers/help_handler.py
# Version: "Distinguished Engineer" — ИСПРАВЛЕНО (28.10.2025)
# Description:
#   /help — краткая справка по командам и подсказки по текстовому вводу.
# ИСПРАВЛЕНО: parse_mode="HTML" заменён на ParseMode.HTML (enum)
# ======================================================================================

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode  # ← ДОБАВЛЕНО

router = Router(name="help_public")

HELP_TEXT = (
    "<b>Справка</b>\n"
    "• <code>/menu</code> — главное меню\n"
    "• <code>/price BTC USDT</code> — показать цену пары (по умолчанию BTC/USDT)\n"
    "• <code>/news</code> — свежие крипто-новости\n"
    "\n"
    "<b>Подсказки</b>\n"
    "• Можно писать просто: <code>btc</code>, <code>eth/usdt</code>, <code>btc usd</code> — бот поймёт.\n"
    "• Админам доступны: <code>/health</code>, <code>/cache_info</code>, <code>/cache_clear</code>, "
    "<code>/version</code>, <code>/ban</code>, <code>/unban</code>, <code>/mute</code>, <code>/warn</code>, <code>/pardon</code>.\n"
)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """
    Обработчик команды /help.
    
    ИСПРАВЛЕНО: parse_mode="HTML" → ParseMode.HTML
    """
    await message.answer(
        HELP_TEXT,
        parse_mode=ParseMode.HTML,  # ← ИСПРАВЛЕНО
        disable_web_page_preview=True
    )