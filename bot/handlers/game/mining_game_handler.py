# ===============================================================
# Файл: bot/handlers/game/mining_game_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: "Тонкий" обработчик, использующий FSM для оптимизации
# и надежные идентификаторы в колбэках.
# ===============================================================
import logging
from aiogram import F, Router, Bot, types
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config.settings import settings
from bot.services.mining_game_service import MiningGameService
from bot.services.asic_service import AsicService
from bot.states.mining_states import MiningGameStates
from bot.keyboards.mining_keyboards import (
    get_mining_menu_keyboard, get_shop_keyboard, get_my_farm_keyboard,
    get_withdraw_keyboard
)

game_router = Router(name=__name__)
logger = logging.getLogger(__name__)

# --- Главное меню и навигация ---

@game_router.callback_query(F.data == "nav:mining_game")
async def handle_mining_menu(call: CallbackQuery, state: FSMContext):
    """Отображает главное меню игры 'Виртуальный Майнинг'."""
    await state.clear() # Очищаем состояние при входе в главное меню игры
    text = "💎 <b>Центр управления Виртуальным Майнингом</b>\n\nВыберите действие:"
    await call.message.edit_text(text, reply_markup=get_mining_menu_keyboard())

# --- Магазин оборудования (с FSM для кэширования) ---

async def show_shop_page(call: CallbackQuery, state: FSMContext, asic_service: AsicService, page: int = 0):
    """Отображает страницу магазина, используя данные из FSM или загружая их."""
    fsm_data = await state.get_data()
    asics = fsm_data.get('shop_asics')

    if not asics:
        logger.info(f"User {call.from_user.id} fetching new ASIC list for shop.")
        # --- УЛУЧШЕНИЕ: Загружаем список ОДИН РАЗ ---
        asics, _ = await asic_service.get_top_asics(count=50) # Загружаем разумное количество для игры
        if not asics:
            await call.message.edit_text(
                "К сожалению, список оборудования временно недоступен.",
                reply_markup=get_mining_menu_keyboard()
            )
            return
        # --- УЛУЧШЕНИЕ: Кэшируем список в FSM ---
        await state.update_data(shop_asics=asics)
    
    text = "🏪 <b>Магазин оборудования</b>\n\nВыберите ASIC для запуска сессии:"
    keyboard = get_shop_keyboard(asics, page)
    await call.message.edit_text(text, reply_markup=keyboard)

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
    # --- УЛУЧШЕНИЕ: Используем стабильный ID вместо хрупкого индекса ---
    asic_id = call.data.split(":")[-1]
    
    fsm_data = await state.get_data()
    shop_asics = fsm_data.get('shop_asics', [])
    
    # Находим нужный ASIC в закэшированном списке
    selected_asic = next((asic for asic in shop_asics if normalize_asic_name(asic.name) == asic_id), None)
    
    if not selected_asic:
        await call.answer("Ошибка! Этот ASIC больше не доступен. Обновите магазин.", show_alert=True)
        return

    result_text = await game_service.start_session(call.from_user.id, selected_asic)
    await call.message.edit_text(result_text, reply_markup=get_mining_menu_keyboard())
    await state.clear() # Выходим из состояния магазина

@game_router.callback_query(F.data == "game_nav:my_farm")
async def handle_my_farm(call: CallbackQuery, game_service: MiningGameService):
    """Показывает информацию об активной сессии и статистике."""
    farm_info_text, user_stats_text = await game_service.get_farm_and_stats_info(call.from_user.id)
    full_text = f"{farm_info_text}\n\n{user_stats_text}"
    await call.message.edit_text(full_text, reply_markup=get_my_farm_keyboard())

# --- Вывод средств и рефералы ---

@game_router.callback_query(F.data == "game_action:withdraw")
async def handle_withdraw(call: CallbackQuery, game_service: MiningGameService):
    """Обрабатывает вывод средств."""
    result_text, can_withdraw = await game_service.process_withdrawal(call.from_user.id)
    if can_withdraw:
        await call.message.edit_text(result_text, reply_markup=get_withdraw_keyboard())
    else:
        await call.answer(result_text, show_alert=True)

@game_gouter.callback_query(F.data == "game_action:invite")
async def handle_invite_friend(call: CallbackQuery, bot_info: types.User):
    """Показывает реферальную ссылку, используя кэшированные данные о боте."""
    # --- УЛУЧШЕНИЕ: Используем кэшированный `bot_info` из `deps` ---
    referral_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    text = (
        f"🤝 <b>Ваша реферальная программа</b>\n\n"
        f"Пригласите друга, и как только он запустит бота по вашей ссылке, вы получите бонус в размере "
        f"<b>{settings.game.referral_bonus_amount:.2f} монет</b>!\n\n"
        f"Ваша персональная ссылка для приглашения:\n"
        f"<code>{referral_link}</code>"
    )
    await call.message.answer(text)

# --- Управление электроэнергией ---

@game_router.callback_query(F.data == "game_nav:electricity")
async def handle_electricity_menu(call: CallbackQuery, game_service: MiningGameService):
    """Показывает меню управления тарифами."""
    text, keyboard = await game_service.get_electricity_menu(call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard)

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