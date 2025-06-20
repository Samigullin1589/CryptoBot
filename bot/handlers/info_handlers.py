import asyncio
import logging
import re
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.services.asic_service import AsicService
from bot.services.price_service import PriceService
from bot.services.news_service import NewsService
from bot.services.market_data_service import MarketDataService
from bot.services.quiz_service import QuizService
from bot.utils.helpers import sanitize_html
from bot.utils.plotting import generate_fng_image # Импортируем из нового файла
from bot.utils.keyboards import (get_main_menu_keyboard, get_price_keyboard,
                                 get_quiz_keyboard)
from bot.utils.states import PriceInquiry, ProfitCalculator # Импортируем состояния

router = Router()
logger = logging.getLogger(__name__)

async def show_main_menu(message: Message):
    """Отправляет или редактирует сообщение, показывая главное меню."""
    try:
        # Пытаемся отредактировать, если это возможно (исходное сообщение от колбэка)
        await message.edit_text("Главное меню:", reply_markup=get_main_menu_keyboard())
    except (TypeError, AttributeError, Exception):
         # Если отредактировать не удалось, отправляем новое сообщение
         await message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "menu_asics")
async def handle_asics_menu(call: CallbackQuery, asic_service: AsicService):
    await call.answer("Загружаю...", show_alert=False)
    await call.message.edit_text("⏳ Загружаю актуальный список...")
    asics = await asic_service.get_profitable_asics()
    text = "🏆 <b>Топ-10 доходных ASIC:</b>\n\n"
    for miner in asics[:10]:
        text += (f"<b>{sanitize_html(miner.name)}</b>\n  Доход: <b>${miner.profitability:.2f}/день</b>"
                 f"{f' | {miner.algorithm}' if miner.algorithm else ''}"
                 f"{f' | {miner.power}W' if miner.power else ''}\n")
    await call.message.edit_text(text, reply_markup=get_main_menu_keyboard())

@router.callback_query(F.data == "menu_price")
async def handle_price_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Курс какой монеты вас интересует?", reply_markup=get_price_keyboard())
    await call.answer()

async def send_price_info(message: Message, query: str, price_service: PriceService, asic_service: AsicService):
    """Формирует и отправляет сообщение с информацией о цене и ASICах."""
    coin = await price_service.get_crypto_price(query)
    if not coin:
        await message.answer(f"❌ Не удалось найти информацию по '{sanitize_html(query)}'.")
        return
        
    change = coin.price_change_24h or 0
    emoji = "📈" if change >= 0 else "📉"
    text = (f"<b>{coin.name} ({coin.symbol})</b>\n"
            f"💹 Курс: <b>${coin.price:,.4f}</b>\n"
            f"{emoji} 24ч: <b>{change:.2f}%</b>\n")
            
    if coin.algorithm:
        text += f"⚙️ Алгоритм: <code>{coin.algorithm}</code>\n"
        relevant_asics = await asic_service.find_asics_by_algorithm(coin.algorithm)
        if relevant_asics:
            text += f"\n⚙️ <b>Рекомендуемое оборудование под {coin.algorithm}:</b>\n"
            for asic in relevant_asics[:3]:
                text += f"  • <b>{sanitize_html(asic.name)}</b>: ${asic.profitability:.2f}/день\n"
    await message.answer(text)

@router.callback_query(F.data.startswith("price_"))
async def handle_price_callback(call: CallbackQuery, state: FSMContext, price_service: PriceService, asic_service: AsicService):
    action = call.data.split('_')[1]
    
    if action == "other":
        await state.set_state(PriceInquiry.waiting_for_ticker)
        await call.message.edit_text("Введите тикер монеты (напр. Aleo):")
    else:
        # Если была нажата кнопка с конкретной монетой, удаляем клавиатуру и отправляем инфо
        await call.message.delete()
        await send_price_info(call.message, action, price_service, asic_service)
        await show_main_menu(call.message)
        
    await call.answer()

@router.message(PriceInquiry.waiting_for_ticker)
async def process_ticker_input(message: Message, state: FSMContext, price_service: PriceService, asic_service: AsicService):
    await state.clear()
    await send_price_info(message, message.text, price_service, asic_service)
    await show_main_menu(message)


@router.callback_query(F.data == "menu_news")
async def handle_news_menu(call: CallbackQuery, news_service: NewsService):
    await call.answer("Загружаю...", show_alert=False)
    await call.message.edit_text("⏳ Загружаю новости...")
    news = await news_service.fetch_latest_news()
    if not news:
        await call.message.edit_text("Не удалось загрузить новости.", reply_markup=get_main_menu_keyboard())
        return
    text = "📰 <b>Последние крипто-новости:</b>\n\n" + "\n\n".join(
        [f"🔹 <a href=\"{n['link']}\">{n['title']}</a>" for n in news])
    await call.message.edit_text(text, disable_web_page_preview=True, reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "menu_fear_greed")
async def handle_fear_greed_menu(call: CallbackQuery, market_data_service: MarketDataService):
    await call.answer("Рисую график...", show_alert=False)
    await call.message.edit_text("⏳ Получаю индекс и рисую график...")
    index = await market_data_service.get_fear_and_greed_index()
    if not index:
        await call.message.edit_text("Не удалось получить индекс.", reply_markup=get_main_menu_keyboard())
        return

    value, classification = int(index['value']), index['value_classification']
    
    # Выносим блокирующий код в executor
    loop = asyncio.get_running_loop()
    image_bytes = await loop.run_in_executor(
        None, generate_fng_image, value, classification
    )
    
    caption = f"😱 <b>Индекс страха и жадности: {value} - {classification}</b>"
    
    await call.message.delete()
    await call.message.answer_photo(BufferedInputFile(image_bytes, "fng.png"), caption=caption)
    await show_main_menu(call.message)


@router.callback_query(F.data.in_({"menu_halving", "menu_btc_status"}))
async def handle_info_callbacks(call: CallbackQuery, market_data_service: MarketDataService):
    await call.answer("Обрабатываю...", show_alert=False)
    await call.message.edit_text("⏳ Обрабатываю запрос...")
    text = "❌ Ошибка."
    if call.data == "menu_halving":
        text = await market_data_service.get_halving_info()
    elif call.data == "menu_btc_status":
        text = await market_data_service.get_btc_network_status()

    await call.message.edit_text(text, reply_markup=get_main_menu_keyboard())

# --- FSM для калькулятора ---
@router.callback_query(F.data == "menu_calculator")
async def handle_calculator_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(ProfitCalculator.waiting_for_electricity_cost)
    await call.message.edit_text("💡 Введите стоимость электроэнергии в <b>рублях</b> за кВт/ч:")
    await call.answer()

@router.message(ProfitCalculator.waiting_for_electricity_cost)
async def process_electricity_cost(message: Message, state: FSMContext, market_data_service: MarketDataService, asic_service: AsicService):
    await state.clear()
    try:
        cost_rub = float(message.text.replace(',', '.'))
        rate_usd_rub = await market_data_service.get_usd_rub_rate()
        cost_usd = cost_rub / rate_usd_rub
        asics = await asic_service.get_profitable_asics()
        res = [f"💰 <b>Расчет профита (розетка {cost_rub:.2f} ₽/кВтч)</b>\n"]
        for asic in asics[:10]:
            if asic.power:
                profit = asic.profitability - ((asic.power / 1000) * 24 * cost_usd)
                res.append(f"<b>{sanitize_html(asic.name)}</b>: ${profit:.2f}/день")
        await message.answer("\n".join(res))
        await show_main_menu(message)
    except (ValueError, TypeError):
        await message.answer("❌ Неверный формат. Введите число (напр. 4.5).")
        await show_main_menu(message)

# --- Викторина ---
@router.callback_query(F.data == "menu_quiz")
async def handle_quiz_menu(call: CallbackQuery, quiz_service: QuizService):
    await call.answer("Генерирую...", show_alert=False)
    await call.message.edit_text("⏳ Генерирую вопрос...")
    quiz = await quiz_service.generate_quiz_question()
    if not quiz:
        await call.message.edit_text("😕 Не удалось сгенерировать вопрос.", reply_markup=get_main_menu_keyboard())
        return
    await call.message.delete()
    await call.message.answer_poll(
        question=quiz['question'], options=quiz['options'], type='quiz',
        correct_option_id=quiz['correct_option_index'], is_anonymous=False,
        reply_markup=get_quiz_keyboard()
    )


@router.message(F.text)
async def handle_text_message(message: Message, price_service: PriceService, asic_service: AsicService):
    """Обрабатывает произвольный текст как запрос цены."""
    if message.text in ["💹 Курс", "⚙️ Топ ASIC", "⛏️ Калькулятор", "📰 Новости", "😱 Индекс Страха", "⏳ Халвинг", "📡 Статус BTC", "🧠 Викторина"]:
         return
         
    logger.info(f"User sent text '{message.text}', processing as price request.", extra={'user_id': message.from_user.id})
    await send_price_info(message, message.text, price_service, asic_service)
