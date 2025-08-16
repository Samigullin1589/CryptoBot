# ======================================================================================
# File: bot/handlers/menu_handler.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   /menu и инлайн-меню с быстрыми действиями: цены, новости, справка.
# ======================================================================================

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router(name="menu_public")


def _menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="💱 Цена BTC", callback_data="menu:price:BTC:USDT"),
            InlineKeyboardButton(text="📰 Новости", callback_data="menu:news"),
        ],
        [
            InlineKeyboardButton(text="❓ Справка", callback_data="menu:help"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer("<b>Главное меню</b>", parse_mode="HTML", reply_markup=_menu_kb())


@router.callback_query(F.data == "menu:open")
async def cb_open(call: CallbackQuery) -> None:
    await call.message.edit_text("<b>Главное меню</b>", parse_mode="HTML", reply_markup=_menu_kb())  # type: ignore[union-attr]
    await call.answer()


@router.callback_query(F.data.startswith("menu:price:"))
async def cb_price_shortcut(call: CallbackQuery, deps) -> None:
    _, _, symbol, quote = (call.data or "").split(":")
    p = await deps.price_service.get_price(symbol, quote)  # type: ignore[attr-defined]
    if p is None:
        await call.answer("Нет данных.")
        return
    from bot.handlers.price_handler import _fmt_price  # reuse formatter
    text = f"<b>{symbol}/{quote}</b>: <code>{_fmt_price(p)}</code>"
    await call.message.answer(text, parse_mode="HTML")  # type: ignore[union-attr]
    await call.answer()


@router.callback_query(F.data == "menu:news")
async def cb_news_shortcut(call: CallbackQuery, deps) -> None:
    from bot.handlers.news_handler import _get_items, _render  # reuse renderer
    items = await _get_items(deps)
    await call.message.answer(_render(items, page=0), parse_mode="HTML", disable_web_page_preview=True)  # type: ignore[union-attr]
    await call.answer()


@router.callback_query(F.data == "menu:help")
async def cb_help_shortcut(call: CallbackQuery) -> None:
    from bot.handlers.help_handler import HELP_TEXT  # reuse text
    await call.message.answer(HELP_TEXT, parse_mode="HTML", disable_web_page_preview=True)  # type: ignore[union-attr]
    await call.answer()