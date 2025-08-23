# =============================================================================
# Файл: src/bot/handlers/public/start_handler.py
# Версия: "Distinguished Engineer" — ПРОДАКШН-СБОРКА (23 августа 2025)
# Описание: Обработчик базовых команд /start и /help. Экспортирует "router".
# =============================================================================

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
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
    """
    await message.answer(f"Привет, {hbold(message.from_user.full_name)}!")

@router.message(Command("help"))
async def handle_help(message: Message):
    """
    Обработчик команды /help. Отправляет справочное сообщение.
    """
    await message.answer(HELP_MESSAGE)