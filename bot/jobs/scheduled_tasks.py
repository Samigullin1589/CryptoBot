# =================================================================================
# Файл: bot/jobs/scheduled_tasks.py (ВЕРСИЯ "Distinguished Engineer" - ОБЪЕДИНЕННАЯ)
# Описание: Содержит полную логику фоновых задач, включая ваши оригинальные
# задачи и новую систему динамических достижений.
# =================================================================================

import logging
from typing import TYPE_CHECKING
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Используем TYPE_CHECKING для подсказок типов, избегая циклических импортов
if TYPE_CHECKING:
    from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)


# --- Логика отдельных задач ---

async def update_asics_db_job(deps: "Deps"):
    """Задача для принудительного обновления базы данных ASIC-майнеров."""
    logger.info("Scheduler: Запуск обновления базы ASIC...")
    try:
        updated_count = await deps.asic_service.update_asic_list_from_sources()
        logger.info(f"Scheduler: База ASIC обновлена. Изменено/добавлено: {updated_count}.")
    except Exception as e:
        logger.error(f"Scheduler: Ошибка в задаче 'update_asics_db_job': {e}", exc_info=True)


async def send_news_job(deps: "Deps"):
    """Задача для отправки подборки новостей в указанный канал."""
    logger.info("Scheduler: Запуск отправки новостей...")
    try:
        if not deps.settings.NEWS_CHAT_ID:
            logger.warning("Scheduler: NEWS_CHAT_ID не задан, пропуск задачи.")
            return

        await deps.news_service.send_news_digest(deps.bot, deps.settings.NEWS_CHAT_ID)
        logger.info(f"Scheduler: Дайджест новостей отправлен в чат {deps.settings.NEWS_CHAT_ID}.")
    except Exception as e:
        logger.error(f"Scheduler: Ошибка в задаче 'send_news_job': {e}", exc_info=True)


async def send_morning_summary_job(deps: "Deps"):
    """Задача для отправки утренней сводки администратору."""
    logger.info("Scheduler: Запуск отправки утренней сводки...")
    try:
        if not deps.settings.ADMIN_CHAT_ID:
            logger.warning("Scheduler: ADMIN_CHAT_ID не задан, пропуск задачи.")
            return

        stats_text, _ = await deps.admin_service.get_stats_page_content("main")
        header = "Доброе утро! ☀️ Вот краткая сводка по боту:\n\n"
        await deps.bot.send_message(deps.settings.ADMIN_CHAT_ID, f"{header}{stats_text}")
        logger.info("Scheduler: Утренняя сводка отправлена.")
    except Exception as e:
        logger.error(f"Scheduler: Ошибка в задаче 'send_morning_summary_job': {e}", exc_info=True)


async def send_leaderboard_job(deps: "Deps"):
    """Задача для отправки таблицы лидеров игровой экономики."""
    logger.info("Scheduler: Запуск отправки таблицы лидеров...")
    try:
        if not deps.settings.NEWS_CHAT_ID:
            logger.warning("Scheduler: NEWS_CHAT_ID для таблицы лидеров не задан, пропуск.")
            return

        leaderboard_data = await deps.mining_game_service.get_leaderboard(top_n=10)
        if not leaderboard_data:
            logger.info("Scheduler: Нет данных для таблицы лидеров.")
            return

        leaderboard_rows = [f"🏆 <b>Таблица лидеров недели</b> 🏆\n"]
        for i, (user_id, balance) in enumerate(leaderboard_data.items(), 1):
            # ИСПРАВЛЕНО: Используем get_user_profile для совместимости
            profile = await deps.user_service.get_user_profile(int(user_id))
            username = profile.username if profile and profile.username != "N/A" else f"User_{user_id}"
            emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else "🔹"
            leaderboard_rows.append(f"{emoji} {i}. {username} - {balance:,.2f} монет")

        text = "\n".join(leaderboard_rows)
        await deps.bot.send_message(deps.settings.NEWS_CHAT_ID, text)
        logger.info("Scheduler: Таблица лидеров отправлена.")
    except Exception as e:
        logger.error(f"Scheduler: Ошибка в задаче 'send_leaderboard_job': {e}", exc_info=True)


async def check_market_achievements_for_all_users(deps: "Deps"):
    """Проверяет рыночные события для всех пользователей и выдает динамические достижения."""
    logger.info("Scheduler: Запуск плановой проверки рыночных достижений...")
    all_user_ids = await deps.user_service.get_all_user_ids()
    if not all_user_ids:
        logger.info("Scheduler: Нет пользователей для проверки достижений.")
        return

    logger.info(f"Scheduler: Проверка достижений для {len(all_user_ids)} пользователей.")
    for user_id in all_user_ids:
        try:
            unlocked_achievements = await deps.achievement_service.check_market_events(user_id)
            if unlocked_achievements:
                full_list = await deps.achievement_service.get_user_achievements(user_id)
                for ach in unlocked_achievements:
                    for unlocked_data in full_list:
                        if unlocked_data.get('name') == ach.name:
                             message = (
                                f"🏆 <b>Новое достижение!</b>\n\n"
                                f"<b>{unlocked_data['name']}</b>\n"
                                f"<i>{unlocked_data['description']}</i>\n\n"
                                f"💰 Награда: +{unlocked_data['reward']} монет!"
                            )
                             await deps.bot.send_message(user_id, message)
                             break
        except Exception as e:
            logger.error(f"Scheduler: Ошибка при проверке достижений для пользователя {user_id}: {e}")


# --- Функция для настройки и регистрации всех задач ---

def setup_jobs(scheduler: AsyncIOScheduler, deps: "Deps"):
    """Настраивает и добавляет все периодические задачи в планировщик."""
    try:
        scheduler.add_job(update_asics_db_job, 'interval', hours=6, id='update_asics_db', replace_existing=True, args=[deps])
        scheduler.add_job(send_news_job, 'interval', hours=3, id='send_news', replace_existing=True, args=[deps])
        scheduler.add_job(send_morning_summary_job, 'cron', hour=9, minute=0, id='morning_summary', replace_existing=True, args=[deps])
        scheduler.add_job(send_leaderboard_job, 'cron', day_of_week='mon', hour=12, minute=0, id='weekly_leaderboard', replace_existing=True, args=[deps])
        scheduler.add_job(check_market_achievements_for_all_users, 'interval', minutes=15, id='market_achievements_check', replace_existing=True, args=[deps])
        
        logger.info(f"Все {len(scheduler.get_jobs())} периодических задач успешно настроены.")
    except Exception as e:
        logger.error(f"Не удалось настроить периодические задачи: {e}", exc_info=True)
