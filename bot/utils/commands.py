from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault
from loguru import logger

async def set_main_menu(bot: Bot):
    """
    Устанавливает команды, которые будут видны пользователю в меню Telegram.
    """
    main_menu_commands = [
        BotCommand(command="/start", description="🚀 Запустить бота"),
        BotCommand(command="/game", description="🎮 Открыть игровое меню"),
        BotCommand(command="/help", description="ℹ️ Помощь по боту"),
    ]
    await bot.set_my_commands(main_menu_commands, BotCommandScopeDefault())
    logger.info("Команды в меню успешно установлены.")