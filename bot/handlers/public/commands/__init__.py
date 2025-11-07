# bot/handlers/public/commands/__init__.py
"""
Модуль команд бота.
"""

from aiogram import Router

from bot.handlers.public.commands.start import router as start_router
from bot.handlers.public.commands.info import router as info_router
from bot.handlers.public.commands.tools import router as tools_router
from bot.handlers.public.commands.social import router as social_router
from bot.handlers.public.commands.premium import router as premium_router
from bot.handlers.public.commands.technical import router as technical_router
from bot.handlers.public.commands.buttons import router as buttons_router
from bot.handlers.public.commands.callbacks import router as callbacks_router

# Главный роутер
router = Router(name="commands_main_router")

# Подключаем все под-роутеры
router.include_router(start_router)
router.include_router(info_router)
router.include_router(tools_router)
router.include_router(social_router)
router.include_router(premium_router)
router.include_router(technical_router)
router.include_router(buttons_router)
router.include_router(callbacks_router)

__all__ = ["router"]