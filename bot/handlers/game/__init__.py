from aiogram import Router
from .mining_game_handler import game_router as mining_game_router

game_router = Router(name="game_router")
game_router.include_router(mining_game_router)