# ===============================================================
# Файл: bot/handlers/game/mining_game_handler.py
# ПРОДАКШН-ВЕРСИЯ 2025 — ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ
# Описание: "Тонкий" обработчик с FSM и надёжными ID в колбэках.
# ===============================================================

from __future__ import annotations

import logging
from aiogram import F, Router, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config.settings import settings
from bot.states.game_states import MiningGameStates
from bot.keyboards.mining_keyboards import (
    get_mining_menu_keyboard,
    get_shop_keyboard,
    get_my_farm_keyboard,
    get_withdraw_keyboard,
    get_confirm_purchase_keyboard,
)
from bot.utils.text_utils import normalize_asic_name
from bot.utils.models import AsicMiner
from bot.utils.dependencies import Deps
from bot.keyboards.callback_factories import GameCallback

# ИСПРАВЛЕНО: Имя роутера соответствует ожиданиям
game_router = Router(name="mining_game_handler")
logger = logging.getLogger(__name__)


def _fmt_money(val, digits: int = 2, dash: str = "—") -> str:
    try:
        if val is None:
            return dash
        return f"{float(val):,.{digits}f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(val) if val is not None else dash


# --- Главное меню / навигация ---

@game_router.callback_query(GameCallback.filter(F.action == "main_menu"))
async def handle_mining_menu(call: CallbackQuery, state: FSMContext, deps: Deps):
    game_service = deps.mining_game_service
    await state.clear()

    text = "💎 <b>Центр управления Виртуальным Майнингом</b>\n\nВыберите действие:"
    farm_info, stats_info = await game_service.get_farm_and_stats_info(call.from_user.id)
    full_text = f"{text}\n\n{farm_info}\n\n{stats_info}"

    session_data = await game_service.redis.hgetall(
        game_service.keys.active_session(call.from_user.id)
    )
    is_session_active = bool(session_data)

    await call.message.edit_text(full_text, reply_markup=get_mining_menu_keyboard(is_session_active), parse_mode="HTML")
    await call.answer()


# --- Магазин (FSM-кэш) ---

async def show_shop_page(call: CallbackQuery, state: FSMContext, deps: Deps, page: int = 0):
    asic_service = deps.asic_service
    game_service = deps.mining_game_service

    fsm_data = await state.get_data()
    asics_data = fsm_data.get("shop_asics")
    asics = [AsicMiner(**data) for data in asics_data] if asics_data else []

    if not asics:
        logger.info("User %s fetching new ASIC list for shop.", call.from_user.id)
        asics, _ = await asic_service.get_top_asics(electricity_cost=0.05, count=50)
        if not asics:
            is_session_active = await game_service.redis.exists(
                game_service.keys.active_session(call.from_user.id)
            )
            await call.message.edit_text(
                "К сожалению, список оборудования временно недоступен.",
                reply_markup=get_mining_menu_keyboard(bool(is_session_active)),
                parse_mode="HTML",
            )
            return
        await state.update_data(shop_asics=[asic.model_dump() for asic in asics])

    text = "🏪 <b>Магазин оборудования</b>\n\nВыберите ASIC для покупки и запуска сессии:"
    await call.message.edit_text(text, reply_markup=get_shop_keyboard(asics, page), parse_mode="HTML")
    await call.answer()


@game_router.callback_query(GameCallback.filter(F.action == "shop"))
async def handle_shop_menu(call: CallbackQuery, state: FSMContext, deps: Deps):
    await call.message.edit_text("⏳ Загружаю оборудование...", parse_mode="HTML")
    await state.set_state(MiningGameStates.in_shop)
    await show_shop_page(call, state, deps, 0)


@game_router.callback_query(GameCallback.filter(F.action == "shop_page"), MiningGameStates.in_shop)
async def handle_shop_pagination(call: CallbackQuery, callback_data: GameCallback, state: FSMContext, deps: Deps):
    page = int(getattr(callback_data, "page", 0))
    await show_shop_page(call, state, deps, page)


# --- Покупка / запуск ---

@game_router.callback_query(GameCallback.filter(F.action == "start"), MiningGameStates.in_shop)
async def handle_purchase_confirmation(call: CallbackQuery, callback_data: GameCallback, state: FSMContext, deps: Deps):
    asic_id_norm = callback_data.value

    fsm_data = await state.get_data()
    shop_asics_data = fsm_data.get("shop_asics", [])
    shop_asics = [AsicMiner(**data) for data in shop_asics_data]

    selected_asic = next(
        (asic for asic in shop_asics if normalize_asic_name(asic.name) == asic_id_norm),
        None,
    )

    if not selected_asic:
        await call.answer("Ошибка! Этот ASIC больше не доступен. Обновите магазин.", show_alert=True)
        return

    await state.update_data(selected_asic_json=selected_asic.model_dump())
    await state.set_state(MiningGameStates.confirm_purchase)

    text = (
        f"Вы собираетесь приобрести <b>{selected_asic.name}</b>.\n"
        f"Цена: <b>{_fmt_money(selected_asic.price)} монет</b>.\n\n"
        "После покупки сессия майнинга начнется автоматически. Подтверждаете?"
    )
    await call.message.edit_text(text, reply_markup=get_confirm_purchase_keyboard(asic_id_norm), parse_mode="HTML")


@game_router.callback_query(GameCallback.filter(F.action == "buy_confirm"), MiningGameStates.confirm_purchase)
async def handle_start_mining(call: CallbackQuery, state: FSMContext, deps: Deps):
    game_service = deps.mining_game_service
    fsm_data = await state.get_data()
    selected_asic_data = fsm_data.get("selected_asic_json")

    if not selected_asic_data:
        await call.answer("Произошла ошибка, данные о сессии устарели.", show_alert=True)
        return

    selected_asic = AsicMiner(**selected_asic_data)

    result_text, success = await game_service.purchase_and_start_session(call.from_user.id, selected_asic)

    if not success:
        await call.answer(result_text, show_alert=True)
        return

    await call.message.edit_text(result_text, parse_mode="HTML")
    await state.clear()
    await handle_mining_menu(call, state, deps)


@game_router.callback_query(GameCallback.filter(F.action == "buy_cancel"), MiningGameStates.confirm_purchase)
async def handle_cancel_purchase(call: CallbackQuery, state: FSMContext, deps: Deps):
    """Отмена покупки -> возвращаемся в магазин на первую страницу."""
    await state.set_state(MiningGameStates.in_shop)
    await show_shop_page(call, state, deps, 0)


# --- Моя ферма / вывод / рефералы ---

@game_router.callback_query(GameCallback.filter(F.action == "my_farm"))
async def handle_my_farm(call: CallbackQuery, deps: Deps):
    farm_info_text, user_stats_text = await deps.mining_game_service.get_farm_and_stats_info(call.from_user.id)
    full_text = f"{farm_info_text}\n\n{user_stats_text}"
    await call.message.edit_text(full_text, reply_markup=get_my_farm_keyboard(), parse_mode="HTML")
    await call.answer()


@game_router.callback_query(GameCallback.filter(F.action == "withdraw"))
async def handle_withdraw(call: CallbackQuery, deps: Deps):
    game_service = deps.mining_game_service
    user, _ = await game_service.user_service.get_or_create_user(call.from_user)
    result_text, can_withdraw = await game_service.process_withdrawal(user)
    if can_withdraw:
        await call.message.edit_text(result_text, reply_markup=get_withdraw_keyboard(), parse_mode="HTML")
    else:
        await call.answer(result_text, show_alert=True)


@game_router.callback_query(GameCallback.filter(F.action == "invite"))
async def handle_invite_friend(call: CallbackQuery, bot: Bot):
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    text = (
        f"🤝 <b>Ваша реферальная программа</b>\n\n"
        f"Пригласите друга, и как только он запустит бота по вашей ссылке, вы получите бонус в размере "
        f"<b>{settings.game.min_withdrawal_amount / 20:.2f} монет</b>!\n\n"
        f"Ваша персональная ссылка для приглашения:\n"
        f"<code>{referral_link}</code>"
    )
    await call.message.edit_text(text, reply_markup=get_my_farm_keyboard(), parse_mode="HTML")
    await call.answer("Ваша реферальная ссылка сформирована!")


# --- Электричество ---

@game_router.callback_query(GameCallback.filter(F.action == "electricity"))
async def handle_electricity_menu(call: CallbackQuery, deps: Deps):
    text, keyboard = await deps.mining_game_service.get_electricity_menu(call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()


@game_router.callback_query(GameCallback.filter(F.action == "tariff_select"))
async def handle_select_tariff(call: CallbackQuery, callback_data: GameCallback, deps: Deps):
    game_service = deps.mining_game_service
    tariff_name = callback_data.value
    alert_text = await game_service.select_tariff(call.from_user.id, tariff_name)
    await call.answer(alert_text, show_alert=True)
    text, keyboard = await game_service.get_electricity_menu(call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@game_router.callback_query(GameCallback.filter(F.action == "tariff_buy"))
async def handle_buy_tariff(call: CallbackQuery, callback_data: GameCallback, deps: Deps):
    game_service = deps.mining_game_service
    tariff_name = callback_data.value
    alert_text = await game_service.buy_tariff(call.from_user.id, tariff_name)
    await call.answer(alert_text, show_alert=True)
    if "🎉" in alert_text:
        text, keyboard = await game_service.get_electricity_menu(call.from_user.id)
        await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")