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

AI_DISCLAIMER = "\n\n<i>⚠️ Информация сгенерирована ИИ и может содержать неточности. Всегда проводите собственное исследование (DYOR).</i>"

# --- ГЛАВНОЕ МЕНЮ КРИПТО-ЦЕНТРА ---

@router.message(F.text == "💎 Крипто-Центр")
async def handle_crypto_center_menu(message: Message, admin_service: AdminService):
    await admin_service.track_command_usage("💎 Крипто-Центр")
    text = (
        "<b>💎 Крипто-Центр</b>\n\n"
        "Эксклюзивный раздел с информацией, которая может принести прибыль.\n\n"
        "Выберите направление:"
    )
    await message.answer(text, reply_markup=get_crypto_center_main_menu_keyboard())

@router.callback_query(F.data == "back_to_crypto_center_main")
async def back_to_crypto_center_main_menu(call: CallbackQuery):
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

# --- РАЗДЕЛ "АНАЛИТИКА ОТ AI" ---

@router.callback_query(F.data == "crypto_center_guides")
async def handle_guides_menu(call: CallbackQuery):
    text = "<b>🤖 Аналитика от AI</b>\n\nВыберите категорию:"
    await call.message.edit_text(text, reply_markup=get_crypto_center_guides_menu_keyboard())
    await call.answer()

# --- ПОДРАЗДЕЛ AIRDROPS (AI) ---

@router.callback_query(F.data == "guides_airdrops")
async def handle_airdrops_list(call: CallbackQuery, crypto_center_service: CryptoCenterService, redis_client: redis.Redis):
    await call.message.edit_text("⏳ AI анализирует Airdrop-возможности...")
    all_airdrops = await crypto_center_service.generate_airdrop_alpha()

    if not all_airdrops:
        await call.message.edit_text("😕 AI не смог сгенерировать список. Попробуйте позже.", reply_markup=get_crypto_center_guides_menu_keyboard())
        await call.answer()
        return

    text = "<b>💧 Охота за Airdrop'ами (AI)</b>\n\nВыберите проект, чтобы увидеть чеклист:"
    user_id = call.from_user.id
    airdrops_with_progress = []
    for airdrop in all_airdrops:
        progress = await crypto_center_service.get_user_progress(user_id, airdrop['id'], all_airdrops)
        total_tasks = len(airdrop.get('tasks', []))
        progress_text = f"✅ {len(progress)}/{total_tasks}"
        airdrops_with_progress.append({
            "name": airdrop['name'], "id": airdrop['id'], "progress_text": progress_text
        })
    keyboard = await get_airdrops_list_keyboard(airdrops_with_progress)
    await call.message.edit_text(text + AI_DISCLAIMER, reply_markup=keyboard)
    await call.answer()


@router.callback_query(F.data.startswith("airdrop_details_"))
async def show_airdrop_details(call: CallbackQuery, crypto_center_service: CryptoCenterService, redis_client: redis.Redis):
    airdrop_id = call.data.split("_")[2]
    all_airdrops = await crypto_center_service.generate_airdrop_alpha() # Получаем свежие данные
    airdrop = crypto_center_service.get_airdrop_by_id(airdrop_id, all_airdrops)

    if not airdrop:
        await call.answer("❌ Проект не найден. Возможно, он уже не актуален.", show_alert=True)
        return

    user_progress = await crypto_center_service.get_user_progress(call.from_user.id, airdrop_id, all_airdrops)
    keyboard = await get_airdrop_details_keyboard(airdrop, user_progress)
    text = (
        f"<b>Проект: {airdrop['name']}</b> ({airdrop.get('status', 'N/A')})\n\n"
        f"{airdrop['description']}\n\n"
        f"<b>Чеклист для получения Airdrop:</b>"
    )
    await call.message.edit_text(text + AI_DISCLAIMER, reply_markup=keyboard, disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data.startswith("toggle_task_"))
async def toggle_task(call: CallbackQuery, crypto_center_service: CryptoCenterService, redis_client: redis.Redis):
    try:
        _, airdrop_id, task_index_str = call.data.split("_")
        task_index = int(task_index_str)
    except (ValueError, IndexError):
        await call.answer("❌ Ошибка данных.", show_alert=True)
        return

    all_airdrops = await crypto_center_service.generate_airdrop_alpha()
    airdrop = crypto_center_service.get_airdrop_by_id(airdrop_id, all_airdrops)
    if not airdrop or task_index >= len(airdrop.get('tasks', [])):
        await call.answer("❌ Задача или проект не найдены.", show_alert=True)
        return

    await crypto_center_service.toggle_task_status(call.from_user.id, airdrop_id, task_index)
    user_progress = await crypto_center_service.get_user_progress(call.from_user.id, airdrop_id, all_airdrops)
    new_keyboard = await get_airdrop_details_keyboard(airdrop, user_progress)
    await call.message.edit_reply_markup(reply_markup=new_keyboard)
    await call.answer("Статус задачи обновлен!")


@router.callback_query(F.data == "back_to_airdrops_list")
async def back_to_airdrops_list(call: CallbackQuery, crypto_center_service: CryptoCenterService, redis_client: redis.Redis):
    await handle_airdrops_list(call, crypto_center_service, redis_client)

# --- ПОДРАЗДЕЛ MINING SIGNALS (AI) ---

@router.callback_query(F.data == "guides_mining")
async def handle_mining_signals_list(call: CallbackQuery, crypto_center_service: CryptoCenterService):
    await call.message.edit_text("⏳ AI анализирует майнинг-сигналы...")
    signals = await crypto_center_service.generate_mining_alpha()
    
    if not signals:
        text = "<b>⛏️ Сигналы для майнеров (AI)</b>\n\n😕 AI не смог сгенерировать список. Попробуйте позже."
    else:
        text = "<b>⛏️ Сигналы для майнеров (AI)</b>\n"
        for signal in signals:
            text += (
                f"\n➖➖➖➖➖➖➖➖➖➖\n"
                f"<b>{signal.get('name', 'N/A')}</b> (Статус: {signal.get('status', 'N/A')})\n"
                f"<i>{signal.get('description', '')}</i>\n"
                f"<b>Алгоритм:</b> <code>{signal.get('algorithm', 'N/A')}</code>\n"
                f"<b>Оборудование:</b> {signal.get('hardware', 'N/A')}\n"
                f"<a href='{signal.get('guide_url', '#')}'>Подробный гайд</a>"
            )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к выбору аналитики", callback_data="crypto_center_guides")
    await call.message.edit_text(text + AI_DISCLAIMER, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    await call.answer()
