# bot/handlers/game/__init__.py
from aiogram import Router

# Создаем роутеры для игры
game_router = Router(name="game_handlers")
mining_router = Router(name="mining_handlers")

# Импортируем обработчики
try:
    from .game_handler import router as game_handler_router
    game_router.include_router(game_handler_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import game_handler: {e}")

try:
    from .mining_handler import router as mining_handler_router
    mining_router.include_router(mining_handler_router)
except ImportError as e:
    print(f"⚠️ Warning: Could not import mining_handler: {e}")

__all__ = ["game_router", "mining_router"]

print(f"✅ Game routers configured")