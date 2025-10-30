# bot/handlers/game/game_handler.py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.keyboards.callback_factories import GameCallback
from bot.utils.dependencies import Deps

router = Router(name="game_handler")


@router.message(Command("game"))
async def cmd_game(message: Message, deps: Deps) -> None:
    """Команда /game - запуск игры"""
    try:
        text = (
            "🎮 <b>Майнинг-симулятор</b>\n\n"
            "Добро пожаловать в игру!\n\n"
            "Здесь вы можете:\n"
            "⛏️ Майнить криптовалюту\n"
            "💰 Зарабатывать монеты\n"
            "🏆 Получать достижения\n\n"
            "Используйте команды для управления игрой."
        )
        
        await message.answer(text, parse_mode="HTML")
        logger.info(f"User {message.from_user.id} started game via /game")
        
    except Exception as e:
        logger.error(f"Error in cmd_game: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка при запуске игры.")


@router.callback_query(GameCallback.filter(F.action == "main_menu"))
async def game_main_menu(call: CallbackQuery, deps: Deps) -> None:
    """Главное меню игры из кнопки"""
    try:
        await call.answer()
        
        text = (
            "🎮 <b>Майнинг-симулятор</b>\n\n"
            "Добро пожаловать в игру!\n\n"
            "Здесь вы можете:\n"
            "⛏️ Майнить криптовалюту\n"
            "💰 Зарабатывать монеты\n"
            "🏆 Получать достижения\n\n"
            "Используйте команды для управления игрой."
        )
        
        await call.message.edit_text(text, parse_mode="HTML")
        logger.info(f"User {call.from_user.id} opened game main menu")
        
    except Exception as e:
        logger.error(f"Error in game_main_menu: {e}", exc_info=True)
        try:
            await call.answer("⚠️ Произошла ошибка", show_alert=True)
        except Exception:
            pass


@router.callback_query(GameCallback.filter())
async def game_callback_handler(call: CallbackQuery, callback_data: GameCallback, deps: Deps) -> None:
    """Обработчик всех остальных game коллбеков"""
    try:
        await call.answer()
        
        action = callback_data.action
        logger.info(f"User {call.from_user.id} triggered game action: {action}")
        
        # Здесь можно добавить обработку других действий
        await call.answer(f"Действие '{action}' в разработке", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error in game_callback_handler: {e}", exc_info=True)
        await call.answer("⚠️ Ошибка", show_alert=True)


logger.info("✅ Game handler loaded")