# ===============================================================
# Файл: bot/handlers/mining_handlers.py (Полная финальная версия)
# Описание: Восстановлен полный код "Виртуального майнинга".
# Логика калькулятора переписана для максимальной надежности.
# ===============================================================
import time
import logging
import re
from typing import Union, List
from math import floor
import redis.asyncio as redis
from aiogram import F, Router, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

from bot.config.settings import settings
from bot.services.asic_service import AsicService
from bot.services.admin_service import AdminService
from bot.services.mining_service import MiningService
from bot.services.market_data_service import MarketDataService
from bot.utils.states import ProfitCalculator
from bot.utils.models import AsicMiner
from bot.keyboards.keyboards import (
    get_mining_menu_keyboard, get_asic_shop_keyboard,
    get_my_farm_keyboard, get_withdraw_keyboard, get_electricity_menu_keyboard
)
from bot.utils.helpers import sanitize_html

router = Router()
logger = logging.getLogger(__name__)

# ===============================================================
# --- БЛОК 1: ВИРТУАЛЬНАЯ ФЕРМА (ПОЛНОСТЬЮ ВОССТАНОВЛЕН) ---
# ===============================================================

@router.callback_query(F.data == "menu_mining")
async def handle_mining_menu(call: CallbackQuery, admin_service: AdminService):
    await admin_service.track_command_usage("💎 Виртуальный Майнинг")
    text = "<b>💎 Центр управления Виртуальным Майнингом</b>\n\nВыберите действие:"
    await call.message.edit_text(text, reply_markup=get_mining_menu_keyboard())

async def show_shop_page(message: Message, asic_service: AsicService, page: int = 0):
    asics, _ = await asic_service.get_top_asics(count=1000, electricity_cost=0.0)
    if not asics:
        await message.edit_text("К сожалению, список оборудования недоступен. Используются резервные данные.", reply_markup=get_mining_menu_keyboard())
        return
    text = "🏪 <b>Магазин оборудования</b>\n\nВыберите ASIC для запуска сессии:"
    keyboard = get_asic_shop_keyboard(asics, page)
    await message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "mining_shop")
async def handle_shop_menu(call: CallbackQuery, asic_service: AsicService, admin_service: AdminService):
    await admin_service.track_command_usage("🏪 Магазин оборудования")
    await call.message.edit_text("⏳ Загружаю оборудование...")
    await show_shop_page(call.message, asic_service, 0)

@router.callback_query(F.data.startswith("shop_page_"))
async def handle_shop_pagination(call: CallbackQuery, asic_service: AsicService):
    page = int(call.data.split("_")[2])
    await show_shop_page(call.message, asic_service, page)

@router.callback_query(F.data.startswith("start_mining_"))
async def handle_start_mining(call: CallbackQuery, redis_client: redis.Redis, scheduler: AsyncIOScheduler, asic_service: AsicService, admin_service: AdminService):
    user_id = call.from_user.id
    if await redis_client.exists(f"mining:session:{user_id}"):
        await call.answer("ℹ️ У вас уже запущена одна майнинг-сессия. Дождитесь ее окончания.", show_alert=True)
        return
    
    asic_index = int(call.data.split("_")[2])
    all_asics, _ = await asic_service.get_top_asics(count=1000, electricity_cost=0.0)
    if asic_index >= len(all_asics):
        await call.answer("❌ Ошибка. Оборудование не найдено. Попробуйте обновить магазин.", show_alert=True)
        return
        
    selected_asic = all_asics[asic_index]
    await admin_service.track_command_usage(f"Запуск: {selected_asic.name}")
    run_date = datetime.now() + timedelta(seconds=settings.MINING_DURATION_SECONDS)
    job = scheduler.add_job(
        'bot.services.mining_tasks:end_mining_session', 'date',
        run_date=run_date, args=[user_id], id=f"mining_job_{user_id}", replace_existing=True
    )
    session_data = {
        "start_time": int(time.time()), "job_id": job.id, "asic_name": selected_asic.name,
        "asic_profitability_per_day": selected_asic.profitability, "asic_power": selected_asic.power or 0
    }
    await redis_client.hset(f"mining:session:{user_id}", mapping=session_data)
    await call.message.edit_text(
        f"✅ Вы успешно запустили майнинг на <b>{selected_asic.name}</b>!\n\n"
        f"Сессия продлится {settings.MINING_DURATION_SECONDS / 3600:.0f} часов. "
        f"Уведомление о завершении придет в этот чат.",
        reply_markup=get_mining_menu_keyboard()
    )
    logger.info(f"User {user_id} started mining session with ASIC: {selected_asic.name}")

@router.callback_query(F.data == "mining_my_farm")
async def handle_my_farm(call: CallbackQuery, redis_client: redis.Redis, admin_service: AdminService):
    await admin_service.track_command_usage("🖥️ Моя ферма")
    user_id = call.from_user.id
    session_data = await redis_client.hgetall(f"mining:session:{user_id}")
    if not session_data:
        text = "🖥️ <b>Моя ферма</b>\n\nУ вас нет активных майнинг-сессий. Зайдите в магазин, чтобы запустить оборудование!"
        await call.message.edit_text(text, reply_markup=get_my_farm_keyboard())
        return

    start_time_bytes = session_data.get(b"start_time")
    start_time = int(start_time_bytes) if start_time_bytes else 0
    profitability_per_day_bytes = session_data.get(b"asic_profitability_per_day")
    profitability_per_day = float(profitability_per_day_bytes) if profitability_per_day_bytes else 0.0
    asic_name_bytes = session_data.get(b'asic_name')
    asic_name = asic_name_bytes.decode('utf-8') if asic_name_bytes else "Неизвестно"

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
        f"⚙️ <b>Оборудование:</b> {sanitize_html(asic_name)}\n"
        f"⏳ <b>Осталось времени:</b> <code>{remaining_time_str}</code>\n"
        f"💰 <b>Намайнено в этой сессии:</b> ~${earned_so_far:.4f}"
    )
    await call.message.edit_text(text, reply_markup=get_my_farm_keyboard())

@router.callback_query(F.data == "mining_withdraw")
async def handle_withdraw(call: CallbackQuery, redis_client: redis.Redis, admin_service: AdminService):
    await admin_service.track_command_usage("💰 Вывод средств")
    user_id = call.from_user.id
    if await redis_client.exists(f"mining:session:{user_id}"):
        await call.answer("Пожалуйста, дождитесь окончания текущей майнинг-сессии перед выводом.", show_alert=True)
        return
    balance_bytes = await redis_client.get(f"user:{user_id}:balance")
    balance = float(balance_bytes) if balance_bytes else 0.0
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

@router.callback_query(F.data == "mining_invite")
async def handle_invite_friend(call: CallbackQuery, bot: Bot, admin_service: AdminService):
    await admin_service.track_command_usage("🤝 Пригласить друга")
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
    await call.message.answer(text, reply_markup=get_mining_menu_keyboard())

@router.callback_query(F.data == "mining_stats")
async def handle_my_stats(call: CallbackQuery, redis_client: redis.Redis, admin_service: AdminService):
    await admin_service.track_command_usage("📊 Статистика (Майнинг)")
    user_id = call.from_user.id
    async with redis_client.pipeline() as pipe:
        pipe.get(f"user:{user_id}:balance")
        pipe.get(f"user:{user_id}:total_earned")
        pipe.get(f"user:{user_id}:total_withdrawn")
        pipe.scard(f"user:{user_id}:referrals")
        results = await pipe.execute()
    
    balance = float(results[0]) if results[0] else 0.0
    total_earned = float(results[1]) if results[1] else 0.0
    total_withdrawn = float(results[2]) if results[2] else 0.0
    referrals_count = int(results[3]) if results[3] else 0
    text = (
        f"📊 <b>Ваша игровая статистика</b>\n\n"
        f"💰 Текущий баланс: <b>{balance:.2f} монет</b>\n"
        f"📈 Всего заработано: <b>{total_earned:.2f} монет</b>\n"
        f"📉 Всего выведено: <b>{total_withdrawn:.2f} монет</b>\n"
        f"🤝 Приглашено друзей: <b>{referrals_count}</b>"
    )
    await call.message.edit_text(text, reply_markup=get_my_farm_keyboard())

@router.callback_query(F.data == "mining_electricity")
async def handle_electricity_menu(call: CallbackQuery, redis_client: redis.Redis, admin_service: AdminService):
    await admin_service.track_command_usage("⚡️ Электроэнергия")
    user_id = call.from_user.id
    
    current_tariff_bytes = await redis_client.get(f"user:{user_id}:tariff")
    current_tariff = current_tariff_bytes.decode('utf-8') if current_tariff_bytes else settings.DEFAULT_ELECTRICITY_TARIFF
    unlocked_tariffs_bytes = await redis_client.smembers(f"user:{user_id}:unlocked_tariffs")
    unlocked_tariffs = {t.decode('utf-8') for t in unlocked_tariffs_bytes}
    if not unlocked_tariffs:
        unlocked_tariffs = {settings.DEFAULT_ELECTRICITY_TARIFF}
    text = (
        f"⚡️ <b>Управление электроэнергией</b>\n\n"
        f"Покупайте более выгодные тарифы, чтобы увеличить чистую прибыль от майнинга.\n\n"
        f"Текущий выбранный тариф: <b>{current_tariff}</b>"
    )
    await call.message.edit_text(text, reply_markup=get_electricity_menu_keyboard(current_tariff, unlocked_tariffs))

@router.callback_query(F.data.startswith("select_tariff_"))
async def handle_select_tariff(call: CallbackQuery, redis_client: redis.Redis, admin_service: AdminService):
    user_id = call.from_user.id
    tariff_name = call.data[len("select_tariff_"):]
    unlocked_tariffs_bytes = await redis_client.smembers(f"user:{user_id}:unlocked_tariffs")
    unlocked_tariffs = {t.decode('utf-8') for t in unlocked_tariffs_bytes}
    if not unlocked_tariffs:
        unlocked_tariffs = {settings.DEFAULT_ELECTRICITY_TARIFF}
    if tariff_name not in unlocked_tariffs:
        await call.answer("🔒 Этот тариф вам еще не доступен. Сначала его нужно купить.", show_alert=True)
        return
    await redis_client.set(f"user:{user_id}:tariff", tariff_name)
    logger.info(f"User {user_id} selected new electricity tariff: {tariff_name}")
    await call.answer(f"✅ Тариф '{tariff_name}' успешно выбран!")
    await handle_electricity_menu(call, redis_client, admin_service)

@router.callback_query(F.data.startswith("buy_tariff_"))
async def handle_buy_tariff(call: CallbackQuery, redis_client: redis.Redis, admin_service: AdminService):
    user_id = call.from_user.id
    tariff_name = call.data[len("buy_tariff_"):]
    tariff_info = settings.ELECTRICITY_TARIFFS.get(tariff_name)
    if not tariff_info:
        await call.answer("❌ Тариф не найден.", show_alert=True)
        return
    unlock_price = tariff_info['unlock_price']
    balance_bytes = await redis_client.get(f"user:{user_id}:balance")
    balance = float(balance_bytes) if balance_bytes else 0.0
    if balance < unlock_price:
        await call.answer(f"ℹ️ Недостаточно средств. Нужно {unlock_price:.0f} монет, у вас {balance:.2f}.", show_alert=True)
        return
    await admin_service.track_command_usage(f"Покупка тарифа: {tariff_name}")
    async with redis_client.pipeline() as pipe:
        pipe.incrbyfloat(f"user:{user_id}:balance", -unlock_price)
        pipe.sadd(f"user:{user_id}:unlocked_tariffs", tariff_name)
        await pipe.execute()
    logger.info(f"User {user_id} bought new tariff '{tariff_name}' for {unlock_price} coins.")
    await call.answer(f"🎉 Тариф '{tariff_name}' успешно куплен и доступен для выбора!", show_alert=True)
    await handle_electricity_menu(call, redis_client, admin_service)

@router.message(Command("tip"))
async def handle_tip_command(message: Message, command: CommandObject, redis_client: redis.Redis, admin_service: AdminService):
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать ответом на сообщение того, кому вы хотите отправить монеты.")
        return
    try:
        if command.args is None: raise ValueError("Не указана сумма.")
        amount = float(command.args)
        if amount <= 0: raise ValueError("Сумма должна быть положительной.")
    except (ValueError, TypeError):
        await message.reply("⚠️ Неверный формат. Используйте: <code>/tip [сумма]</code>\nНапример: <code>/tip 10.5</code>")
        return
    sender = message.from_user
    recipient = message.reply_to_message.from_user
    if sender.id == recipient.id:
        await message.reply("😅 Нельзя отправить чаевые самому себе.")
        return
    if recipient.is_bot:
        await message.reply("🤖 Нельзя отправить чаевые боту.")
        return
    sender_balance_bytes = await redis_client.get(f"user:{sender.id}:balance")
    sender_balance = float(sender_balance_bytes) if sender_balance_bytes else 0.0
    if sender_balance < amount:
        await message.reply(f"😕 Недостаточно средств. Ваш баланс: {sender_balance:.2f} монет.")
        return
    try:
        async with redis_client.pipeline() as pipe:
            pipe.incrbyfloat(f"user:{sender.id}:balance", -amount)
            pipe.incrbyfloat(f"user:{recipient.id}:balance", amount)
            pipe.incrbyfloat(f"user:{recipient.id}:total_earned", amount)
            await pipe.execute()
    except Exception as e:
        logger.error(f"Failed to process tip from {sender.id} to {recipient.id}: {e}")
        await message.reply("❌ Произошла внутренняя ошибка при переводе. Попробуйте позже.")
        return
    await admin_service.track_command_usage("/tip")
    sender_name = f"<a href='tg://user?id={sender.id}'>{sanitize_html(sender.full_name)}</a>"
    recipient_name = f"<a href='tg://user?id={recipient.id}'>{sanitize_html(recipient.full_name)}</a>"
    await message.reply(
        f"💸 {sender_name} отправил(а) <b>{amount:.2f} монет</b> в качестве чаевых {recipient_name}!",
        disable_web_page_preview=True
    )
    logger.info(f"User {sender.id} tipped {amount:.2f} to {recipient.id}")

# ===============================================================
# --- БЛОК 2: ПРОФЕССИОНАЛЬНЫЙ КАЛЬКУЛЯТОР (НОВАЯ НАДЕЖНАЯ ВЕРСИЯ) ---
# ===============================================================

def build_cancel_keyboard():
    """Создает клавиатуру с кнопкой отмены."""
    return InlineKeyboardBuilder().button(text="❌ Отмена", callback_data="prof_calc_cancel").as_markup()

@router.callback_query(F.data == "menu_calculator")
@router.message(F.text == "⛏️ Калькулятор")
async def start_profit_calculator(update: Union[Message, CallbackQuery], state: FSMContext, admin_service: AdminService):
    """Шаг 0: Запуск калькулятора и сброс состояния."""
    await admin_service.track_command_usage("⛏️ Калькулятор")
    await state.clear()
    logger.info(f"Calculator started by user {update.from_user.id}. State cleared.")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="USD ($)", callback_data="calc_currency_usd")
    builder.button(text="RUB (₽)", callback_data="calc_currency_rub")
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="prof_calc_cancel"))
    
    text = "💡 Выберите валюту для указания стоимости электроэнергии:"
    keyboard = builder.as_markup()
    
    if isinstance(update, Message):
        await update.answer(text, reply_markup=keyboard)
    else:
        await update.message.edit_text(text, reply_markup=keyboard)
        await update.answer()
        
    await state.set_state(ProfitCalculator.waiting_for_currency)

@router.callback_query(ProfitCalculator.waiting_for_currency, F.data.startswith("calc_currency_"))
async def process_currency_selection(call: CallbackQuery, state: FSMContext):
    """Шаг 1: Обработка выбора валюты."""
    currency = call.data.split("_")[-1]
    await state.update_data(currency=currency)
    logger.info(f"User {call.from_user.id} selected currency: {currency}")
    
    prompts = {
        "usd": "💡 Введите стоимость электроэнергии в <b>USD</b> за кВт/ч (например, <code>0.05</code>):",
        "rub": "💡 Введите стоимость электроэнергии в <b>рублях</b> за кВт/ч (например, <code>4.5</code>):"
    }
    await call.message.edit_text(prompts[currency], reply_markup=build_cancel_keyboard())
    await state.set_state(ProfitCalculator.waiting_for_electricity_cost)
    await call.answer()

@router.message(ProfitCalculator.waiting_for_electricity_cost)
async def process_electricity_cost(message: Message, state: FSMContext, asic_service: AsicService, market_data_service: MarketDataService):
    """Шаг 2: Обработка стоимости электроэнергии и показ списка ASIC."""
    logger.info(f"User {message.from_user.id} entered electricity cost: '{message.text}'")
    try:
        cost = float(message.text.replace(',', '.').strip())
        if cost < 0: raise ValueError("Стоимость не может быть отрицательной.")
    except (ValueError, TypeError):
        await message.answer("❌ Неверный формат. Введите корректное число (например, <b>4.5</b>).", reply_markup=build_cancel_keyboard())
        return

    msg = await message.answer("⏳ Подготавливаю данные...")
    user_data = await state.get_data()
    currency = user_data.get("currency")
    cost_usd = cost

    if currency == "rub":
        await msg.edit_text("⏳ Получаю актуальный курс USD/RUB...")
        rate_usd_rub = await market_data_service.get_usd_rub_rate()
        if not rate_usd_rub:
            await msg.edit_text("❌ Не удалось получить курс валют. Попробуйте позже.", reply_markup=build_cancel_keyboard())
            await state.clear()
            return
        cost_usd = cost / rate_usd_rub
    
    await state.update_data(electricity_cost_usd=cost_usd)
    
    await msg.edit_text("⏳ Загружаю список оборудования...")
    all_asics, _ = await asic_service.get_top_asics(count=1000, electricity_cost=0.0)
    
    if not all_asics:
        await msg.edit_text("❌ Ошибка: не удалось загрузить список ASIC. Расчет невозможен.", reply_markup=build_cancel_keyboard())
        await state.clear()
        return

    await state.update_data(asic_list=[asic.model_dump() for asic in all_asics])
    
    builder = InlineKeyboardBuilder()
    items_per_page, page = 8, 0
    start, end = page * items_per_page, page * items_per_page + items_per_page
    for i, asic in enumerate(all_asics[start:end]):
        builder.button(text=f"✅ {asic.name}", callback_data=f"prof_calc_select_{i + start}")
    builder.adjust(2)
    if end < len(all_asics):
        builder.row(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"prof_calc_page_1"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="prof_calc_cancel"))

    await msg.edit_text("✅ Отлично! Теперь выберите ваш ASIC-майнер из списка:", reply_markup=builder.as_markup())
    logger.info(f"User {message.from_user.id}: a list of ASICs is shown. Setting state to waiting_for_asic_selection.")
    await state.set_state(ProfitCalculator.waiting_for_asic_selection)

@router.callback_query(ProfitCalculator.waiting_for_asic_selection, F.data.startswith("prof_calc_"))
async def process_asic_selection(call: CallbackQuery, state: FSMContext):
    """Шаг 3: Обработка выбора ASIC или пагинации."""
    logger.info(f"User {call.from_user.id} interacted with ASIC list: {call.data}")
    user_data = await state.get_data()
    asic_list_data = user_data.get("asic_list", [])
    if not asic_list_data:
        await call.message.edit_text("❌ Произошла ошибка: список ASIC потерян. Начните заново.", reply_markup=build_cancel_keyboard())
        await state.clear()
        return
        
    all_asics = [AsicMiner(**data) for data in asic_list_data]
    action, _, value = call.data.partition("_")[2].partition("_")

    if action == "page":
        page = int(value)
        items_per_page = 8
        start, end = page * items_per_page, (page + 1) * items_per_page
        
        builder = InlineKeyboardBuilder()
        for i, asic in enumerate(all_asics[start:end]):
            builder.button(text=f"✅ {asic.name}", callback_data=f"prof_calc_select_{i + start}")
        builder.adjust(2)
        
        nav_buttons = []
        if page > 0: nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"prof_calc_page_{page - 1}"))
        if end < len(all_asics): nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"prof_calc_page_{page + 1}"))
        builder.row(*nav_buttons)
        builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="prof_calc_cancel"))
        
        await call.message.edit_text("Выберите ваш ASIC-майнер из списка:", reply_markup=builder.as_markup())
        await call.answer()
        return

    if action == "select":
        asic_index = int(value)
        selected_asic = all_asics[asic_index]
        
        if not all([selected_asic.hashrate, selected_asic.power, selected_asic.algorithm, selected_asic.hashrate.lower() != 'n/a', re.search(r'[\d.]+', selected_asic.hashrate), selected_asic.power > 0]):
             await call.answer("ℹ️ Для этой модели нет всех данных для расчета. Выберите другую.", show_alert=True)
             return

        await state.update_data(selected_asic=selected_asic.model_dump())
        await call.message.edit_text("📊 Введите комиссию вашего пула в % (например, <code>1</code> или <code>1.5</code>):", reply_markup=build_cancel_keyboard())
        logger.info(f"User {call.from_user.id} selected ASIC: {selected_asic.name}. Setting state to waiting_for_pool_commission.")
        await state.set_state(ProfitCalculator.waiting_for_pool_commission)

    await call.answer()
    
@router.message(ProfitCalculator.waiting_for_pool_commission)
async def process_pool_commission(message: Message, state: FSMContext, mining_service: MiningService):
    """Шаг 4: Получение комиссии и финальный расчет."""
    logger.info(f"User {message.from_user.id} entered pool commission: '{message.text}'")
    user_data = await state.get_data()
    selected_asic_data = user_data.get("selected_asic")
    electricity_cost_usd = user_data.get("electricity_cost_usd")

    # Проверка, не пропустили ли мы шаг
    if not selected_asic_data:
        logger.error(f"User {message.from_user.id} is in pool commission state, but no ASIC was selected.")
        await message.answer("❌ Ошибка! Не был выбран ASIC. Пожалуйста, начните расчет заново.", reply_markup=build_cancel_keyboard())
        await state.clear()
        return

    try:
        commission_percent = float(message.text.replace(',', '.').strip())
        if not (0 <= commission_percent < 100):
            raise ValueError("Комиссия должна быть от 0 до 99.9")
    except (ValueError, TypeError):
        await message.answer("❌ Неверный формат. Введите число (например, <b>1.5</b>).", reply_markup=build_cancel_keyboard())
        return

    msg = await message.answer("⏳ Считаю...")
    try:
        selected_asic = AsicMiner(**selected_asic_data)
        result_text = await mining_service.calculate(
            hashrate_str=selected_asic.hashrate,
            power_consumption_watts=selected_asic.power,
            electricity_cost=electricity_cost_usd,
            pool_commission=commission_percent,
            algorithm=selected_asic.algorithm
        )
        await msg.edit_text(result_text, disable_web_page_preview=True)
        logger.info(f"Calculation for user {message.from_user.id} is complete.")
    except Exception as e:
        logger.error(f"Error in final calculation for user {message.from_user.id}: {e}", exc_info=True)
        await msg.edit_text("❌ Произошла непредвиденная ошибка при расчете. Пожалуйста, сообщите администратору.", reply_markup=build_cancel_keyboard())
    finally:
        await state.clear()

# Единый обработчик отмены для всех состояний калькулятора
@router.callback_query(ProfitCalculator, F.data == "prof_calc_cancel")
async def cancel_calculator(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("✅ Расчет отменен.")
    await call.answer()
    logger.info(f"User {call.from_user.id} cancelled the calculation.")
