import asyncio
import logging
import re
from typing import Union
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message, MessageEntity
from aiogram.enums import ContentType
from aiogram.exceptions import TelegramBadRequest

from bot.services.asic_service import AsicService
from bot.services.market_data_service import MarketDataService
from bot.services.news_service import NewsService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.utils.helpers import sanitize_html, get_message_and_chat_id, show_main_menu
from bot.keyboards.keyboards import (get_main_menu_keyboard, get_price_keyboard, get_quiz_keyboard)
from bot.utils.plotting import generate_fng_image
from bot.utils.states import PriceInquiry, ProfitCalculator

router = Router()
logger = logging.getLogger(__name__)

async def send_price_info(message: Message, query: str, price_service: PriceService, asic_service: AsicService):  
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

@router.callback_query(F.data == "menu_asics")
@router.message(F.text == "⚙️ Топ ASIC")
async def handle_asics_menu(update: Union[CallbackQuery, Message], asic_service: AsicService):
    message, _ = await get_message_and_chat_id(update)
    
    try:
        if isinstance(update, CallbackQuery):
            await message.edit_text("⏳ Загружаю актуальный список...")
        else:
            await message.answer("⏳ Загружаю актуальный список...")
    except TelegramBadRequest:
        logger.warning("Message not modified, skipping initial edit.")

    asics = await asic_service.get_profitable_asics()
    
    if not asics:
        text = "❌ Не удалось получить список ASIC-майнеров. Попробуйте позже."
    else:
        text = "🏆 <b>Топ-10 доходных ASIC из резервного списка:</b>\n\n"
        for miner in asics[:10]:
            text += (f"<b>{sanitize_html(miner.name)}</b>\n  Доход: <b>${miner.profitability:.2f}/день</b>"
                     f"{f' | {miner.algorithm}' if miner.algorithm else ''}"
                     f"{f' | {miner.power}W' if miner.power else ''}\n")
    
    try:
        if isinstance(update, CallbackQuery):
            await message.edit_text(text, reply_markup=get_main_menu_keyboard())
        else:
            await message.answer(text, reply_markup=get_main_menu_keyboard())
    except TelegramBadRequest as e:
        logger.error(f"Failed to edit message in handle_asics_menu: {e}")

@router.callback_query(F.data == "menu_price")
@router.message(F.text == "💹 Курс")
async def handle_price_menu(update: Union[CallbackQuery, Message], state: FSMContext):
    message, _ = await get_message_and_chat_id(update)
    await state.clear()
    await message.edit_text("Курс какой монеты вас интересует?", reply_markup=get_price_keyboard())

@router.callback_query(F.data == "menu_news")
@router.message(F.text == "📰 Новости")
async def handle_news_menu(update: Union[CallbackQuery, Message], news_service: NewsService):
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
    message, _ = await get_message_and_chat_id(update)
    await message.edit_text("⏳ Получаю индекс и рисую график...")
    index = await market_data_service.get_fear_and_greed_index()
    if not index:
        await message.edit_text("Не удалось получить индекс.", reply_markup=get_main_menu_keyboard())
        return

    value, classification = int(index['value']), index['value_classification']
    loop = asyncio.get_running_loop()
    image_bytes = await loop.run_in_executor(None, generate_fng_image, value, classification)
    caption = f"😱 <b>Индекс страха и жадности: {value} - {classification}</b>"

    await message.delete()
    await message.answer_photo(BufferedInputFile(image_bytes, "fng.png"), caption=caption)
    await show_main_menu(message)

@router.callback_query(F.data == "menu_halving")
@router.message(F.text == "⏳ Халвинг")
async def handle_halving_menu(update: Union[CallbackQuery, Message], market_data_service: MarketDataService):
    message, _ = await get_message_and_chat_id(update)
    await message.edit_text("⏳ Обрабатываю запрос...")
    text = await market_data_service.get_halving_info()
    await message.edit_text(text, reply_markup=get_main_menu_keyboard())

@router.callback_query(F.data == "menu_btc_status")
@router.message(F.text == "📡 Статус BTC")
async def handle_btc_status_menu(update: Union[CallbackQuery, Message], market_data_service: MarketDataService):
    message, _ = await get_message_and_chat_id(update)
    await message.edit_text("⏳ Обрабатываю запрос...")
    text = await market_data_service.get_btc_network_status()
    await message.edit_text(text, reply_markup=get_main_menu_keyboard())

@router.callback_query(F.data.startswith("price_"))
async def handle_price_callback(call: CallbackQuery, state: FSMContext, price_service: PriceService, asic_service: AsicService):
    action = call.data.split('_')[1]
    
    if action == "other":
        await state.set_state(PriceInquiry.waiting_for_ticker)
        await call.message.edit_text("Введите тикер монеты (напр. Aleo):")
    else:
        await call.message.delete()
        await send_price_info(call.message, action, price_service, asic_service)
        await show_main_menu(call.message)

@router.message(PriceInquiry.waiting_for_ticker)
async def process_ticker_input(message: Message, state: FSMContext, price_service: PriceService, asic_service: AsicService):
    await state.clear()
    await send_price_info(message, message.text, price_service, asic_service)
    await show_main_menu(message)

@router.callback_query(F.data == "menu_calculator")
@router.message(F.text == "⛏️ Калькулятор")
async def handle_calculator_menu(update: Union[CallbackQuery, Message], state: FSMContext):
    message, _ = await get_message_and_chat_id(update)
    await state.set_state(ProfitCalculator.waiting_for_electricity_cost)
    await message.edit_text("💡 Введите стоимость электроэнергии в <b>рублях</b> за кВт/ч:")

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
        await message.answer("\n".join(res))
    except (ValueError, TypeError):
        await message.answer("❌ Неверный формат. Введите число (напр. 4.5).")
    
    await state.clear()
    await show_main_menu(message)

@router.callback_query(F.data == "menu_quiz")
@router.message(F.text == "🧠 Викторина")
async def handle_quiz_menu(update: Union[CallbackQuery, Message], quiz_service: QuizService):
    message, _ = await get_message_and_chat_id(update)
    
    if isinstance(update, CallbackQuery):
        await message.delete()
        message_to_process = await message.answer("⏳ Генерирую вопрос...")
    else:
        message_to_process = await message.answer("⏳ Генерирую вопрос...")

    quiz = await quiz_service.generate_quiz_question()
    if not quiz:
        await message_to_process.edit_text("😕 Не удалось сгенерировать вопрос.", reply_markup=get_main_menu_keyboard())
        return
    
    await message_to_process.delete()
    await message.answer_poll(
        question=quiz['question'], options=quiz['options'], type='quiz',
        correct_option_id=quiz['correct_option_index'], is_anonymous=False,
        reply_markup=get_quiz_keyboard()
    )

# ИСПРАВЛЕНИЕ: Это правильный способ игнорировать команды в текстовом обработчике
@router.message(
    F.content_type == ContentType.TEXT,
    # Этот lambda-фильтр проверяет, что в сообщении нет сущностей типа "команда"
    lambda message: not any(entity.type == "bot_command" for entity in message.entities or [])
)
async def handle_arbitrary_text(message: Message, price_service: PriceService, asic_service: AsicService, bot: Bot):
    if message.chat.type == "private":
        logger.info(f"User sent text '{message.text}' in private, processing as price request.")
        await send_price_info(message, message.text, price_service, asic_service)
        return

    bot_info = await bot.get_me()
    if bot_info.username and f"@{bot_info.username}" in message.text:
        text_to_process = re.sub(f'@{bot_info.username}', '', message.text, flags=re.IGNORECASE).strip()
        if text_to_process:
            logger.info(f"User mentioned bot in group with text '{text_to_process}', processing as price request.")
            await send_price_info(message, text_to_process, price_service, asic_service)