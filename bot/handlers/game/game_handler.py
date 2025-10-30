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


logger.info("✅ Game handler loaded")