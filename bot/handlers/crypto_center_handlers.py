import logging
import redis.asyncio as redis
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.services.crypto_center_service import CryptoCenterService
from bot.services.admin_service import AdminService
from bot.keyboards.keyboards import (
    get_crypto_center_main_menu_keyboard, 
    get_crypto_center_guides_menu_keyboard,
    get_airdrops_list_keyboard, 
    get_airdrop_details_keyboard
)

router = Router()
logger = logging.getLogger(__name__)

# --- ГЛАВНОЕ МЕНЮ КРИПТО-ЦЕНТРА ---

@router.message(F.text == "💎 Крипто-Центр")
async def handle_crypto_center_menu(message: Message, admin_service: AdminService):
    """Отображает главное меню Крипто-Центра с выбором разделов."""
    await admin_service.track_command_usage("💎 Крипто-Центр")
    text = (
        "<b>💎 Крипто-Центр</b>\n\n"
        "Эксклюзивный раздел с информацией, которая может принести прибыль.\n\n"
        "Выберите направление:"
    )
    await message.answer(text, reply_markup=get_crypto_center_main_menu_keyboard())

@router.callback_query(F.data == "back_to_crypto_center_main")
async def back_to_crypto_center_main_menu(call: CallbackQuery):
    """Возвращает в главное меню Крипто-Центра."""
    text = (
        "<b>💎 Крипто-Центр</b>\n\n"
        "Эксклюзивный раздел с информацией, которая может принести прибыль.\n\n"
        "Выберите направление:"
    )
    await call.message.edit_text(text, reply_markup=get_crypto_center_main_menu_keyboard())
    await call.answer()
    
# --- РАЗДЕЛ: ЛЕНТА НОВОСТЕЙ ---

@router.callback_query(F.data == "crypto_center_feed")
async def handle_live_feed(call: CallbackQuery, crypto_center_service: CryptoCenterService):
    """Отображает самообновляемую ленту новостей."""
    await call.message.edit_text("⏳ Загружаю свежие новости...")
    
    news_feed = await crypto_center_service.fetch_live_feed()
    
    if not news_feed:
        text = "😕 Не удалось загрузить ленту новостей. Попробуйте позже."
    else:
        text = "<b>⚡️ Лента Крипто-Новостей (Live)</b>\n\n"
        for item in news_feed:
            text += f"▪️ <a href='{item['url']}'>{item['title']}</a>\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить ленту", callback_data="crypto_center_feed")
    builder.button(text="⬅️ Назад в Крипто-Центр", callback_data="back_to_crypto_center_main")
    builder.adjust(1)
    
    await call.message.edit_text(text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    await call.answer()

# --- РАЗДЕЛ КУРАТОРСКИХ ГАЙДОВ ---

@router.callback_query(F.data == "crypto_center_guides")
async def handle_guides_menu(call: CallbackQuery):
    """Показывает меню выбора типа гайдов."""
    text = "<b>📚 Кураторские Гайды</b>\n\nВыберите категорию:"
    await call.message.edit_text(text, reply_markup=get_crypto_center_guides_menu_keyboard())
    await call.answer()

# --- ПОДРАЗДЕЛ AIRDROPS ---

@router.callback_query(F.data == "guides_airdrops")
async def handle_airdrops_list(call: CallbackQuery, crypto_center_service: CryptoCenterService, redis_client: redis.Redis):
    """Отображает список Airdrop-проектов."""
    text = (
        "<b>💧 Охота за Airdrop'ами</b>\n\n"
        "Выберите проект, чтобы увидеть чеклист и отследить свой прогресс."
    )
    
    # --- ЛОГИКА ПОДГОТОВКИ ДАННЫХ ПЕРЕНЕСЕНА СЮДА ИЗ KEYBOARDS.PY ---
    user_id = call.from_user.id
    all_airdrops = crypto_center_service.get_all_airdrops()
    airdrops_with_progress = []
    for airdrop in all_airdrops:
        progress = await crypto_center_service.get_user_progress(user_id, airdrop['id'])
        total_tasks = len(airdrop['tasks'])
        progress_text = f"✅ {len(progress)}/{total_tasks}"
        airdrops_with_progress.append({
            "name": airdrop['name'],
            "id": airdrop['id'],
            "progress_text": progress_text
        })
    # --- КОНЕЦ ЛОГИКИ ПОДГОТОВКИ ДАННЫХ ---

    # Передаем уже готовые данные в функцию клавиатуры
    keyboard = await get_airdrops_list_keyboard(airdrops_with_progress)
    
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()


@router.callback_query(F.data.startswith("airdrop_details_"))
async def show_airdrop_details(call: CallbackQuery, crypto_center_service: CryptoCenterService, redis_client: redis.Redis):
    """Показывает детальную информацию о выбранном Airdrop проекте."""
    airdrop_id = call.data.split("_")[2]
    airdrop = crypto_center_service.get_airdrop_by_id(airdrop_id)

    if not airdrop:
        await call.answer("❌ Проект не найден.", show_alert=True)
        return

    user_progress = await crypto_center_service.get_user_progress(call.from_user.id, airdrop_id)
    keyboard = await get_airdrop_details_keyboard(airdrop, user_progress)

    text = (
        f"<b>Проект: {airdrop['name']}</b> ({airdrop['status']})\n\n"
        f"{airdrop['description']}\n\n"
        f"<b>Чеклист для получения Airdrop:</b>"
    )
    
    await call.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data.startswith("toggle_task_"))
async def toggle_task(call: CallbackQuery, crypto_center_service: CryptoCenterService, redis_client: redis.Redis):
    """Обрабатывает нажатие на задачу в чеклисте."""
    try:
        _, airdrop_id, task_index_str = call.data.split("_")
        task_index = int(task_index_str)
    except (ValueError, IndexError):
        await call.answer("❌ Ошибка данных.", show_alert=True)
        return

    airdrop = crypto_center_service.get_airdrop_by_id(airdrop_id)
    if not airdrop or task_index >= len(airdrop['tasks']):
        await call.answer("❌ Задача или проект не найдены.", show_alert=True)
        return

    await crypto_center_service.toggle_task_status(call.from_user.id, airdrop_id, task_index)
    
    user_progress = await crypto_center_service.get_user_progress(call.from_user.id, airdrop_id)
    new_keyboard = await get_airdrop_details_keyboard(airdrop, user_progress)

    await call.message.edit_reply_markup(reply_markup=new_keyboard)
    await call.answer("Статус задачи обновлен!")


@router.callback_query(F.data == "back_to_airdrops_list")
async def back_to_airdrops_list(call: CallbackQuery, crypto_center_service: CryptoCenterService, redis_client: redis.Redis):
    """Возвращает пользователя к списку Airdrop проектов."""
    await handle_airdrops_list(call, crypto_center_service, redis_client)

# --- ПОДРАЗДЕЛ MINING SIGNALS ---

@router.callback_query(F.data == "guides_mining")
async def handle_mining_signals_list(call: CallbackQuery, crypto_center_service: CryptoCenterService):
    """Отображает список актуальных майнинг-сигналов."""
    signals = crypto_center_service.get_all_mining_signals()
    
    if not signals:
        text = "<b>⛏️ Сигналы для майнеров</b>\n\nНа данный момент нет активных сигналов. Загляните позже!"
    else:
        text = "<b>⛏️ Сигналы для майнеров</b>\n\n"
        for signal in signals:
            text += (
                f"\n➖➖➖➖➖➖➖➖➖➖\n"
                f"<b>{signal['name']}</b> (Статус: {signal['status']})\n"
                f"<i>{signal['description']}</i>\n"
                f"<b>Алгоритм:</b> <code>{signal['algorithm']}</code>\n"
                f"<b>Оборудование:</b> {signal['hardware']}\n"
                f"<a href='{signal['guide_url']}'>Подробный гайд</a>"
            )
            
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к выбору гайдов", callback_data="crypto_center_guides")
    
    await call.message.edit_text(text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    await call.answer()
