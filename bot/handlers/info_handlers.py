import asyncio
import logging
import re
from typing import Union

from aiogram import Bot, F, Router
from aiogram.enums import ContentType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.keyboards.keyboards import (get_main_menu_keyboard,
                                     get_price_keyboard,
                                     get_quiz_keyboard)
from bot.services.asic_service import AsicService
from bot.services.market_data_service import MarketDataService
from bot.services.news_service import NewsService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.services.admin_service import AdminService
from bot.utils.helpers import (get_message_and_chat_id, sanitize_html,
                               show_main_menu)
from bot.utils.plotting import generate_fng_image
from bot.utils.states import PriceInquiry, ProfitCalculator

router = Router()
logger = logging.getLogger(__name__)


# --- УНИВЕРСАЛЬНЫЙ МЕТОД ОТВЕТА ---
async def safe_edit_or_send(call: CallbackQuery, text: str, markup, delete_photo: bool = True):
    """
    Безопасно редактирует сообщение, если это текст,
    или удаляет и отправляет новое, если это медиа.
    """
    try:
        if call.message.content_type == ContentType.TEXT:
            await call.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        else:
            if delete_photo:
                await call.message.delete()
            await call.message.answer(text, reply_markup=markup, disable_web_page_preview=True)
    except TelegramBadRequest as e:
        logger.error(f"Error editing or sending message: {e}")
        # Если редактирование не удалось, отправляем новое сообщение
        await call.message.answer(text, reply_markup=markup, disable_web_page_preview=True)


async def send_price_info(message: Message, query: str, price_service: PriceService):
    coin = await price_service.get_crypto_price(query)
    
    if not coin:
        await message.edit_text(
            f"❌ Не удалось найти информацию по '{sanitize_html(query)}'.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    change = coin.price_change_24h or 0
    emoji = "📈" if change >= 0 else "📉"
    text = (f"<b>{coin.name} ({coin.symbol})</b>\n"
            f"💹 Курс: <b>${coin.price:,.4f}</b>\n"
            f"{emoji} 24ч: <b>{change:.2f}%</b>\n")
    if coin.algorithm:
        text += f"⚙️ Алгоритм: <code>{coin.algorithm}</code>"
    
    await message.edit_text(text, reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "menu_asics")
@router.message(F.text == "⚙️ Топ ASIC")
async def handle_asics_menu(update: Union[CallbackQuery, Message], asic_service: AsicService, admin_service: AdminService):
    await admin_service.track_command_usage("⚙️ Топ ASIC")
    
    if isinstance(update, CallbackQuery):
        message = update.message
        await safe_edit_or_send(update, "⏳ Загружаю актуальный список...", None, delete_photo=False)
    else:
        message = await update.answer("⏳ Загружаю актуальный список...")

    asics = await asic_service.get_profitable_asics()
    
    if not asics:
        text = "❌ Не удалось получить список ASIC-майнеров. Попробуйте позже."
    else:
        text = "🏆 <b>Топ-10 доходных ASIC:</b>\n\n"
        for miner in asics[:10]:
            text += (f"<b>{sanitize_html(miner.name)}</b>\n  Доход: <b>${miner.profitability:.2f}/день</b>"
                     f"{f' | {miner.algorithm}' if miner.algorithm else ''}"
                     f"{f' | {miner.power}W' if miner.power else ''}\n")
    
    await message.edit_text(text, reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "menu_price")
@router.message(F.text == "💹 Курс")
async def handle_price_menu(update: Union[CallbackQuery, Message], state: FSMContext, admin_service: AdminService):
    await admin_service.track_command_usage("💹 Курс")
    
    text = "Курс какой монеты вас интересует?"
    markup = get_price_keyboard()
    
    if isinstance(update, CallbackQuery):
        await safe_edit_or_send(update, text, markup)
    else:
        await update.answer(text, reply_markup=markup)
    
    await state.clear()


@router.callback_query(F.data == "menu_news")
@router.message(F.text == "📰 Новости")
async def handle_news_menu(update: Union[CallbackQuery, Message], news_service: NewsService, admin_service: AdminService):
    await admin_service.track_command_usage("📰 Новости")

    if isinstance(update, CallbackQuery):
        await safe_edit_or_send(update, "⏳ Загружаю новости...", None, delete_photo=False)
        message_to_edit = update.message
    else:
        message_to_edit = await update.answer("⏳ Загружаю новости...")

    news = await news_service.fetch_latest_news()
    if not news:
        await message_to_edit.edit_text("Не удалось загрузить новости.", reply_markup=get_main_menu_keyboard())
        return
        
    text = "📰 <b>Последние крипто-новости:</b>\n\n" + "\n\n".join(
        [f"🔹 <a href=\"{n['link']}\">{n['title']}</a>" for n in news])
        
    await message_to_edit.edit_text(text, disable_web_page_preview=True, reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "menu_fear_greed")
@router.message(F.text == "😱 Индекс Страха")
async def handle_fear_greed_menu(update: Union[CallbackQuery, Message], market_data_service: MarketDataService, admin_service: AdminService):
    await admin_service.track_command_usage("😱 Индекс Страха")
    message, _ = await get_message_and_chat_id(update)
    
    if isinstance(update, CallbackQuery):
        try:
            await update.message.delete()
        except TelegramBadRequest:
            pass

    temp_message = await message.answer("⏳ Получаю индекс и рисую график...")

    index = await market_data_service.get_fear_and_greed_index()
    if not index:
        await temp_message.edit_text("Не удалось получить индекс.", reply_markup=get_main_menu_keyboard())
        return

    value = int(index.get('value', 50))
    classification = index.get('value_classification', 'Neutral')
    
    loop = asyncio.get_running_loop()
    image_bytes = await loop.run_in_executor(None, generate_fng_image, value, classification)
    caption = f"😱 <b>Индекс страха и жадности: {value} - {classification}</b>"

    await temp_message.delete()
    await message.answer_photo(BufferedInputFile(image_bytes, "fng.png"), caption=caption, reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "menu_halving")
@router.message(F.text == "⏳ Халвинг")
async def handle_halving_menu(update: Union[CallbackQuery, Message], market_data_service: MarketDataService, admin_service: AdminService):
    await admin_service.track_command_usage("⏳ Халвинг")
    text = await market_data_service.get_halving_info()
    markup = get_main_menu_keyboard()

    if isinstance(update, CallbackQuery):
        await safe_edit_or_send(update, text, markup)
    else:
        await update.answer(text, reply_markup=markup)


@router.callback_query(F.data == "menu_btc_status")
@router.message(F.text == "📡 Статус BTC")
async def handle_btc_status_menu(update: Union[CallbackQuery, Message], market_data_service: MarketDataService, admin_service: AdminService):
    await admin_service.track_command_usage("📡 Статус BTC")
    text = await market_data_service.get_btc_network_status()
    markup = get_main_menu_keyboard()
    
    if isinstance(update, CallbackQuery):
        await safe_edit_or_send(update, text, markup)
    else:
        await update.answer(text, reply_markup=markup)

@router.callback_query(F.data.startswith("price_"))
async def handle_price_callback(call: CallbackQuery, state: FSMContext, price_service: PriceService, admin_service: AdminService):
    query = call.data.split('_', 1)[1]
    
    if query == "other":
        await call.message.edit_text("Введите тикер монеты (напр. Aleo):")
        await state.set_state(PriceInquiry.waiting_for_ticker)
    else:
        await admin_service.track_command_usage(f"Курс: {query.upper()}")
        await call.message.edit_text(f"⏳ Получаю курс для {query.upper()}...")
        await send_price_info(call.message, query, price_service)


@router.message(PriceInquiry.waiting_for_ticker)
async def process_ticker_input(message: Message, state: FSMContext, price_service: PriceService, admin_service: AdminService):
    await admin_service.track_command_usage("Курс: Другая монета")
    await state.clear()
    temp_msg = await message.answer("⏳ Получаю курс...")
    await send_price_info(temp_msg, message.text, price_service)


@router.callback_query(F.data == "menu_calculator")
@router.message(F.text == "⛏️ Калькулятор")
async def handle_calculator_menu(update: Union[CallbackQuery, Message], state: FSMContext, admin_service: AdminService):
    await admin_service.track_command_usage("⛏️ Калькулятор")
    text = "💡 Введите стоимость электроэнергии в <b>рублях</b> за кВт/ч:"
    
    if isinstance(update, CallbackQuery):
        await safe_edit_or_send(update, text, None)
    else:
        await update.answer(text)
        
    await state.clear()
    await state.set_state(ProfitCalculator.waiting_for_electricity_cost)


@router.message(ProfitCalculator.waiting_for_electricity_cost)
async def process_electricity_cost(message: Message, state: FSMContext, market_data_service: MarketDataService, asic_service: AsicService):
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
        await message.answer("\n".join(res), reply_markup=get_main_menu_keyboard())
    except (ValueError, TypeError):
        await message.answer("❌ Неверный формат. Введите число (напр. 4.5).")
    
    await state.clear()


@router.callback_query(F.data == "menu_quiz")
@router.message(F.text == "🧠 Викторина")
async def handle_quiz_menu(update: Union[CallbackQuery, Message], quiz_service: QuizService, admin_service: AdminService):
    await admin_service.track_command_usage("🧠 Викторина")
    message, _ = await get_message_and_chat_id(update)
    
    if isinstance(update, CallbackQuery):
        try:
            await update.message.delete()
        except TelegramBadRequest:
            pass

    temp_message = await message.answer("⏳ Генерирую вопрос...")

    quiz = await quiz_service.generate_quiz_question()
    if not quiz:
        await temp_message.edit_text("😕 Не удалось сгенерировать вопрос.", reply_markup=get_main_menu_keyboard())
        return
    
    await temp_message.delete()
    
    await message.answer_poll(
        question=quiz['question'], options=quiz['options'], type='quiz',
        correct_option_id=quiz['correct_option_index'], is_anonymous=False,
        reply_markup=get_quiz_keyboard()
    )


@router.message(
    F.content_type == ContentType.TEXT,
    lambda message: not any(entity.type == "bot_command" for entity in message.entities or [])
)
async def handle_arbitrary_text(message: Message, price_service: PriceService, bot: Bot):
    if message.chat.type != "private":
        return

    logger.info(f"User sent text '{message.text}' in private, processing as price request.")
    temp_msg = await message.answer("⏳ Получаю курс...")
    await send_price_info(temp_msg, message.text, price_service)