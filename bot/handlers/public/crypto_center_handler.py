# ===============================================================
# Файл: bot/handlers/public/crypto_center_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - УЛУЧШЕННАЯ)
# Описание: "Тонкий" хэндлер для Крипто-Центра, разделенный на
# логические блоки для максимальной читаемости и поддержки.
# ===============================================================
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.services.crypto_center_service import CryptoCenterService
from bot.states.crypto_center_states import CryptoCenterStates
from bot.keyboards.crypto_center_keyboards import *
from bot.utils.formatters import *
from bot.texts.public_texts import CRYPTO_CENTER_TEXTS

router = Router(name="crypto_center_handler")
logger = logging.getLogger(__name__)

# --- Точка входа и навигация по главному меню ---

@router.callback_query(F.data == "nav:crypto_center")
async def crypto_center_entry(call: CallbackQuery, state: FSMContext):
    """Точка входа в Крипто-Центр."""
    await state.set_state(CryptoCenterStates.main_menu)
    await call.message.edit_text(
        CRYPTO_CENTER_TEXTS['main_menu'],
        reply_markup=get_crypto_center_main_menu_keyboard()
    )
    await call.answer()

@router.callback_query(F.data == "cc_nav:main_menu")
async def crypto_center_back_to_main(call: CallbackQuery, state: FSMContext):
    """Возврат в главное меню Крипто-Центра."""
    await crypto_center_entry(call, state)

@router.callback_query(F.data == "cc_nav:guides_menu")
async def crypto_center_guides_menu(call: CallbackQuery, state: FSMContext):
    """Отображает меню гайдов."""
    await state.set_state(CryptoCenterStates.viewing_guides_menu)
    await call.message.edit_text(
        CRYPTO_CENTER_TEXTS['guides_menu'],
        reply_markup=get_crypto_center_guides_menu_keyboard()
    )
    await call.answer()

# --- Лента новостей и майнинг-сигналы ---

@router.callback_query(F.data == "cc_nav:feed")
async def crypto_center_feed(call: CallbackQuery, state: FSMContext, crypto_center_service: CryptoCenterService):
    """Отображает ленту новостей с AI-саммари."""
    await state.set_state(CryptoCenterStates.viewing_feed)
    await call.message.edit_text("⏳ AI анализирует свежие новости...")
    feed_items = await crypto_center_service.get_live_feed_with_summary()
    text = format_crypto_feed(feed_items)
    await call.message.edit_text(text, reply_markup=get_live_feed_keyboard(), disable_web_page_preview=True)
    await call.answer()

@router.callback_query(F.data == "cc_nav:mining_signals")
async def crypto_center_mining_signals(call: CallbackQuery, state: FSMContext, crypto_center_service: CryptoCenterService):
    """Отображает майнинг-сигналы."""
    await state.set_state(CryptoCenterStates.viewing_mining_signals)
    await call.message.edit_text("⏳ AI анализирует майнинг-сигналы...")
    signals = await crypto_center_service.generate_mining_alpha()
    text = format_mining_signals(signals)
    await call.message.edit_text(text, reply_markup=get_back_to_cc_menu_keyboard('guides_menu'), disable_web_page_preview=True)
    await call.answer()

# --- Список Airdrop'ов и детальный просмотр ---

@router.callback_query(AirdropListPage.filter())
async def airdrops_list_handler(call: CallbackQuery, callback_data: AirdropListPage, state: FSMContext, crypto_center_service: CryptoCenterService):
    """Отображает список Airdrop'ов с пагинацией."""
    await state.set_state(CryptoCenterStates.viewing_airdrops_list)
    await call.message.edit_text("⏳ AI ищет Airdrop-возможности...")
    
    airdrops = await crypto_center_service.generate_airdrop_alpha() # Получаем полный список
    
    if not airdrops:
        await call.message.edit_text(
            "😕 AI не нашел актуальных Airdrop-возможностей.",
            reply_markup=get_back_to_cc_menu_keyboard('guides_menu')
        )
        return
    
    # Пагинация
    page = callback_data.page
    page_size = 5
    total_pages = (len(airdrops) + page_size - 1) // page_size
    paginated_airdrops = airdrops[(page-1)*page_size : page*page_size]
    
    await state.update_data(all_airdrops=airdrops) # Кэшируем полный список в FSM
    
    await call.message.edit_text(
        CRYPTO_CENTER_TEXTS['airdrops_list'],
        reply_markup=get_airdrops_list_keyboard(paginated_airdrops, page, total_pages)
    )
    await call.answer()

@router.callback_query(AirdropDetails.filter())
async def airdrop_details_handler(call: CallbackQuery, callback_data: AirdropDetails, state: FSMContext, crypto_center_service: CryptoCenterService):
    """Отображает детальную информацию об Airdrop."""
    fsm_data = await state.get_data()
    all_airdrops = fsm_data.get('all_airdrops', [])
    airdrop_id = callback_data.airdrop_id
    
    airdrop = next((a for a in all_airdrops if a['id'] == airdrop_id), None)
    
    if not airdrop:
        await call.answer("❌ Проект не найден. Возможно, он уже не актуален.", show_alert=True)
        return
    
    await state.set_state(CryptoCenterStates.viewing_airdrop_details)
    user_progress = await crypto_center_service.get_user_progress(call.from_user.id, airdrop_id)
    text = format_airdrop_details(airdrop)
    keyboard = get_airdrop_details_keyboard(airdrop, user_progress)
    await call.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    await call.answer()

# --- Обработка действий пользователя (чеклист) ---

@router.callback_query(AirdropTask.filter(), CryptoCenterStates.viewing_airdrop_details)
async def toggle_task_handler(call: CallbackQuery, callback_data: AirdropTask, state: FSMContext, crypto_center_service: CryptoCenterService):
    """Отмечает/снимает задачу в чеклисте."""
    airdrop_id = callback_data.airdrop_id
    task_index = callback_data.task_index

    await crypto_center_service.toggle_task_status(call.from_user.id, airdrop_id, task_index)
    
    # Обновляем клавиатуру без перерисовки всего сообщения
    fsm_data = await state.get_data()
    all_airdrops = fsm_data.get('all_airdrops', [])
    airdrop = next((a for a in all_airdrops if a['id'] == airdrop_id), None)

    if not airdrop:
        await call.answer("❌ Ошибка обновления.", show_alert=True)
        return

    user_progress = await crypto_center_service.get_user_progress(call.from_user.id, airdrop_id)
    new_keyboard = get_airdrop_details_keyboard(airdrop, user_progress)
    
    try:
        await call.message.edit_reply_markup(reply_markup=new_keyboard)
        await call.answer("Статус задачи обновлен!")
    except TelegramBadRequest as e:
        logger.warning(f"Could not edit reply markup for toggle_task: {e}")
        await call.answer("Статус обновлен, но не удалось обновить кнопки.")
