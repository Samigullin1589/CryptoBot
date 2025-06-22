import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards.keyboards import get_back_to_menu_keyboard, get_price_keyboard, get_quiz_keyboard
from bot.utils.states import UserState
from bot.services.price_service import PriceService
from bot.services.asic_service import AsicService
from bot.services.news_service import NewsService
from bot.services.market_data_service import MarketDataService
from bot.services.quiz_service import QuizService

router = Router()
logger = logging.getLogger(__name__)

# --- Обработчик меню Курсов ---
@router.callback_query(F.data == "menu_price")
async def handle_prices_menu(query: CallbackQuery):
    await query.message.edit_text(
        "Выберите популярную монету или введите свою.",
        reply_markup=get_price_keyboard()
    )
    await query.answer()

# --- Обработчик для кнопок популярных тикеров ---
@router.callback_query(F.data.startswith("price_"))
async def handle_popular_ticker_price(query: CallbackQuery, price_service: PriceService, state: FSMContext):
    await state.clear()
    ticker = query.data.split("_")[1]

    # Если нажата кнопка "Другая монета"
    if ticker == 'other':
        await state.set_state(UserState.awaiting_ticker)
        await query.message.edit_text(
            "Введите тикер криптовалюты (например, BTC или ETH):",
            reply_markup=get_back_to_menu_keyboard()
        )
        await query.answer()
        return

    # Для обычных тикеров
    await query.answer(f"Запрашиваю цену для {ticker}...")
    price = await price_service.get_price(ticker)

    if price is not None:
        response_text = f"✅ Текущий курс {ticker}/USD: **${price:,.4f}**"
    else:
        response_text = f"❌ Не удалось найти информацию по тикеру {ticker}."

    await query.message.edit_text(response_text, reply_markup=get_price_keyboard())

# --- Обработчик для ручного ввода тикера ---
@router.message(UserState.awaiting_ticker)
async def handle_ticker_input(message: Message, state: FSMContext, price_service: PriceService):
    ticker = message.text.upper()
    price = await price_service.get_price(ticker)

    if price is not None:
        response_text = f"✅ Текущий курс {ticker}/USD: **${price:,.4f}**"
    else:
        response_text = f"❌ Не удалось найти информацию по тикеру {ticker}. Попробуйте другой."

    await message.answer(response_text, reply_markup=get_price_keyboard())
    await state.clear()

# --- Обработка ASIC-майнеров ---
@router.callback_query(F.data == "menu_asics")
async def handle_asics_menu(query: CallbackQuery, asic_service: AsicService):
    await query.answer("Загружаю данные по ASIC-майнерам...")
    top_asics = await asic_service.get_profitable_asics()
    if not top_asics:
        await query.message.edit_text("Не удалось получить данные о майнерах. Попробуйте позже.", reply_markup=get_back_to_menu_keyboard())
        return

    response_text = "Топ-10 самых прибыльных ASIC-майнеров на данный момент:\n\n"
    for i, asic in enumerate(top_asics[:10], 1):
        response_text += f"{i}. **{asic.name}**\n"
        response_text += f"   - Прибыльность: ${asic.profitability:,.2f}/день\n"
        response_text += f"   - Алгоритм: {asic.algorithm}\n"
        response_text += f"   - Потребление: {asic.power}W\n\n"

    await query.message.edit_text(response_text, reply_markup=get_back_to_menu_keyboard(), disable_web_page_preview=True)

# --- Обработка новостей ---
@router.callback_query(F.data == "menu_news")
async def handle_news_menu(query: CallbackQuery, news_service: NewsService):
    await query.answer("Ищу последние новости...")
    latest_news = await news_service.get_latest_news()
    if not latest_news:
        await query.message.edit_text("Не удалось найти свежие новости. Попробуйте позже.", reply_markup=get_back_to_menu_keyboard())
        return

    response_text = "Последние новости из мира криптовалют:\n\n"
    for i, item in enumerate(latest_news[:10], 1):
        response_text += f"{i}. <a href='{item['link']}'>{item['title']}</a>\n"

    await query.message.edit_text(response_text, reply_markup=get_back_to_menu_keyboard(), disable_web_page_preview=True)

# --- Обработка индекса страха и жадности ---
@router.callback_query(F.data == "menu_fear_greed")
async def handle_fng_menu(query: CallbackQuery, market_data_service: MarketDataService):
    await query.answer("Получаю индекс...")
    fng_data = await market_data_service.get_fear_and_greed_index()
    if not fng_data:
        await query.message.edit_text("Не удалось получить данные об индексе. Попробуйте позже.", reply_markup=get_back_to_menu_keyboard())
        return

    value = int(fng_data.get('value', 0))
    value_classification = fng_data.get('value_classification', 'N/A')
    response_text = f"Текущее значение индекса страха и жадности: **{value} - {value_classification}**"
    await query.message.edit_text(response_text, reply_markup=get_back_to_menu_keyboard())

# --- Обработка викторины ---
@router.callback_query(F.data == "menu_quiz")
async def handle_quiz_menu(query: CallbackQuery, quiz_service: QuizService, bot: Bot):
    await query.answer("Готовлю вопрос...")
    quiz_question = await quiz_service.get_quiz_question()
    if not quiz_question:
        await query.message.edit_text("Не удалось сгенерировать вопрос для викторины. Возможно, сервис перегружен. Попробуйте позже.", reply_markup=get_back_to_menu_keyboard())
        return

    # Удаляем старое сообщение с меню, чтобы не было путаницы
    await query.message.delete()
    await bot.send_poll(
        chat_id=query.from_user.id,
        question=quiz_question.question,
        options=quiz_question.options,
        type='quiz',
        correct_option_id=quiz_question.correct_option_index,
        is_anonymous=False,
        # Используем новую клавиатуру для викторины
        reply_markup=get_quiz_keyboard()
    )

# --- ЗАГЛУШКИ ДЛЯ НОВЫХ РАЗДЕЛОВ ---
@router.callback_query(F.data.in_({"menu_calculator", "menu_halving", "menu_btc_status"}))
async def handle_coming_soon(query: CallbackQuery):
    await query.answer("Этот раздел находится в разработке.", show_alert=True)