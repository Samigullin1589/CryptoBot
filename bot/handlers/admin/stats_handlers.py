import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.filters.admin_filter import IsAdmin
from bot.keyboards.admin_keyboards import get_back_to_admin_menu_keyboard
from bot.services.admin_service import AdminStatsService

stats_router = Router()
logger = logging.getLogger(__name__)

# Применяем фильтр админа ко всем обработчикам в этом файле
stats_router.callback_query.filter(IsAdmin())

@stats_router.callback_query(F.data == "admin_stats_general")
async def show_general_stats(call: CallbackQuery, admin_service: AdminStatsService):
    stats = await admin_service.get_general_stats()
    text = (
        "<b>📊 Общая статистика</b>\n\n"
        f"👥 Всего пользователей в боте: <b>{stats['total_users']}</b>\n"
        f"🏃‍♂️ Активных за последние 24 часа: <b>{stats['active_24h']}</b>"
    )
    await call.message.edit_text(text, reply_markup=get_back_to_admin_menu_keyboard())


@stats_router.callback_query(F.data == "admin_stats_mining")
async def show_mining_stats(call: CallbackQuery, admin_service: AdminStatsService):
    stats = await admin_service.get_mining_stats()
    text = (
        "<b>💎 Статистика 'Виртуального Майнинга'</b>\n\n"
        f"⚡️ Активных сессий сейчас: <b>{stats['active_sessions']}</b>\n"
        f"💰 Всего монет на балансах: <b>{stats['total_balance']:.2f}</b>\n"
        f"📤 Всего выведено средств: <b>{stats['total_withdrawn']:.2f}</b>\n"
        f"🤝 Всего успешных рефералов: <b>{stats['total_referrals']}</b>"
    )
    await call.message.edit_text(text, reply_markup=get_back_to_admin_menu_keyboard())


@stats_router.callback_query(F.data == "admin_stats_commands")
async def show_command_stats(call: CallbackQuery, admin_service: AdminStatsService):
    top_commands = await admin_service.get_command_stats()
    
    if not top_commands:
        stats_text = "Еще нет данных."
    else:
        stats_text = "\n".join([f"🔹 <code>{cmd}</code> - {score} раз" for cmd, score in top_commands])

    text = (
        "<b>📈 Статистика использования команд</b>\n\n"
        f"{stats_text}"
    )
    await call.message.edit_text(text, reply_markup=get_back_to_admin_menu_keyboard())