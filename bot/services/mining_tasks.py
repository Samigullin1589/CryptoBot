# ===============================================================
# Файл: bot/services/mining_tasks.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Фоновая задача для завершения майнинг-сессий.
# Полностью переработан: теперь это "тонкий" оркестратор,
# который использует специализированные сервисы для выполнения
# основной работы, соответствуя современным стандартам архитектуры.
# ===============================================================

import logging
from aiogram import Bot

# ПРИМЕЧАНИЕ: В реальном проекте зависимости (bot, services)
# должны предоставляться через DI-контейнер, а не через глобальный импорт.
# Этот файл - пример того, как должен выглядеть сам таск.
from bot.utils import dependencies 
from bot.services.mining_game_service import MiningGameService
from bot.utils.formatters import format_mining_session_result

logger = logging.getLogger(__name__)

async def end_mining_session(user_id: int):
    """
    Завершает майнинг-сессию. Является точкой входа для APScheduler.
    Делегирует всю сложную работу специализированным сервисам.
    """
    logger.info(f"Scheduler starting end_mining_session task for user {user_id}")

    # --- Шаг 1: Получаем необходимые зависимости ---
    # В идеальном мире DI-контейнер передал бы их в качестве аргументов.
    bot: Bot = dependencies.bot
    mining_game_service: MiningGameService = dependencies.mining_game_service

    # --- Шаг 2: Вызываем сервис для выполнения бизнес-логики ---
    # Сервис выполняет все расчеты и обновления в базе данных.
    result_model = await mining_game_service.end_session(user_id)

    # --- Шаг 3: Если сессия успешно завершена, форматируем и отправляем уведомление ---
    if result_model:
        # Форматтер отвечает за создание красивого текста из модели данных.
        notification_text = format_mining_session_result(result_model)
        
        try:
            await bot.send_message(user_id, notification_text)
            logger.info(f"Successfully sent session end notification to user {user_id}")
        except Exception as e:
            # Если пользователь заблокировал бота, мы не можем отправить сообщение,
            # но его баланс все равно был корректно обновлен.
            logger.error(f"Failed to send notification to user {user_id}: {e}")
    else:
        logger.warning(f"Mining session for user {user_id} could not be processed. Result was None.")

