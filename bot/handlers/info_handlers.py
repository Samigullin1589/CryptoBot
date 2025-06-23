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
                                     get_price_keyboard, get_quiz_keyboard, get_after_action_keyboard)
from bot.services.asic_service import AsicService
from bot.services.market_data_service import MarketDataService
from bot.services.news_service import NewsService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.utils.helpers import (get_message_and_chat_id, sanitize_html,
                               show_main_menu)
from bot.utils.plotting import generate_fng_image
from bot.utils.states import PriceInquiry, ProfitCalculator

router = Router()
logger = logging.getLogger(__name__)

async def send_price_info(message: Message, query: str, price_service: PriceService, asic_service: AsicService):
    """
    Готовит и отправляет сообщение с информацией о курсе и клавиатурой.
    """
    coin = await price_service.get_crypto_price(query)
    
    if not coin:
        await message.edit_text(
            f"❌ Не удалось найти информацию по '{sanitize_html(query)}'.",
            reply_markup=get_after_action_keyboard()
        )
        return

    change = coin.price_change_24h or 0
    emoji = "📈" if change >= 0 else "📉"
    text = (f"<b>{coin.name} ({coin.symbol})</b>\n"
            f"💹 Курс: <b>${coin.price:,.4f}</b>\n"
            f"{emoji} 24ч: <b>{change:.2f}%</b>\n")

    if coin.algorithm:
        text += f"⚙️ Алгоритм: <code>{coin.algorithm}</code>"
    
    await message.edit_text(text, reply_markup=get_after_action_keyboard())


@router.callback_query(F.data == "menu_asics")
@router.message(F.text == "⚙️ Топ ASIC")
async def handle_asics_menu(update: Union[CallbackQuery, Message], asic_service: AsicService):
    """
    Обрабатывает запрос на получение списка лучших ASIC-майнеров.
    """
    message, _ = await get_message_and_chat_id(update)
    
    if isinstance(update, CallbackQuery):
        await message.edit_text("⏳ Загружаю актуальный список...")
    else:
        # В случае текстовой команды, отправляем новое сообщение
        message = await message.answer("⏳ Загружаю актуальный список...")

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
async def handle_price_menu(update: Union[CallbackQuery, Message], state: FSMContext):
    """
    Отображает меню для запроса цены криптовалюты.
    """
    message, _ = await get_message_and_chat_id(update)
    await state.clear()
    await message.edit_text("Курс какой монеты вас интересует?", reply_markup=get_price_keyboard())


@router.callback_query(F.data == "menu_news")
@router.message(F.text == "📰 Новости")
async def handle_news_menu(update: Union[CallbackQuery, Message], news_service: NewsService):
    """
    Отправляет последние новости из RSS-лент.
    """
    message, _ = await get_message_and_chat_id(update)
    await message.edit_text("⏳ Загружаю новости...")
    news = await news_service.fetch_latest_news()
    if not news:
        await message.edit_text("Не удалось загрузить новости.", reply_markup=get_main_menu_keyboard())
        return
        
    text = "📰 <b>Последние крипто-новости:</b>\n\n" + "\n\n".join(
        [f"🔹 <a href=\"{n['link']}\">{n['title']}</a>" for n in news])
        
    await message.edit_text(text, disable_web_page_preview=True, reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "menu_fear_greed")
@router.message(F.text == "😱 Индекс Страха")
async def handle_fear_greed_menu(update: Union[CallbackQuery, Message], market_data_service: MarketDataService):
    """
    Отправляет график Индекса Страха и Жадности.
    """
    message, _ = await get_message_and_chat_id(update)
    temp_message = await message.answer("⏳ Получаю индекс и рисую график...")
    try:
        if isinstance(update, CallbackQuery):
            await update.message.delete()
    except TelegramBadRequest:
        pass # Игнорируем ошибку, если сообщение уже удалено

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
    await message.answer_photo(BufferedInputFile(image_bytes, "fng.png"), caption=caption, reply_markup=get_after_action_keyboard())


@router.callback_query(F.data == "menu_halving")
@router.message(F.text == "⏳ Халвинг")
async def handle_halving_menu(update: Union[CallbackQuery, Message], market_data_service: MarketDataService):
    """
    Отправляет информацию о дате халвинга Bitcoin.
    """
    message, _ = await get_message_and_chat_id(update)
    text = await market_data_service.get_halving_info()
    await message.answer(text, reply_markup=get_after_action_keyboard())


@router.callback_query(F.data == "menu_btc_status")
@router.message(F.text == "📡 Статус BTC")
async def handle_btc_status_menu(update: Union[CallbackQuery, Message], market_data_service: MarketDataService):
    """
    Отправляет информацию о статусе сети Bitcoin.
    """
    message, _ = await get_message_and_chat_id(update)
    text = await market_data_service.get_btc_network_status()
    await message.answer(text, reply_markup=get_after_action_keyboard())


@router.callback_query(F.data.startswith("price_"))
async def handle_price_callback(call: CallbackQuery, state: FSMContext, price_service: PriceService, asic_service: AsicService):
    """
    Обрабатывает выбор монеты из кнопок и редактирует сообщение.
    """
    query = call.data.split('_', 1)[1]
    
    if query == "other":
        await state.set_state(PriceInquiry.waiting_for_ticker)
        await call.message.edit_text("Введите тикер монеты (напр. Aleo):")
    else:
        await call.message.edit_text(f"⏳ Получаю курс для {query.upper()}...")
        text = await send_price_info(call.message, query, price_service, asic_service)


@router.message(PriceInquiry.waiting_for_ticker)
async def process_ticker_input(message: Message, state: FSMContext, price_service: PriceService, asic_service: AsicService):
    """
    Обрабатывает введенный пользователем тикер.
    """
    await state.clear()
    temp_msg = await message.answer("⏳ Получаю курс...")
    # Так как send_price_info теперь возвращает текст, мы должны его отправить
    text_to_send = await send_price_info(temp_msg, message.text, price_service, asic_service)
    # Теперь редактируем временное сообщение
    await temp_msg.edit_text(text_to_send, reply_markup=get_after_action_keyboard())


@router.callback_query(F.data == "menu_calculator")
@router.message(F.text == "⛏️ Калькулятор")
async def handle_calculator_menu(update: Union[CallbackQuery, Message], state: FSMContext):
    """
    Запускает сценарий калькулятора доходности.
    """
    message, _ = await get_message_and_chat_id(update)
    await state.set_state(ProfitCalculator.waiting_for_electricity_cost)
    await message.edit_text("💡 Введите стоимость электроэнергии в <b>рублях</b> за кВт/ч:")


@router.message(ProfitCalculator.waiting_for_electricity_cost)
async def process_electricity_cost(message: Message, state: FSMContext, market_data_service: MarketDataService, asic_service: AsicService):
    """
    Обрабатывает введенную стоимость и выдает расчет.
    """
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
    except (ValueError, TypeError):
        await message.answer("❌ Неверный формат. Введите число (напр. 4.5).")
    
    await state.clear()
    await show_main_menu(message)


@router.callback_query(F.data == "menu_quiz")
@router.message(F.text == "🧠 Викторина")
async def handle_quiz_menu(update: Union[CallbackQuery, Message], quiz_service: QuizService):
    """
    Запускает викторину.
    """
    message, _ = await get_message_and_chat_id(update)
    
    temp_message = await message.answer("⏳ Генерирую вопрос...")
    if isinstance(update, CallbackQuery):
        try:
            await update.message.delete()
        except TelegramBadRequest:
            pass

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
async def handle_arbitrary_text(message: Message, price_service: PriceService, asic_service: AsicService, bot: Bot):
    """
    Обрабатывает произвольный текст как запрос цены.
    """
    if message.chat.type == "private":
        logger.info(f"User sent text '{message.text}' in private, processing as price request.")
        # Используем новую функцию, которая сразу отправляет сообщение с клавиатурой
        await send_price_info(message, message.text, price_service, asic_service)
        return

    bot_info = await bot.get_me()
    if bot_info.username and f"@{bot_info.username}" in message.text:
        text_to_process = re.sub(f'@{bot_info.username}', '', message.text, flags=re.IGNORECASE).strip()
        if text_to_process:
            logger.info(f"User mentioned bot in group with text '{text_to_process}', processing as price request.")
            await send_price_info(message, text_to_process, price_service, asic_service)