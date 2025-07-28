# ===============================================================
# Файл: bot/handlers/game/mining_game_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: "Тонкий" обработчик для игры "Виртуальный Майнинг".
# Управляет навигацией по меню и вызывает MiningGameService.
# ===============================================================
import logging
from aiogram import F, Router, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config.settings import settings
# --- ИСПРАВЛЕНИЕ: Импортируем сервис из правильного файла ---
from bot.services.mining_game_service import MiningGameService
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from bot.services.asic_service import AsicService
from bot.services.admin_service import AdminService
from bot.states.mining_states import MiningGameState
from bot.keyboards.mining_keyboards import (
    get_mining_menu_keyboard, get_shop_keyboard, get_my_farm_keyboard,
    get_withdraw_keyboard, get_electricity_menu_keyboard
)
from bot.utils.ui_helpers import show_main_menu_from_callback

game_router = Router()
logger = logging.getLogger(__name__)

# --- Главное меню и навигация ---

@game_router.callback_query(F.data == "nav:mining_game")
async def handle_mining_menu(call: CallbackQuery, state: FSMContext, admin_service: AdminService):
    """Отображает главное меню игры 'Виртуальный Майнинг'."""
    await state.clear()
    await admin_service.track_action("nav:mining_game")
    text = "💎 <b>Центр управления Виртуальным Майнингом</b>\n\nВыберите действие:"
    await call.message.edit_text(text, reply_markup=get_mining_menu_keyboard())

# --- Магазин оборудования ---

async def show_shop_page(call: CallbackQuery, asic_service: AsicService, page: int = 0):
    """Вспомогательная функция для отображения страницы магазина."""
    asics, _ = await asic_service.get_top_asics(count=1000, electricity_cost=0.0)
    if not asics:
        await call.message.edit_text(
            "К сожалению, список оборудования временно недоступен.",
            reply_markup=get_mining_menu_keyboard()
        )
        return
    text = "🏪 <b>Магазин оборудования</b>\n\nВыберите ASIC для запуска сессии:"
    keyboard = get_shop_keyboard(asics, page)
    await call.message.edit_text(text, reply_markup=keyboard)

@game_router.callback_query(F.data == "game_nav:shop")
async def handle_shop_menu(call: CallbackQuery, asic_service: AsicService, admin_service: AdminService):
    """Отображает первую страницу магазина."""
    await admin_service.track_action("game_nav:shop")
    await call.message.edit_text("⏳ Загружаю оборудование...")
    await show_shop_page(call, asic_service, 0)

@game_router.callback_query(F.data.startswith("game_shop_page:"))
async def handle_shop_pagination(call: CallbackQuery, asic_service: AsicService):
    """Обрабатывает пагинацию в магазине."""
    page = int(call.data.split(":")[2])
    await show_shop_page(call, asic_service, page)

# --- Логика игры ---

@game_router.callback_query(F.data.startswith("game_action:start:"))
async def handle_start_mining(call: CallbackQuery, game_service: MiningGameService, asic_service: AsicService, admin_service: AdminService):
    """Запускает майнинг-сессию для пользователя."""
    asic_index = int(call.data.split(":")[2])
    
    result_text = await game_service.start_session(
        user_id=call.from_user.id,
        asic_index=asic_index
    )
    
    # Отслеживаем только успешный запуск
    if "✅" in result_text:
        all_asics, _ = await asic_service.get_top_asics(count=1000)
        if asic_index < len(all_asics):
            await admin_service.track_action(f"game_start:{all_asics[asic_index].name}")
    
    await call.message.edit_text(result_text, reply_markup=get_mining_menu_keyboard())

@game_router.callback_query(F.data == "game_nav:my_farm")
async def handle_my_farm(call: CallbackQuery, game_service: MiningGameService, admin_service: AdminService):
    """Показывает информацию об активной сессии и статистике."""
    await admin_service.track_action("game_nav:my_farm")
    
    # Получаем всю информацию одним вызовом
    farm_info_text, user_stats_text = await game_service.get_farm_and_stats_info(call.from_user.id)
    
    full_text = f"{farm_info_text}\n\n{user_stats_text}"
    
    await call.message.edit_text(full_text, reply_markup=get_my_farm_keyboard())

# --- Вывод средств и рефералы ---

@game_router.callback_query(F.data == "game_action:withdraw")
async def handle_withdraw(call: CallbackQuery, game_service: MiningGameService, admin_service: AdminService):
    """Обрабатывает вывод средств."""
    await admin_service.track_action("game_action:withdraw")
    
    result_text, can_withdraw = await game_service.process_withdrawal(call.from_user.id)
    
    if can_withdraw:
        await call.message.edit_text(result_text, reply_markup=get_withdraw_keyboard())
    else:
        await call.answer(result_text, show_alert=True)

@game_router.callback_query(F.data == "game_action:invite")
async def handle_invite_friend(call: CallbackQuery, bot: Bot, admin_service: AdminService):
    """Показывает реферальную ссылку."""
    await admin_service.track_action("game_action:invite")
    
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    
    text = (
        f"🤝 <b>Ваша реферальная программа</b>\n\n"
        f"Пригласите друга, и как только он запустит бота по вашей ссылке, вы получите бонус в размере "
        f"<b>{settings.game.referral_bonus:.2f} монет</b>!\n\n"
        f"Ваша персональная ссылка для приглашения:\n"
        f"<code>{referral_link}</code>"
    )
    # Отвечаем новым сообщением, чтобы не заменять меню
    await call.message.answer(text)

# --- Управление электроэнергией ---

@game_router.callback_query(F.data == "game_nav:electricity")
async def handle_electricity_menu(call: CallbackQuery, game_service: MiningGameService, admin_service: AdminService):
    """Показывает меню управления тарифами."""
    await admin_service.track_action("game_nav:electricity")
    
    text, keyboard = await game_service.get_electricity_menu(call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard)

@game_router.callback_query(F.data.startswith("game_tariff_select:"))
async def handle_select_tariff(call: CallbackQuery, game_service: MiningGameService):
    """Выбирает тариф."""
    tariff_name = call.data.split(":")[2]
    alert_text = await game_service.select_tariff(call.from_user.id, tariff_name)
    await call.answer(alert_text, show_alert=True)
    # Обновляем меню после выбора
    text, keyboard = await game_service.get_electricity_menu(call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard)

@game_router.callback_query(F.data.startswith("game_tariff_buy:"))
async def handle_buy_tariff(call: CallbackQuery, game_service: MiningGameService, admin_service: AdminService):
    """Покупает тариф."""
    tariff_name = call.data.split(":")[2]
    alert_text = await game_service.buy_tariff(call.from_user.id, tariff_name)
    await call.answer(alert_text, show_alert=True)
    
    if "🎉" in alert_text: # Если покупка успешна
        await admin_service.track_action(f"game_buy_tariff:{tariff_name}")
    
    # Обновляем меню после покупки
    text, keyboard = await game_service.get_electricity_menu(call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard)
