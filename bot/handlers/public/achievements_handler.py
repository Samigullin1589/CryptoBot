import logging
from aiogram import Router, types
from aiogram.filters import Command

from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)
router = Router(name="public_achievements")


@router.message(Command("achievements"))
async def achievements_handler(message: types.Message, deps: Deps):
    """
    Отображает список всех достижений пользователя.
    Совместимо с DI (Deps) и безопасно при отсутствии данных.
    """
    user_id = message.from_user.id

    try:
        all_achievements = await deps.achievement_service.get_all_achievements()
    except Exception as e:
        logger.error("Не удалось получить список всех достижений: %s", e, exc_info=True)
        all_achievements = []

    try:
        unlocked_achievements = await deps.achievement_service.get_user_achievements(user_id)
    except Exception as e:
        logger.error("Не удалось получить достижения пользователя %s: %s", user_id, e, exc_info=True)
        unlocked_achievements = []

    unlocked_ids = {ach.id for ach in unlocked_achievements}
    unlocked_count = len(unlocked_ids)
    total_count = len(all_achievements)

    header = (
        f"<b>Ваши Достижения ({unlocked_count}/{total_count})</b>\n\n"
        "Здесь собран ваш путь от новичка до крипто-магната.\n"
        "🏆 — получено, 🔒 — еще не открыто.\n"
    )

    if not all_achievements:
        await message.answer(header + "\nПока что здесь пусто. Продолжайте активность в боте!")
        return

    # Формируем описание для каждого достижения
    lines = [header]
    for ach in sorted(all_achievements, key=lambda x: x.id):
        icon = "🏆" if ach.id in unlocked_ids else "🔒"
        line = f"\n<b>{icon} {ach.name}</b>\n<i>{ach.description}</i>"
        try:
            if getattr(ach, "reward_coins", 0) > 0:
                line += f" (Награда: {ach.reward_coins} монет)"
        except Exception:
            # Если у модели нет поля reward_coins — игнорируем
            pass
        lines.append(line)

    await message.answer("".join(lines))