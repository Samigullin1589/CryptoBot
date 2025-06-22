import time
import logging
from typing import Union
import redis.asyncio as redis
from aiogram import F, Router, Bot
from aiogram.types import Message, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

from bot.config.settings import settings
from bot.services.asic_service import AsicService
from bot.keyboards.keyboards import get_mining_menu_keyboard, get_asic_shop_keyboard, get_my_farm_keyboard
from bot.utils.helpers import get_message_and_chat_id, sanitize_html

router = Router()
logger = logging.getLogger(__name__)

# --- ГЛАВНОЕ МЕНЮ РАЗДЕЛА ---

@router.callback_query(F.data == "menu_mining")
async def handle_mining_menu(call: CallbackQuery):
    """Отправляет пользователю главное меню раздела "Виртуальный Майнинг"."""
    text = "<b>💎 Центр управления Виртуальным Майнингом</b>\n\nВыберите действие:"
    await call.message.edit_text(text, reply_markup=get_mining_menu_keyboard())


# --- ЛОГИКА МАГАЗИНА ОБОРУДОВАНИЯ ---

async def show_shop_page(message: Message, asic_service: AsicService, page: int = 0):
    """Отображает страницу магазина с оборудованием."""
    asics = await asic_service.get_profitable_asics()
    if not asics:
        await message.edit_text("К сожалению, список оборудования сейчас недоступен.", reply_markup=get_mining_menu_keyboard())
        return

    text = "🏪 <b>Магазин оборудования</b>\n\nВыберите ASIC для запуска сессии:"
    keyboard = get_asic_shop_keyboard(asics, page)
    await message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "mining_shop")
async def handle_shop_menu(call: CallbackQuery, asic_service: AsicService):
    """Обработчик кнопки 'Магазин оборудования'."""
    await show_shop_page(call.message, asic_service, 0)


@router.callback_query(F.data.startswith("shop_page_"))
async def handle_shop_pagination(call: CallbackQuery, asic_service: AsicService):
    """Обработчик кнопок пагинации в магазине."""
    page = int(call.data.split("_")[2])
    await show_shop_page(call.message, asic_service, page)


# --- ЛОГИКА ЗАПУСКА МАЙНИНГА ---

@router.callback_query(F.data.startswith("start_mining_"))
async def handle_start_mining(call: CallbackQuery, redis_client: redis.Redis, scheduler: AsyncIOScheduler, asic_service: AsicService):
    """Обработчик выбора конкретного ASIC для запуска майнинга."""
    user_id = call.from_user.id

    if await redis_client.exists(f"mining:session:{user_id}"):
        await call.answer("ℹ️ У вас уже запущена одна майнинг-сессия. Дождитесь ее окончания.", show_alert=True)
        return
    
    asic_index = int(call.data.split("_")[2])
    all_asics = await asic_service.get_profitable_asics()

    if asic_index >= len(all_asics):
        await call.answer("❌ Ошибка. Оборудование не найдено. Попробуйте обновить магазин.", show_alert=True)
        return
        
    selected_asic = all_asics[asic_index]
    
    run_date = datetime.now() + timedelta(seconds=settings.MINING_DURATION_SECONDS)
    
    job = scheduler.add_job(
        'bot.services.mining_tasks:end_mining_session',
        'date',
        run_date=run_date,
        args=[user_id],
        id=f"mining_job_{user_id}",
        replace_existing=True
    )

    session_data = {
        "start_time": int(time.time()),
        "job_id": job.id,
        "asic_name": selected_asic.name,
        "asic_profitability_per_day": selected_asic.profitability,
        "asic_power": selected_asic.power or 0
    }
    await redis_client.hset(f"mining:session:{user_id}", mapping=session_data)

    await call.message.edit_text(
        f"✅ Вы успешно запустили майнинг на <b>{selected_asic.name}</b>!\n\n"
        f"Сессия продлится {settings.MINING_DURATION_SECONDS / 3600:.0f} часов. "
        f"Уведомление о завершении придет в этот чат.",
        reply_markup=get_mining_menu_keyboard()
    )
    logger.info(f"User {user_id} started mining session with ASIC: {selected_asic.name}")


# --- НОВЫЙ ОБРАБОТЧИК: 'МОЯ ФЕРМА' ---

@router.callback_query(F.data == "mining_my_farm")
async def handle_my_farm(call: CallbackQuery, redis_client: redis.Redis):
    """Показывает статус текущей майнинг-сессии."""
    user_id = call.from_user.id
    session_data = await redis_client.hgetall(f"mining:session:{user_id}")

    if not session_data:
        text = "🖥️ <b>Моя ферма</b>\n\nУ вас нет активных майнинг-сессий. Зайдите в магазин, чтобы запустить оборудование!"
        await call.message.edit_text(text, reply_markup=get_my_farm_keyboard())
        return

    # Расчеты времени и дохода
    start_time = int(session_data.get("start_time", 0))
    profitability_per_day = float(session_data.get("asic_profitability_per_day", 0))
    
    elapsed_seconds = int(time.time()) - start_time
    remaining_seconds = settings.MINING_DURATION_SECONDS - elapsed_seconds
    
    profit_per_second = profitability_per_day / (24 * 3600)
    earned_so_far = elapsed_seconds * profit_per_second

    # Форматирование времени
    m, s = divmod(remaining_seconds, 60)
    h, m = divmod(m, 60)
    remaining_time_str = f"{h:02d}:{m:02d}:{s:02d}"

    text = (
        f"🖥️ <b>Моя ферма</b>\n\n"
        f"✅ <b>Статус:</b> В работе\n"
        f"⚙️ <b>Оборудование:</b> {sanitize_html(session_data.get('asic_name', 'Неизвестно'))}\n"
        f"⏳ <b>Осталось времени:</b> <code>{remaining_time_str}</code>\n"
        f"💰 <b>Намайнено в этой сессии:</b> ~${earned_so_far:.4f}"
    )
    
    await call.message.edit_text(text, reply_markup=get_my_farm_keyboard())