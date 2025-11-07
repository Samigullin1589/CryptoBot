# bot/startup/__init__.py
from bot.startup.lifecycle import on_shutdown, on_startup
from bot.startup.polling import start_polling
from bot.startup.setup import setup_bot, setup_dependencies

__all__ = [
    "setup_dependencies",
    "setup_bot",
    "on_startup",
    "on_shutdown",
    "start_polling",
]