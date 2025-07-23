# ===============================================================
# Файл: bot/handlers/info_handlers.py (ОКОНЧАТЕЛЬНЫЙ FIX)
# Описание: Исправлена ошибка в викторине (AttributeError).
# Удален старый, конфликтующий код калькулятора.
# ===============================================================
import asyncio
import logging
from typing import Union
from datetime import datetime, timezone
import redis.asyncio as redis

from aiogram import Bot, F, Router
from aiogram.enums import ContentType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.keyboards.keyboards import (get_main_menu_keyboard,
                                     get_price_keyboard,
                                     get_quiz_keyboard)
# Импортируем все нужные сервисы
from bot.services.asic_service import AsicService
from bot.services.user_service import UserService
from bot.services.market_data_service import MarketDataService
from bot.services.news_service import NewsService
from bot.services.price_service import PriceService
from bot.services.quiz_service import QuizService
from bot.services.admin_service import AdminService
from bot.utils.helpers import (get_message_and_chat_id, sanitize_html,
                                     show_main_menu)
from bot.utils.plotting import generate_fng_image
from bot.utils.states import PriceInquiry

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
    finally:
        # В любом случае отвечаем на колбэк, чтобы убрать "часики"
        await call.answer()


# --- "АЛЬФА" РЕФАКТОРИНГ: ОТДЕЛЯЕМ ЛОГИКУ ПОЛУЧЕНИЯ ДАННЫХ ОТ ОТПРАВКИ ---
async def format_price_info_text(query: str, price_service: PriceService) -> str:
    """
    Получает данные о монете и форматирует их в готовый для отправки текст.
    Возвращает либо информацию о цене, либо сообщение об ошибке.
    """
    coin = await price_service.get_crypto_price(query)
    
    if not coin:
        return f"❌ К сожалению, не удалось найти информацию по тикеру '{sanitize_html(query)}'.\n\nПожалуйста, проверьте правильность написания или попробуйте другую монету."

    change = coin.price_change_24h or 0
    emoji = "📈" if change >= 0 else "📉"
    text = (f"<b>{coin.name} ({coin.symbol})</b>\n"
            f"💹 Курс: <b>${coin.price:,.4f}</b>\n"
            f"{emoji} 24ч: <b>{change:.2f}%</b>\n")
    if coin.algorithm:
        text += f"⚙️ Алгоритм: <code>{coin.algorithm}</code>"
    
    return text


@router.callback_query(F.data == "menu_asics")
@router.message(F.text == "⚙️ Топ ASIC")
async def handle_asics_menu(update: Union[CallbackQuery, Message], asic_service: AsicService, admin_service: AdminService, user_service: UserService):
    """
    ОБНОВЛЕННЫЙ обработчик для "Топ ASIC" с правильным использованием зависимостей.
    """
    await admin_service.track_command_usage("⚙️ Топ ASIC")
    
    message, chat_id = await get_message_and_chat_id(update)
    temp_message = await message.answer("⏳ Загружаю актуальный список...")
    
    if isinstance(update, CallbackQuery) and update.message.content_type != ContentType.TEXT:
        try:
            await update.message.delete()
        except TelegramBadRequest:
            pass
    
    electricity_cost = await user_service.get_user_electricity_cost(update.from_user.id, chat_id, default_cost=0.05)
    
    top_miners, last_update_time = await asic_service.get_top_asics(count=10, electricity_cost=electricity_cost)

    if not top_miners:
        text = "❌ Не удалось получить список ASIC-майнеров. Попробуйте позже."
    else:
        text_lines = [f"🏆 <b>Топ-10 доходных ASIC</b> (чистыми, при цене э/э ${electricity_cost:.4f}/кВт·ч)\n"]
        for miner in top_miners:
            line = (f"<b>{sanitize_html(miner.name)}</b>\n"
                    f"   Доход: <b>${miner.profitability:.2f}/день</b>"
                    f"{f' | {miner.algorithm}' if miner.algorithm and miner.algorithm != 'N/A' else ''}")
            text_lines.append(line)
        
        if last_update_time:
            now = datetime.now(timezone.utc)
            minutes_ago = int((now - last_update_time).total_seconds() / 60)
            text_lines.append(f"\n<i>Данные обновлены {minutes_ago} минут назад.</i>")
        
        text = "\n".join(text_lines)

    await temp_message.edit_text(text, reply_markup=get_main_menu_keyboard(), disable_web_page_preview=True)


@router.callback_query(F.data == "menu_price")
@router.message(F.text == "💹 Курс")
async def handle_price_menu(update: Union[CallbackQuery, Message], state: FSMContext, admin_service: AdminService):
    await admin_service.track_command_usage("💹 Курс")
    
    text = "Курс какой монеты вас интересует?"
    markup = get_price_keyboard()
    
    message, _ = await get_message_and_chat_id(update)
    await message.answer(text, reply_markup=markup)
    
    await state.set_state(PriceInquiry.waiting_for_ticker)


@router.callback_query(F.data == "menu_news")
@router.message(F.text == "📰 Новости")
async def handle_news_menu(update: Union[CallbackQuery, Message], news_service: NewsService, admin_service: AdminService):
    await admin_service.track_command_usage("📰 Новости")

    message_to_edit = update.message if isinstance(update, CallbackQuery) else await update.answer("⏳ Загружаю новости...")
    if isinstance(update, CallbackQuery):
        await safe_edit_or_send(update, "⏳ Загружаю новости...", None, delete_photo=False)

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
    await state.clear()
    query = call.data.split('_', 1)[1]
    
    if query == "other":
        await call.message.edit_text("Введите тикер монеты (напр. Aleo):")
        await state.set_state(PriceInquiry.waiting_for_ticker)
        await call.answer()
    else:
        await admin_service.track_command_usage(f"Курс: {query.upper()}")
        await call.message.edit_text(f"⏳ Получаю курс для {query.upper()}...")
        
        response_text = await format_price_info_text(query, price_service)
        await call.message.edit_text(response_text, reply_markup=get_main_menu_keyboard())
        await call.answer()


@router.message(PriceInquiry.waiting_for_ticker)
async def process_ticker_input(message: Message, state: FSMContext, price_service: PriceService, admin_service: AdminService):
    await admin_service.track_command_usage("Курс: Другая монета")
    await state.clear()
    temp_msg = await message.answer("⏳ Получаю курс...")
    
    response_text = await format_price_info_text(message.text, price_service)
    await temp_msg.edit_text(response_text, reply_markup=get_main_menu_keyboard())


# --- БЛОК ВИКТОРИНЫ (ИСПРАВЛЕН) ---

@router.callback_query(F.data == "menu_quiz")
@router.message(F.text == "🧠 Викторина")
async def handle_quiz_menu(update: Union[CallbackQuery, Message], quiz_service: QuizService, admin_service: AdminService):
    await admin_service.track_command_usage("🧠 Викторина")
    message, _ = await get_message_and_chat_id(update)
    
    if isinstance(update, CallbackQuery):
        try: await update.message.delete()
        except TelegramBadRequest: pass

    temp_message = await message.answer("⏳ Генерирую вопрос...")

    # --- ИСПРАВЛЕНО: Вызываем правильный метод и распаковываем результат ---
    question, options, correct_option_id = await quiz_service.get_random_question()
    
    # Проверяем, что сервис не вернул сообщение об ошибке
    if not options:
        await temp_message.edit_text(question, reply_markup=get_main_menu_keyboard())
        return
    
    await temp_message.delete()
    
    await message.answer_poll(
        question=question, 
        options=options, 
        type='quiz',
        correct_option_id=correct_option_id, 
        is_anonymous=False,
        reply_markup=get_quiz_keyboard()
    )
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
