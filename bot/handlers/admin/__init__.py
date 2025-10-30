# bot/handlers/admin/__init__.py
from aiogram import Router

# Создаем роутер для админки
admin_router = Router(name="admin_handlers")

# Импортируем обработчики
try:
    from .admin_handler import router as admin_handler_router
    admin_router.include_router(admin_handler_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import admin_handler: {e}")

__all__ = ["admin_router"]

print(f"✅ Admin router configured")