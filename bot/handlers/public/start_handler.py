# =============================================================================
# Файл: src/bot/handlers/public/start_handler.py
# Версия: "Distinguished Engineer" — ИСПРАВЛЕНО (28.10.2025)
# Описание: Обработчик базовых команд /start и /help. Экспортирует "router".
# ИСПРАВЛЕНО: Добавлен parse_mode=ParseMode.HTML ко всем message.answer()
# =============================================================================

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ParseMode  # ← ДОБАВЛЕНО
from aiogram.utils.markdown import hbold

# Важно: имя переменной должно быть "router", чтобы _safe_import его нашёл.
router = Router(name="start_handler_router")

HELP_MESSAGE = (
    f"{hbold('ℹ️ Справка по командам бота:')}\n\n"
    "▪️ /start - Перезапустить бота\n"
    "▪️ /game - Открыть игровое меню\n"
    "▪️ /help - Показать это сообщение"
)


@router.message(CommandStart())
async def handle_start(message: Message):
    """
    Обработчик команды /start. Приветствует пользователя.
    
    ИСПРАВЛЕНО: Добавлен parse_mode=ParseMode.HTML
    """
    await message.answer(
        f"Привет, {hbold(message.from_user.full_name)}!",
        parse_mode=ParseMode.HTML  # ← ДОБАВЛЕНО (КРИТИЧНО!)
    )


@router.message(Command("help"))
async def handle_help(message: Message):
    """
    Обработчик команды /help. Отправляет справочное сообщение.
    
    ИСПРАВЛЕНО: Добавлен parse_mode=ParseMode.HTML
    """
    await message.answer(
        HELP_MESSAGE,
        parse_mode=ParseMode.HTML  # ← ДОБАВЛЕНО (КРИТИЧНО!)
    )