# src/bot/handlers/game/__init__.py
from .game_handler import game_router
from .mining_game_handler import game_router as mining_router

__all__ = ["game_router", "mining_router"]