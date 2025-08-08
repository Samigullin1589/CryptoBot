# =================================================================================
# Файл: bot/jobs/game_tasks.py (ВЕРСИЯ "Distinguished Engineer" - НОВЫЙ)
# Описание: Содержит функции, вызываемые по расписанию для игрового движка.
# =================================================================================
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.services.mining_game_service import MiningGameService

logger = logging.getLogger(__name__)

async def scheduled_end_session(user_id: int, game_service: "MiningGameService"):
    """
    Вызывается планировщиком для завершения майнинг-сессии пользователя.
    """
    logger.info(f"Scheduler: Запуск задачи на завершение сессии для пользователя {user_id}...")
    try:
        result = await game_service.end_session(user_id)
        if result:
            # Формируем и отправляем уведомление о результатах
            event_text = f"\n\n<i>Случайное событие: {result.event_description}</i>" if result.event_description else ""
            ach_text = ""
            if result.unlocked_achievement:
                ach = result.unlocked_achievement
                ach_text = (
                    f"\n\n🏆 <b>Новое достижение!</b>\n"
                    f"<b>{ach.name}</b>: {ach.description}\n"
                    f"<i>Награда: +{ach.reward_coins} монет.</i>"
                )

            message_text = (
                f"🎉 <b>Сессия майнинга на {result.asic_name} завершена!</b>\n\n"
                f"▫️ Доход (грязными): {result.gross_earned:,.4f} монет\n"
                f"▫️ Затраты на э/э: {result.total_electricity_cost:,.4f} монет\n"
                f"<b>💰 Чистая прибыль: {result.net_earned:,.4f} монет</b>"
                f"{event_text}{ach_text}"
            )
            await game_service.bot.send_message(user_id, message_text)
    except Exception as e:
        logger.error(f"Scheduler: Ошибка при завершении сессии для пользователя {user_id}: {e}", exc_info=True)

