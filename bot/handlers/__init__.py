# =============================================================================
# Файл: src/bot/handlers/__init__.py
# Описание: Главный агрегатор роутеров со всех модулей приложения.
# =============================================================================

from aiogram import Router
from .public import public_router # Импортируем уже собранный роутер
# from .admin import admin_router # Аналогично для других модулей

main_router = Router(name="main_router")

main_router.include_router(public_router)
# main_router.include_router(admin_router)