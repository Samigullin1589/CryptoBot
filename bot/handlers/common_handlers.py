import logging
from typing import Union

import redis.asyncio as redis
from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config.settings import settings
from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.utils.helpers import get_message_and_chat_id

router = Router()
logger = logging.getLogger(__name__)


async def handle_referral(message: Message, command: CommandObject, redis_client: redis.Redis, bot: Bot):
    """Обрабатывает запуск по реферальной ссылке."""
    referrer_id = command.args
    new_user_id = message.from_user.id

    # Проверяем, что ID реферера - это число и пользователь не приглашает сам себя
    if not referrer_id.isdigit() or int(referrer_id) == new_user_id:
        return

    referrer_id = int(referrer_id)
    
    # Проверяем, не был ли этот пользователь уже кем-то приглашен
    already_referred = await redis_client.sismember("referred_users", new_user_id)
    if already_referred:
        logger.info(f"User {new_user_id} tried to use referral link from {referrer_id}, but is already a referred user.")
        return

    # Начисляем бонус рефереру и сохраняем информацию
    bonus = settings.REFERRAL_BONUS_AMOUNT
    await redis_client.incrbyfloat(f"user:{referrer_id}:balance", bonus)
    await redis_client.sadd("referred_users", new_user_id) # Добавляем нового юзера в общий сет
    await redis_client.sadd(f"user:{referrer_id}:referrals", new_user_id) # Добавляем реферала к рефереру
    
    logger.info(f"User {new_user_id} joined via referral from {referrer_id}. Referrer received {bonus} coins.")

    # Отправляем уведомление рефереру
    try:
        await bot.send_message(
            referrer_id,
            f"🎉 Поздравляем! Ваш друг @{message.from_user.username} присоединился по вашей ссылке.\n"
            f"💰 Ваш баланс пополнен на <b>{bonus} монет</b>!"
        )
    except Exception as e:
        logger.error(f"Failed to send referral notification to user {referrer_id}: {e}")


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, command: CommandObject, redis_client: redis.Redis, bot: Bot):
    """Обработчик команды /start с поддержкой рефералов."""
    await state.clear()
    
    # Если команда /start была с аргументом (реферальным кодом)
    if command.args:
        await handle_referral(message, command, redis_client, bot)
    
    logger.info(f"User {message.from_user.id} started the bot.")
    await message.answer(
        "👋 Добро пожаловать в CryptoBot! Я ваш помощник в мире криптовалют.\n\n"
        "Выберите одну из опций в меню ниже, чтобы начать.",
        reply_markup=get_main_menu_keyboard()
    )


@router.callback_query(F.data == "back_to_main_menu")
async def handle_back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Главное меню:", reply_markup=get_main_menu_keyboard())