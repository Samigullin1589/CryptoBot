# =================================================================================
# Файл: bot/handlers/public/achievements_handler.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ОКОНЧАТЕЛЬНАЯ)
# Описание: Обработчик для команды /achievements.
# ИСПРАВЛЕНИЕ: Внедрение зависимостей унифицировано через deps: Deps.
# =================================================================================
import logging
from aiogram import Router, types
from aiogram.filters import Command

from bot.keyboards.achievements_keyboards import get_achievements_list_keyboard
from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("achievements"))
async def achievements_handler(message: types.Message, deps: Deps):
    """Отображает список всех достижений пользователя."""
    user_id = message.from_user.id
    
    all_achievements = await deps.achievement_service.get_all_achievements()
    unlocked_achievements = await deps.achievement_service.get_user_achievements(user_id)
    unlocked_ids = {ach.id for ach in unlocked_achievements}
    
    unlocked_count = len(unlocked_ids)
    total_count = len(all_achievements)
    
    text = (f"<b>Ваши Достижения ({unlocked_count}/{total_count})</b>\n\n"
            "Здесь собран ваш путь от новичка до крипто-магната.\n"
            "🏆 - получено, 🔒 - еще не открыто.\n")

    # Формируем описание для каждого достижения
    for ach in sorted(all_achievements, key=lambda x: x.id):
        icon = "🏆" if ach.id in unlocked_ids else "🔒"
        text += f"\n<b>{icon} {ach.name}</b>\n<i>{ach.description}</i>"
        if ach.reward_coins > 0:
            text += f" (Награда: {ach.reward_coins} монет)"
        text += "\n"

    await message.answer(text)