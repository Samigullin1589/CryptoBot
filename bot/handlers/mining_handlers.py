import time
import logging
from datetime import datetime, timedelta
from typing import Union

import redis.asyncio as redis
from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config.settings import settings
from bot.services.mining_tasks import end_mining_session
from bot.utils.keyboards import get_main_menu_keyboard
# get_message_and_chat_id больше не нужен в этом файле
# from bot.utils.helpers import get_message_and_chat_id

router = Router()
logger = logging.getLogger(__name__)


# --- ИСПРАВЛЕННЫЙ ХЭНДЛЕР ---
@router.callback_query(F.data == "menu_mining")
@router.message(F.text == "💎 Виртуальный Майнинг")
async def handle_mining_menu(update: Union[CallbackQuery, Message]):
    text = (
        "<b>💎 Виртуальный майнинг</b>\n\n"
        "Эта функция находится в разработке.\n\n"
        "Скоро здесь вы сможете запускать виртуальные майнинг-фермы, "
        "получать пассивный доход и обменивать его на реальные призы!\n\n"
        "Используйте команду /start_mining для начала."
    )
    
    # Правильная проверка типа update
    if isinstance(update, CallbackQuery):
        # Если это нажатие на кнопку, редактируем сообщение
        await update.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    elif isinstance(update, Message):
        # Если это текстовая команда, отправляем новый ответ
        await update.answer(text, reply_markup=get_main_menu_keyboard())


@router.message(Command("start_mining"))
async def start_mining(message: Message, redis_client: redis.Redis, scheduler: AsyncIOScheduler, bot: Bot):
    user_id = message.from_user.id

    if await redis_client.exists(f"mining:session:{user_id}"):
        await message.answer("ℹ️ Майнинг уже запущен.")
        return

    if await redis_client.exists(f"mining:claimable:{user_id}"):
        await message.answer("✅ У вас есть награды для сбора. Используйте команду /claim_rewards.")
        return

    run_date = datetime.now() + timedelta(seconds=settings.MINING_DURATION_SECONDS)
    job = scheduler.add_job(
        end_mining_session,
        'date',
        run_date=run_date,
        args=[user_id, bot, redis_client],
        id=f"mining_job_{user_id}",
        replace_existing=True
    )

    await redis_client.hset(f"mining:session:{user_id}", mapping={
        "start_time": int(time.time()),
        "job_id": job.id
    })

    await message.answer(f"✅ Виртуальный майнинг запущен на {settings.MINING_DURATION_SECONDS / 3600:.0f} часов!")
    logger.info(f"Started mining session for user {user_id}")


@router.message(Command("claim_rewards"))
async def claim_rewards(message: Message, redis_client: redis.Redis):
    user_id = message.from_user.id
    claimable_key = f"mining:claimable:{user_id}"

    reward = await redis_client.get(claimable_key)
    if not reward:
        await message.answer("ℹ️ У вас нет наград для сбора.")
        return

    reward_amount = float(reward)

    await redis_client.incrbyfloat(f"user:{user_id}:balance", reward_amount)
    await redis_client.delete(claimable_key)

    await message.answer(f"🎉 Награда в размере {reward_amount:.2f} успешно зачислена на ваш баланс!")
    logger.info(f"User {user_id} claimed {reward_amount} reward.")