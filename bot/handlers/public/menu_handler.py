# src/bot/handlers/public/menu_handler.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from loguru import logger

from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.keyboards.callback_factories import PriceCallback, NewsCallback

router = Router(name="menu_public")


def get_quick_actions_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура быстрых действий"""
    buttons = [
        [
            InlineKeyboardButton(
                text="💱 Цена BTC",
                callback_data=PriceCallback(action="show", coin_id="bitcoin").pack()
            ),
            InlineKeyboardButton(
                text="📰 Новости",
                callback_data=NewsCallback(action="sources", source_key=None).pack()
            ),
        ],
        [
            InlineKeyboardButton(text="❓ Справка", callback_data="menu:help"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    """Обработчик команды /menu - показывает главное меню и быстрые действия"""
    # Главное меню
    await message.answer(
        "<b>🎮 Главное меню</b>\n\nВыберите интересующий раздел:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )
    
    # Быстрые действия
    await message.answer(
        "⚡ <b>Быстрые действия:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_quick_actions_keyboard()
    )


@router.callback_query(F.data == "menu:open")
async def cb_open(call: CallbackQuery) -> None:
    """Открытие главного меню через callback"""
    await call.answer()
    
    try:
        await call.message.edit_text(
            "<b>🎮 Главное меню</b>\n\nВыберите интересующий раздел:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error editing menu message: {e}")
        await call.message.answer(
            "<b>🎮 Главное меню</b>\n\nВыберите интересующий раздел:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )


@router.callback_query(F.data == "menu:help")
async def cb_help_shortcut(call: CallbackQuery) -> None:
    """Показ справки через callback из быстрых действий"""
    await call.answer()
    
    help_text = (
        "<b>📖 Справка по боту</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start - Перезапустить бота\n"
        "/menu - Главное меню\n"
        "/game - Майнинг-игра\n"
        "/price - Цены криптовалют\n"
        "/news - Крипто-новости\n"
        "/help - Подробная справка\n\n"
        "<b>Разделы меню:</b>\n"
        "📈 Курс - Актуальные цены криптовалют\n"
        "🏆 Топ ASIC - Лучшие майнеры\n"
        "🕹 Игра - Майнинг-симулятор\n"
        "📰 Новости - Крипто-новости\n"
        "🧮 Калькулятор - Расчёт доходности\n"
        "🛒 Рынок - Покупка/продажа\n"
        "🧭 Центр - Обучение\n"
        "❓ Викторина - Проверка знаний\n\n"
        "Нужна помощь? Напишите /support"
    )
    
    try:
        await call.message.edit_text(
            help_text,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error editing help message: {e}")
        await call.message.answer(
            help_text,
            parse_mode=ParseMode.HTML
        )