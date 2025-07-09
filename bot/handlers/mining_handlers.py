import time
import logging
from typing import Union
from math import floor
import redis.asyncio as redis
from aiogram import F, Router, Bot
from aiogram.types import Message, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

from bot.config.settings import settings
from bot.services.asic_service import AsicService
from bot.services.admin_service import AdminService  # <<< ДОБАВЛЕН ИМПОРТ
from bot.keyboards.keyboards import (
    get_mining_menu_keyboard, get_asic_shop_keyboard,
    get_my_farm_keyboard, get_withdraw_keyboard, get_electricity_menu_keyboard
)
from bot.utils.helpers import get_message_and_chat_id, sanitize_html

router = Router()
logger = logging.getLogger(__name__)

# --- ГЛАВНОЕ МЕНЮ РАЗДЕЛА ---

@router.callback_query(F.data == "menu_mining")
async def handle_mining_menu(call: CallbackQuery, admin_service: AdminService): # <<< ДОБАВЛЕН admin_service
    """
    Отправляет пользователю главное меню раздела "Виртуальный Майнинг".
    """
    await admin_service.track_command_usage("💎 Виртуальный Майнинг") # <<< ДОБАВЛЕНО ОТСЛЕЖИВАНИЕ
    text = "<b>💎 Центр управления Виртуальным Майнингом</b>\n\nВыберите действие:"
    await call.message.edit_text(text, reply_markup=get_mining_menu_keyboard())


# --- ЛОГИКА МАГАЗИНА ОБОРУДОВАНИЯ ---

async def show_shop_page(message: Message, asic_service: AsicService, page: int = 0):
    """
    Отображает страницу магазина с оборудованием.
    """
    asics = await asic_service.get_profitable_asics()
    if not asics:
        await message.edit_text("К сожалению, список оборудования сейчас недоступен.", reply_markup=get_mining_menu_keyboard())
        return

    text = "🏪 <b>Магазин оборудования</b>\n\nВыберите ASIC для запуска сессии:"
    keyboard = get_asic_shop_keyboard(asics, page)
    await message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "mining_shop")
async def handle_shop_menu(call: CallbackQuery, asic_service: AsicService, admin_service: AdminService): # <<< ДОБАВЛЕН admin_service
    """
    Обработчик кнопки 'Магазин оборудования'.
    """
    await admin_service.track_command_usage("🏪 Магазин оборудования") # <<< ДОБАВЛЕНО ОТСЛЕЖИВАНИЕ
    await show_shop_page(call.message, asic_service, 0)


@router.callback_query(F.data.startswith("shop_page_"))
async def handle_shop_pagination(call: CallbackQuery, asic_service: AsicService):
    """
    Обработчик кнопок пагинации в магазине.
    """
    page = int(call.data.split("_")[2])
    await show_shop_page(call.message, asic_service, page)


# --- ЛОГИКА ЗАПУСКА МАЙНИНГА ---

@router.callback_query(F.data.startswith("start_mining_"))
async def handle_start_mining(call: CallbackQuery, redis_client: redis.Redis, scheduler: AsyncIOScheduler, asic_service: AsicService, admin_service: AdminService): # <<< ДОБАВЛЕН admin_service
    """
    Обработчик выбора конкретного ASIC для запуска майнинга.
    """
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
    
    # Отслеживаем запуск конкретного асика
    await admin_service.track_command_usage(f"Запуск: {selected_asic.name}") # <<< ДОБАВЛЕНО ОТСЛЕЖИВАНИЕ
    
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


# --- ЛОГИКА "МОЯ ФЕРМА" ---

@router.callback_query(F.data == "mining_my_farm")
async def handle_my_farm(call: CallbackQuery, redis_client: redis.Redis, admin_service: AdminService): # <<< ДОБАВЛЕН admin_service
    """
    Показывает статус текущей майнинг-сессии.
    """
    await admin_service.track_command_usage("🖥️ Моя ферма") # <<< ДОБАВЛЕНО ОТСЛЕЖИВАНИЕ
    user_id = call.from_user.id
    session_data = await redis_client.hgetall(f"mining:session:{user_id}")

    if not session_data:
        text = "🖥️ <b>Моя ферма</b>\n\nУ вас нет активных майнинг-сессий. Зайдите в магазин, чтобы запустить оборудование!"
        await call.message.edit_text(text, reply_markup=get_my_farm_keyboard())
        return

    start_time = int(session_data.get("start_time", 0))
    profitability_per_day = float(session_data.get("asic_profitability_per_day", 0))
    
    elapsed_seconds = int(time.time()) - start_time
    remaining_seconds = max(0, settings.MINING_DURATION_SECONDS - elapsed_seconds)
    
    profit_per_second = profitability_per_day / (24 * 3600)
    earned_so_far = elapsed_seconds * profit_per_second

    m, s = divmod(remaining_seconds, 60)
    h, m = divmod(m, 60)
    remaining_time_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

    text = (
        f"🖥️ <b>Моя ферма</b>\n\n"
        f"✅ <b>Статус:</b> В работе\n"
        f"⚙️ <b>Оборудование:</b> {sanitize_html(session_data.get('asic_name', 'Неизвестно'))}\n"
        f"⏳ <b>Осталось времени:</b> <code>{remaining_time_str}</code>\n"
        f"💰 <b>Намайнено в этой сессии:</b> ~${earned_so_far:.4f}"
    )
    
    await call.message.edit_text(text, reply_markup=get_my_farm_keyboard())

# --- ЛОГИКА "ВЫВОД СРЕДСТВ" ---

@router.callback_query(F.data == "mining_withdraw")
async def handle_withdraw(call: CallbackQuery, redis_client: redis.Redis, admin_service: AdminService): # <<< ДОБАВЛЕН admin_service
    """
    Обрабатывает вывод средств и расчет скидки.
    """
    await admin_service.track_command_usage("💰 Вывод средств") # <<< ДОБАВЛЕНО ОТСЛЕЖИВАНИЕ
    user_id = call.from_user.id
    
    if await redis_client.exists(f"mining:session:{user_id}"):
        await call.answer("Пожалуйста, дождитесь окончания текущей майнинг-сессии перед выводом.", show_alert=True)
        return

    balance_str = await redis_client.get(f"user:{user_id}:balance")
    balance = float(balance_str) if balance_str else 0

    if balance < 1.0:
        await call.answer("ℹ️ Ваш баланс слишком мал для вывода. Накопите хотя бы 1 монету.", show_alert=True)
        return
        
    DISCOUNT_COIN_RATIO = 50 
    base_discount = 1
    bonus_discount = floor(balance / DISCOUNT_COIN_RATIO)
    total_discount = min(10, base_discount + bonus_discount)

    text = (
        f"🎉 <b>Вывод средств подтвержден!</b>\n\n"
        f"Вы обменяли <b>{balance:.2f} монет</b> на персональную скидку.\n\n"
        f"🔥 Ваша скидка у партнера: <b>{total_discount}%</b>\n\n"
        f"Нажмите на кнопку ниже, чтобы перейти на сайт партнера и воспользоваться предложением."
    )
    
    async with redis_client.pipeline() as pipe:
        pipe.set(f"user:{user_id}:balance", 0)
        pipe.incrbyfloat(f"user:{user_id}:total_withdrawn", balance)
        await pipe.execute()

    logger.info(f"User {user_id} withdrew {balance:.2f} coins for a {total_discount}% discount.")
    await call.message.edit_text(text, reply_markup=get_withdraw_keyboard())


# --- ЛОГИКА "ПРИГЛАСИТЬ ДРУГА" ---

@router.callback_query(F.data == "mining_invite")
async def handle_invite_friend(call: CallbackQuery, bot: Bot, admin_service: AdminService): # <<< ДОБАВЛЕН admin_service
    """
    Генерирует и отправляет пользователю его реферальную ссылку.
    """
    await admin_service.track_command_usage("🤝 Пригласить друга") # <<< ДОБАВЛЕНО ОТСЛЕЖИВАНИЕ
    user_id = call.from_user.id
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    text = (
        f"🤝 <b>Ваша реферальная программа</b>\n\n"
        f"Пригласите друга в нашего бота, и как только он его запустит, вы получите бонус в размере "
        f"<b>{settings.REFERRAL_BONUS_AMOUNT} монет</b> на ваш баланс!\n\n"
        f"Ваша персональная ссылка для приглашения:\n"
        f"<code>{referral_link}</code>"
    )
    
    await call.answer()
    await call.message.answer(text)

# --- ЛОГИКА "СТАТИСТИКА" ---

@router.callback_query(F.data == "mining_stats")
async def handle_my_stats(call: CallbackQuery, redis_client: redis.Redis, admin_service: AdminService): # <<< ДОБАВЛЕН admin_service
    """
    Отображает личную статистику пользователя в игре.
    """
    await admin_service.track_command_usage("📊 Статистика (Майнинг)") # <<< ДОБАВЛЕНО ОТСЛЕЖИВАНИЕ
    user_id = call.from_user.id

    async with redis_client.pipeline() as pipe:
        pipe.get(f"user:{user_id}:balance")
        pipe.get(f"user:{user_id}:total_earned")
        pipe.get(f"user:{user_id}:total_withdrawn")
        pipe.scard(f"user:{user_id}:referrals")
        results = await pipe.execute()
    
    balance = float(results[0]) if results[0] else 0
    total_earned = float(results[1]) if results[1] else 0
    total_withdrawn = float(results[2]) if results[2] else 0
    referrals_count = int(results[3]) if results[3] else 0

    text = (
        f"📊 <b>Ваша игровая статистика</b>\n\n"
        f"💰 Текущий баланс: <b>{balance:.2f} монет</b>\n"
        f"📈 Всего заработано: <b>{total_earned:.2f} монет</b>\n"
        f"📉 Всего выведено: <b>{total_withdrawn:.2f} монет</b>\n"
        f"🤝 Приглашено друзей: <b>{referrals_count}</b>"
    )

    await call.message.edit_text(text, reply_markup=get_my_farm_keyboard())


# --- ЛОГИКА "ЭЛЕКТРОЭНЕРГИЯ" ---

@router.callback_query(F.data == "mining_electricity")
async def handle_electricity_menu(call: CallbackQuery, redis_client: redis.Redis, admin_service: AdminService): # <<< ДОБАВЛЕН admin_service
    """
    Показывает меню выбора и покупки тарифов на электроэнергию.
    """
    await admin_service.track_command_usage("⚡️ Электроэнергия") # <<< ДОБАВЛЕНО ОТСЛЕЖИВАНИЕ
    user_id = call.from_user.id
    
    current_tariff = await redis_client.get(f"user:{user_id}:tariff") or settings.DEFAULT_ELECTRICITY_TARIFF
    
    unlocked_tariffs = await redis_client.smembers(f"user:{user_id}:unlocked_tariffs")
    if not unlocked_tariffs:
        unlocked_tariffs = {settings.DEFAULT_ELECTRICITY_TARIFF}

    text = (
        f"⚡️ <b>Управление электроэнергией</b>\n\n"
        f"Покупайте более выгодные тарифы, чтобы увеличить чистую прибыль от майнинга.\n\n"
        f"Текущий выбранный тариф: <b>{current_tariff}</b>"
    )
    
    await call.message.edit_text(text, reply_markup=get_electricity_menu_keyboard(current_tariff, unlocked_tariffs))


@router.callback_query(F.data.startswith("select_tariff_"))
async def handle_select_tariff(call: CallbackQuery, redis_client: redis.Redis):
    """
    Обрабатывает выбор доступного тарифа.
    """
    user_id = call.from_user.id
    tariff_name = call.data[len("select_tariff_"):]

    unlocked_tariffs = await redis_client.smembers(f"user:{user_id}:unlocked_tariffs")
    if not unlocked_tariffs:
        unlocked_tariffs = {settings.DEFAULT_ELECTRICITY_TARIFF}

    if tariff_name not in unlocked_tariffs:
        await call.answer("🔒 Этот тариф вам еще не доступен. Сначала его нужно купить.", show_alert=True)
        return

    await redis_client.set(f"user:{user_id}:tariff", tariff_name)
    logger.info(f"User {user_id} selected new electricity tariff: {tariff_name}")
    await call.answer(f"✅ Тариф '{tariff_name}' успешно выбран!")
    
    # Переиспользуем `handle_electricity_menu` для обновления меню, но без повторного трекинга
    # Для этого нам нужен `admin_service`, но мы его не используем
    # Это нормально, главное, чтобы он был доступен для вызова
    from bot.services.admin_service import AdminService
    admin_service = call.bot.get("admin_service") # Пример получения сервиса, если он проброшен в bot
    await handle_electricity_menu(call, redis_client, admin_service)


@router.callback_query(F.data.startswith("buy_tariff_"))
async def handle_buy_tariff(call: CallbackQuery, redis_client: redis.Redis, admin_service: AdminService): # <<< ДОБАВЛЕН admin_service
    """
    Обрабатывает покупку нового тарифа.
    """
    user_id = call.from_user.id
    tariff_name = call.data[len("buy_tariff_"):]

    tariff_info = settings.ELECTRICITY_TARIFFS.get(tariff_name)
    if not tariff_info:
        await call.answer("❌ Тариф не найден.", show_alert=True)
        return
        
    unlock_price = tariff_info['unlock_price']
    
    balance_str = await redis_client.get(f"user:{user_id}:balance")
    balance = float(balance_str) if balance_str else 0

    if balance < unlock_price:
        await call.answer(f"ℹ️ Недостаточно средств. Нужно {unlock_price:.0f} монет, у вас {balance:.2f}.", show_alert=True)
        return

    # Отслеживаем покупку тарифа
    await admin_service.track_command_usage(f"Покупка тарифа: {tariff_name}") # <<< ДОБАВЛЕНО ОТСЛЕЖИВАНИЕ

    async with redis_client.pipeline() as pipe:
        pipe.decrbyfloat(f"user:{user_id}:balance", unlock_price)
        pipe.sadd(f"user:{user_id}:unlocked_tariffs", tariff_name)
        await pipe.execute()
        
    logger.info(f"User {user_id} bought new tariff '{tariff_name}' for {unlock_price} coins.")
    await call.answer(f"🎉 Тариф '{tariff_name}' успешно куплен и доступен для выбора!", show_alert=True)

    await handle_electricity_menu(call, redis_client, admin_service)