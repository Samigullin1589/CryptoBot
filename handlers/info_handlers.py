# handlers/info_handlers.py
import io
import logging
import matplotlib.pyplot as plt
from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, ForceReply, Message

from services.api_client import ApiClient
from utils.helpers import sanitize_html
from utils.keyboards import (get_main_menu_keyboard, get_price_keyboard,
                             get_quiz_keyboard)

router = Router()
logger = logging.getLogger(__name__)

# ИЗМЕНЕНИЕ: Список текстов кнопок, которые нужно игнорировать
MENU_BUTTON_TEXTS = [
    "💹 Курс", "⚙️ Топ ASIC", "⛏️ Калькулятор", "📰 Новости",
    "😱 Индекс Страха", "⏳ Халвинг", "📡 Статус BTC", "🧠 Викторина"
]

async def show_main_menu(message: Message):
    # Эта функция была в предыдущих версиях, но для полноты картины оставим ее здесь.
    # Она может быть вызвана из других модулей.
    await message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "menu_asics")
async def handle_asics_menu(call: CallbackQuery, api_client: ApiClient):
    await call.message.edit_text("⏳ Загружаю актуальный список...")
    asics = await api_client.get_profitable_asics()
    if not asics:
        await call.message.edit_text("❌ Не удалось загрузить список ASIC. Попробуйте позже.", reply_markup=get_main_menu_keyboard())
        await call.answer()
        return
        
    text = "🏆 <b>Топ-10 доходных ASIC:</b>\n\n"
    for miner in asics[:10]:
        text += (f"<b>{sanitize_html(miner.name)}</b>\n  Доход: <b>${miner.profitability:.2f}/день</b>"
                 f"{f' | {miner.algorithm}' if miner.algorithm else ''}"
                 f"{f' | {miner.power}W' if miner.power else ''}\n")
    await call.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    await call.answer()

@router.callback_query(F.data == "menu_price")
async def handle_price_menu(call: CallbackQuery):
    await call.message.edit_text("Курс какой монеты вас интересует?", reply_markup=get_price_keyboard())
    await call.answer()

async def send_price_info(message: Message, query: str, api_client: ApiClient):
    coin = await api_client.get_crypto_price(query)
    if not coin:
        await message.answer(f"❌ Не удалось найти информацию по '{query}'.")
        return
    change = coin.price_change_24h or 0
    emoji = "📈" if change >= 0 else "📉"
    text = (f"<b>{coin.name} ({coin.symbol})</b>\n"
            f"💹 Курс: <b>${coin.price:,.4f}</b>\n"
            f"{emoji} 24ч: <b>{change:.2f}%</b>\n")
    if coin.algorithm:
        text += f"⚙️ Алгоритм: <code>{coin.algorithm}</code>\n"
        logger.info(f"Searching for ASICs with algorithm: {coin.algorithm}")
        all_asics = await api_client.get_profitable_asics()
        normalized_coin_algo = coin.algorithm.lower().replace('-', '').replace('_', '')
        relevant_asics = [
            asic for asic in all_asics 
            if asic.algorithm and normalized_coin_algo in asic.algorithm.lower().replace('-', '').replace('_', '')
        ]
        if relevant_asics:
            sorted_relevant_asics = sorted(relevant_asics, key=lambda x: x.profitability, reverse=True)
            text += f"\n⚙️ <b>Рекомендуемое оборудование под {coin.algorithm}:</b>\n"
            for asic in sorted_relevant_asics[:3]:
                text += f"  • <b>{sanitize_html(asic.name)}</b>: ${asic.profitability:.2f}/день\n"
    await message.answer(text)

@router.callback_query(F.data.startswith("price_"))
async def handle_price_callback(call: CallbackQuery, api_client: ApiClient):
    action = call.data.split('_')[1]
    await call.message.delete()
    if action == "other":
        await call.message.answer("Введите тикер монеты (напр. Aleo):", reply_markup=ForceReply())
    else:
        await send_price_info(call.message, action, api_client)
        await show_main_menu(call.message)
    await call.answer()


@router.callback_query(F.data == "menu_news")
async def handle_news_menu(call: CallbackQuery, api_client: ApiClient):
    await call.message.edit_text("⏳ Загружаю новости...")
    news = await api_client.fetch_latest_news()
    if not news:
        await call.message.edit_text("Не удалось загрузить новости.", reply_markup=get_main_menu_keyboard())
        return
    text = "📰 <b>Последние крипто-новости:</b>\n\n" + "\n\n".join(
        [f"🔹 <a href=\"{n['link']}\">{n['title']}</a>" for n in news])
    await call.message.edit_text(text, disable_web_page_preview=True, reply_markup=get_main_menu_keyboard())
    await call.answer()

@router.callback_query(F.data == "menu_fear_greed")
async def handle_fear_greed_menu(call: CallbackQuery, api_client: ApiClient):
    await call.message.edit_text("⏳ Получаю индекс...")
    index = await api_client.get_fear_and_greed_index()
    if not index:
        await call.message.edit_text("Не удалось получить индекс.", reply_markup=get_main_menu_keyboard())
        return

    value, classification = int(index['value']), index['value_classification']
    plt.style.use('dark_background'); fig, ax = plt.subplots(figsize=(8, 4.5), subplot_kw={'projection': 'polar'})
    ax.set_yticklabels([]); ax.set_xticklabels([]); ax.grid(False); ax.spines['polar'].set_visible(False); ax.set_ylim(0, 1)
    colors = ['#d94b4b', '#e88452', '#ece36a', '#b7d968', '#73c269']
    for i in range(100): ax.barh(1, 0.0314, left=3.14-(i*0.0314), height=0.3, color=colors[min(4,int(i/25))])
    angle = 3.14 - (value * 0.0314)
    ax.annotate('', xy=(angle, 1), xytext=(0,0), arrowprops=dict(facecolor='white', shrink=0.05, width=4, headwidth=10))
    fig.text(0.5,0.5,f"{value}",ha='center',va='center',fontsize=48,color='white',weight='bold')
    fig.text(0.5,0.35,classification,ha='center',va='center',fontsize=20,color='white')
    
    buf = io.BytesIO(); plt.savefig(buf, format='png', dpi=150, transparent=True); buf.seek(0); plt.close(fig)
    caption = f"😱 <b>Индекс страха и жадности: {value} - {classification}</b>"
    
    await call.message.delete()
    await call.message.answer_photo(BufferedInputFile(buf.read(), "fng.png"), caption=caption)
    await show_main_menu(call.message)
    await call.answer()

@router.callback_query(F.data.in_({"menu_halving", "menu_btc_status", "menu_calculator"}))
async def handle_info_callbacks(call: CallbackQuery, api_client: ApiClient):
    await call.message.edit_text("⏳ Обрабатываю запрос...")
    text = "❌ Ошибка."
    if call.data == "menu_halving": text = await api_client.get_halving_info()
    elif call.data == "menu_btc_status": text = await api_client.get_btc_network_status()
    elif call.data == "menu_calculator":
        await call.message.edit_text("💡 Введите стоимость электроэнергии в <b>рублях</b> за кВт/ч:", reply_markup=ForceReply())
        await call.answer()
        return
    await call.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    await call.answer()

@router.callback_query(F.data == "menu_quiz")
async def handle_quiz_menu(call: CallbackQuery, api_client: ApiClient):
    await call.message.edit_text("⏳ Генерирую вопрос...")
    quiz = await api_client.generate_quiz_question()
    if not quiz:
        await call.message.edit_text("😕 Не удалось сгенерировать вопрос.", reply_markup=get_main_menu_keyboard())
        return
    await call.message.delete()
    await call.message.answer_poll(
        question=quiz['question'], options=quiz['options'], type='quiz',
        correct_option_id=quiz['correct_option_index'], is_anonymous=False,
        reply_markup=get_quiz_keyboard()
    )
    await call.answer()


@router.message(F.text)
async def handle_text_message(message: Message, api_client: ApiClient):
    # ИЗМЕНЕНИЕ: Добавлена проверка, чтобы игнорировать текст кнопок
    if message.text and message.text.strip() in MENU_BUTTON_TEXTS:
        logger.info(f"Ignoring menu button text: {message.text}")
        return

    if message.reply_to_message and message.reply_to_message.from_user.id == message.bot.id:
        if "Введите тикер" in message.reply_to_message.text:
            await message.reply_to_message.delete()
            await send_price_info(message, message.text, api_client)
            await show_main_menu(message)
        elif "стоимость электроэнергии" in message.reply_to_message.text:
            await message.reply_to_message.delete()
            try:
                cost_rub = float(message.text.replace(',', '.'))
                rate_usd_rub = await api_client.get_usd_rub_rate()
                cost_usd = cost_rub / rate_usd_rub
                asics = await api_client.get_profitable_asics()
                res = [f"💰 <b>Расчет профита (розетка {cost_rub:.2f} ₽/кВтч)</b>\n"]
                for asic in asics[:10]:
                    if asic.power:
                        profit = asic.profitability - ((asic.power / 1000) * 24 * cost_usd)
                        res.append(f"<b>{sanitize_html(asic.name)}</b>: ${profit:.2f}/день")
                await message.answer("\n".join(res))
                await show_main_menu(message)
            except (ValueError, TypeError):
                await message.answer("❌ Неверный формат. Введите число (напр. 4.5).")
    else:
        # Если это не ответ, считаем, что пользователь хочет узнать курс
        await send_price_info(message, message.text, api_client)