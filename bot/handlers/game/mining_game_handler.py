# ===============================================================
# Файл: bot/handlers/game/mining_game_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - ИСПРАВЛЕННАЯ)
# Описание: "Тонкий" обработчик, использующий FSM для оптимизации
# и надежные идентификаторы в колбэках.
# ===============================================================
import logging
from aiogram import F, Router, Bot, types
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config.config import settings
from bot.services.mining_game_service import MiningGameService
from bot.services.asic_service import AsicService
from bot.states.game_states import MiningGameStates # <-- ИСПРАВЛЕН ИМПОРТ
from bot.keyboards.mining_keyboards import (
    get_mining_menu_keyboard, get_shop_keyboard, get_my_farm_keyboard,
    get_withdraw_keyboard
)
from bot.utils.text_utils import normalize_asic_name
from bot.utils.models import AsicMiner

game_router = Router(name=__name__)
logger = logging.getLogger(__name__)

# --- Главное меню и навигация ---

@game_router.callback_query(F.data == "nav:mining_game")
async def handle_mining_menu(call: CallbackQuery, state: FSMContext, game_service: MiningGameService):
    """Отображает главное меню игры 'Виртуальный Майнинг'."""
    await state.clear()
    text = "💎 <b>Центр управления Виртуальным Майнингом</b>\n\nВыберите действие:"
    farm_info, stats_info = await game_service.get_farm_and_stats_info(call.from_user.id)
    full_text = f"{text}\n\n{farm_info}\n\n{stats_info}"
    
    session_data = await game_service.redis.hgetall(game_service.keys.active_session(call.from_user.id))
    is_session_active = bool(session_data)
    
    await call.message.edit_text(full_text, reply_markup=get_mining_menu_keyboard(is_session_active))
    await call.answer()


# --- Магазин оборудования (с FSM для кэширования) ---

async def show_shop_page(call: CallbackQuery, state: FSMContext, asic_service: AsicService, page: int = 0):
    """Отображает страницу магазина, используя данные из FSM или загружая их."""
    fsm_data = await state.get_data()
    asics_data = fsm_data.get('shop_asics')
    asics = [AsicMiner(**data) for data in asics_data] if asics_data else []

    if not asics:
        logger.info(f"User {call.from_user.id} fetching new ASIC list for shop.")
        asics, _ = await asic_service.get_top_asics(electricity_cost=0.05, count=50)
        if not asics:
            await call.message.edit_text(
                "К сожалению, список оборудования временно недоступен.",
                reply_markup=get_mining_menu_keyboard(is_session_active=False)
            )
            return
        await state.update_data(shop_asics=[asic.model_dump() for asic in asics])
    
    text = "🏪 <b>Магазин оборудования</b>\n\nВыберите ASIC для запуска сессии:"
    keyboard = get_shop_keyboard(asics, page)
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()


@game_router.callback_query(F.data == "game_nav:shop")
async def handle_shop_menu(call: CallbackQuery, state: FSMContext, asic_service: AsicService):
    """Отображает первую страницу магазина."""
    await call.message.edit_text("⏳ Загружаю оборудование...")
    await state.set_state(MiningGameStates.in_shop)
    await show_shop_page(call, state, asic_service, 0)


@game_router.callback_query(F.data.startswith("game_shop_page:"), MiningGameStates.in_shop)
async def handle_shop_pagination(call: CallbackQuery, state: FSMContext, asic_service: AsicService):
    """Обрабатывает пагинацию в магазине."""
    page = int(call.data.split(":")[-1])
    await show_shop_page(call, state, asic_service, page)


# --- Логика игры ---

@game_router.callback_query(F.data.startswith("game_action:start:"), MiningGameStates.in_shop)
async def handle_start_mining(call: CallbackQuery, state: FSMContext, game_service: MiningGameService):
    """Запускает майнинг-сессию, используя стабильный ID асика."""
    asic_id_norm = call.data.split(":")[-1]
    
    fsm_data = await state.get_data()
    shop_asics_data = fsm_data.get('shop_asics', [])
    shop_asics = [AsicMiner(**data) for data in shop_asics_data]
    
    selected_asic = next((asic for asic in shop_asics if normalize_asic_name(asic.name) == asic_id_norm), None)
    
    if not selected_asic:
        await call.answer("Ошибка! Этот ASIC больше не доступен. Обновите магазин.", show_alert=True)
        return

    result_text = await game_service.start_session(call.from_user.id, selected_asic.id)
    await call.message.edit_text(result_text, reply_markup=get_mining_menu_keyboard(is_session_active=True))
    await state.clear()


@game_router.callback_query(F.data == "game_nav:my_farm")
async def handle_my_farm(call: CallbackQuery, game_service: MiningGameService):
    """Показывает информацию об активной сессии и статистике."""
    farm_info_text, user_stats_text = await game_service.get_farm_and_stats_info(call.from_user.id)
    full_text = f"{farm_info_text}\n\n{user_stats_text}"
    await call.message.edit_text(full_text, reply_markup=get_my_farm_keyboard())
    await call.answer()


# --- Вывод средств и рефералы ---

@game_router.callback_query(F.data == "game_action:withdraw")
async def handle_withdraw(call: CallbackQuery, game_service: MiningGameService):
    """Обрабатывает вывод средств."""
    user, _ = await game_service.user_service.get_or_create_user(call.from_user)
    result_text, can_withdraw = await game_service.process_withdrawal(user)
    if can_withdraw:
        await call.message.edit_text(result_text, reply_markup=get_withdraw_keyboard())
    else:
        await call.answer(result_text, show_alert=True)


@game_router.callback_query(F.data == "game_action:invite")
async def handle_invite_friend(call: CallbackQuery, bot: Bot):
    """Показывает реферальную ссылку."""
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    text = (
        f"🤝 <b>Ваша реферальная программа</b>\n\n"
        f"Пригласите друга, и как только он запустит бота по вашей ссылке, вы получите бонус в размере "
        f"<b>{settings.game.min_withdrawal_amount / 20:.2f} монет</b>!\n\n"
        f"Ваша персональная ссылка для приглашения:\n"
        f"<code>{referral_link}</code>"
    )
    await call.message.edit_text(text, reply_markup=get_my_farm_keyboard())
    await call.answer("Ваша реферальная ссылка сформирована!")


# --- Управление электроэнергией ---

@game_router.callback_query(F.data == "game_nav:electricity")
async def handle_electricity_menu(call: CallbackQuery, game_service: MiningGameService):
    """Показывает меню управления тарифами."""
    text, keyboard = await game_service.get_electricity_menu(call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()


@game_router.callback_query(F.data.startswith("game_tariff_select:"))
async def handle_select_tariff(call: CallbackQuery, game_service: MiningGameService):
    """Выбирает тариф."""
    tariff_name = call.data.split(":")[-1]
    alert_text = await game_service.select_tariff(call.from_user.id, tariff_name)
    await call.answer(alert_text, show_alert=True)
    text, keyboard = await game_service.get_electricity_menu(call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard)


@game_router.callback_query(F.data.startswith("game_tariff_buy:"))
async def handle_buy_tariff(call: CallbackQuery, game_service: MiningGameService):
    """Покупает тариф."""
    tariff_name = call.data.split(":")[-1]
    alert_text = await game_service.buy_tariff(call.from_user.id, tariff_name)
    await call.answer(alert_text, show_alert=True)
    if "🎉" in alert_text:
        text, keyboard = await game_service.get_electricity_menu(call.from_user.id)
        await call.message.edit_text(text, reply_markup=keyboard)