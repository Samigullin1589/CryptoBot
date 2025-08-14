# =================================================================================
# Файл: bot/handlers/public/price_handler.py (ПРОДАКШН-ВЕРСЯ 2025 - РЕФАКТОРИНГ)
# Описание: Обработчик для сценария получения цены.
# ИСПРАВЛЕНИЕ: Архитектура полностью переработана для устойчивости к отсутствию
#              монеты в CoinListService, но наличию цены у провайдера.
# =================================================================================
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards.keyboards import get_back_to_main_menu_keyboard
from bot.keyboards.info_keyboards import get_price_keyboard
from bot.keyboards.callback_factories import PriceCallback, MenuCallback
from bot.states.info_states import PriceInquiryState
from bot.utils.dependencies import Deps
from bot.utils.formatters import format_price_info
from bot.utils.models import Coin

router = Router(name="price_handler_router")
logger = logging.getLogger(__name__)

@router.callback_query(MenuCallback.filter(F.action == "price"))
async def handle_price_menu_start(call: CallbackQuery, state: FSMContext, **kwargs):
    """Точка входа в раздел курсов, вызывается из главного меню."""
    text = "Курс какой монеты вас интересует? Выберите из популярных или отправьте тикер/название."
    await call.message.edit_text(text, reply_markup=get_price_keyboard())
    await state.set_state(PriceInquiryState.waiting_for_ticker)
    await call.answer()

async def show_price_for_coin(target: Message | CallbackQuery, query: str, deps: Deps):
    """
    Универсальная функция для получения и отображения цены.
    Новая логика: сначала запрашивает цену, затем детали.
    """
    if isinstance(target, CallbackQuery):
        message = target.message
        await target.answer(f"⏳ Получаю курс для {query.upper()}...")
    else:
        message = await target.answer("⏳ Ищу монету и получаю курс...")

    # Шаг 1: Сначала пытаемся получить цену. PriceService использует CoinAliasService внутри.
    prices = await deps.price_service.get_prices([query])
    # CoinAliasService преобразует query в coin_id, который и будет ключом
    resolved_id = await deps.coin_alias_service.resolve_alias(query)
    price_value = prices.get(resolved_id)

    # Шаг 2: Если цена найдена, формируем ответ.
    if price_value is not None:
        # Пытаемся получить полные данные для красивого ответа.
        coin_details = await deps.coin_list_service.find_coin_by_query(resolved_id)
        
        if not coin_details:
            # Если полных данных нет (как в случае с Aleo), создаем заглушку.
            logger.warning(f"Цена для '{resolved_id}' найдена, но детали в CoinListService отсутствуют. Формирую ответ на основе запроса.")
            coin_details = Coin(id=resolved_id, symbol=query.upper(), name=query.capitalize())
        
        response_text = format_price_info(coin_details, {"price": price_value})
        await message.edit_text(response_text, reply_markup=get_back_to_main_menu_keyboard())

    # Шаг 3: Если цена не найдена, используем AI для поиска информации.
    else:
        logger.warning(f"Цена для '{query}' (resolved to '{resolved_id}') не найдена. Запрашиваю AI для объяснения.")
        ai_explanation = await deps.ai_content_service.explain_unlisted_coin(query)
        
        response_text = f"❌ Не удалось найти информацию по '{query}'.\n\n"
        if "недоступен" not in ai_explanation:
            response_text += f"<b>Справка от AI-Консультанта:</b>\n{ai_explanation}"
            
        await message.edit_text(response_text, reply_markup=get_back_to_main_menu_keyboard(), disable_web_page_preview=True)


@router.callback_query(PriceCallback.filter(F.action == "show"))
async def handle_price_button_callback(call: CallbackQuery, callback_data: PriceCallback, state: FSMContext, deps: Deps):
    """Обрабатывает нажатие на кнопку с конкретной монетой."""
    await state.clear()
    await show_price_for_coin(call, callback_data.coin_id, deps)

@router.message(PriceInquiryState.waiting_for_ticker)
async def process_ticker_input_from_user(message: Message, state: FSMContext, deps: Deps):
    """Обрабатывает текстовый ввод тикера или названия от пользователя."""
    await state.clear()
    query = message.text.strip()
    await show_price_for_coin(message, query, deps)