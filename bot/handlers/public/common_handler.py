# ===============================================================
# Файл: bot/handlers/public/common_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Обрабатывает общие команды, такие как /start, /help,
# а также онбординг для новых пользователей и обработку
# произвольного текста (запросы цен, AI-консультант).
# ===============================================================
import logging

from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatType

from bot.config.settings import settings
from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.utils.text_utils import sanitize_html
from bot.keyboards.onboarding_keyboards import get_onboarding_start_keyboard, get_onboarding_step_keyboard
from bot.services.user_service import UserService
from bot.services.ai_content_service import AIContentService
from bot.services.price_service import PriceService
# --- ИСПРАВЛЕНИЕ: Импортируем из правильного, нового файла ---
from bot.states.common_states import CommonStates
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from bot.utils.formatters import format_price_info

# Инициализация роутера
router = Router(name=__name__)
logger = logging.getLogger(__name__)

# --- Текстовые константы ---
# В идеале, их стоит вынести в отдельный файл bot/texts/public_texts.py
HELP_TEXT = """
👋 <b>Добро пожаловать в CryptoBot!</b>

Ваш персональный ассистент в мире криптовалют и майнинга. Я помогу вам быть в курсе самых важных событий и показателей рынка.

📌 <b>Основные возможности:</b>

💹 <b>Актуальные курсы:</b> Узнавайте цены на Bitcoin, Ethereum и другие криптовалюты в реальном времени.
⚙️ <b>Топ ASIC-майнеров:</b> Получайте свежий список самого доходного оборудования, доступного на рынке.
⛏️ <b>Калькулятор доходности:</b> Рассчитайте чистую прибыль любого ASIC с учетом стоимости вашей электроэнергии.
📰 <b>Крипто-новости:</b> Будьте в курсе последних событий с нашими новостными дайджестами из ведущих источников.
😱 <b>Индекс Страха и Жадности:</b> Оцените настроения рынка с помощью наглядного графика, чтобы принимать взвешенные решения.
🧠 <b>Крипто-викторина:</b> Проверьте свои знания в увлекательной викторине и узнайте что-то новое!

💎 <b>Игра "Виртуальный Майнинг"</b>
Запускайте виртуальные ASIC'и, приглашайте друзей, управляйте тарифами на электроэнергию и накапливайте монеты! Обменивайте заработанные монеты на <b>реальные скидки</b> у наших партнеров!

⌨️ <b>Список доступных команд:</b>
<code>/start</code> - Перезапустить бота и вернуться в главное меню.
<code>/help</code> - Показать это справочное сообщение.

<i>Также, вы можете просто отправить мне название или тикер монеты (например, btc или эфир), чтобы узнать ее курс.</i>
"""

ONBOARDING_TEXTS = {
    1: "<b>Шаг 1: Курсы валют 💹</b>\n\nПервая и главная функция — актуальные курсы. Вы можете просто отправить мне тикер (например, <code>btc</code> или <code>эфир</code>) или воспользоваться кнопкой в меню.",
    2: "<b>Шаг 2: Все для майнеров ⚙️</b>\n\nВ разделе 'Топ ASIC' вы всегда найдете свежий список самого доходного оборудования. А 'Калькулятор' поможет рассчитать чистую прибыль с учетом вашей розетки.",
    3: "<b>Шаг 3: Крипто-Центр 💎</b>\n\nЭто наша главная фишка! Здесь наш AI-аналитик 24/7 ищет для вас самые горячие возможности для заработка: от Airdrop'ов до майнинг-сигналов."
}

# --- ОБРАБОТЧИКИ КОМАНД ---

@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, command: CommandObject, user_service: UserService):
    """
    Обработчик команды /start. Регистрирует пользователя, обрабатывает реферальную
    ссылку и запускает онбординг для новых пользователей.
    """
    await state.clear()
    user_id = message.from_user.id
    
    is_new_user = await user_service.is_new_user(user_id)
    if is_new_user:
        await user_service.register_new_user(user_id)
        
        # Обработка реферальной ссылки, если она есть
        if command.args:
            await user_service.process_referral(
                referrer_id_str=command.args, 
                new_user_id=user_id, 
                new_user_username=message.from_user.username
            )

        text = (f"👋 <b>Привет, {message.from_user.full_name}!</b>\n\n"
                "Я ваш персональный ассистент в мире криптовалют и майнинга. "
                "Давайте я быстро покажу, что я умею!")
        await message.answer(text, reply_markup=get_onboarding_start_keyboard())
    else:
        await message.answer(
            "👋 С возвращением! Выберите одну из опций в меню ниже.",
            reply_markup=get_main_menu_keyboard()
        )

@router.message(Command("help"))
async def handle_help(message: Message):
    """Отправляет справочное сообщение по команде /help."""
    await message.answer(HELP_TEXT, disable_web_page_preview=True)

# --- УПРАВЛЕНИЕ ОНБОРДИНГОМ ЧЕРЕЗ FSM ---

@router.callback_query(F.data.startswith("onboarding:"))
async def handle_onboarding_navigation(call: CallbackQuery, state: FSMContext):
    """Единый обработчик для навигации по онбордингу."""
    action = call.data.split(":")[1]

    if action in ["skip", "finish"]:
        text = ("Отлично, теперь вы знаете все основы!\n\n"
                "Вот ваше главное меню. Если забудете, что я умею, просто вызовите команду /help.")
        await call.message.delete()
        await call.message.answer(text, reply_markup=get_main_menu_keyboard())
        await state.clear()
        return

    try:
        step = int(action.split("_")[1])
        await state.update_data(onboarding_step=step)
        await state.set_state(CommonStates.onboarding)
        
        text = ONBOARDING_TEXTS.get(step, "Неизвестный шаг.")
        keyboard = get_onboarding_step_keyboard(step)
        await call.message.edit_text(text, reply_markup=keyboard)
    except (ValueError, IndexError):
        logger.error(f"Invalid onboarding action: {action}")
        await call.answer("Произошла ошибка навигации.", show_alert=True)

# --- ОБРАБОТКА ПРОИЗВОЛЬНОГО ТЕКСТА ---

@router.message(F.content_type == "text", ~F.text.startswith('/'))
async def handle_arbitrary_text(message: Message, state: FSMContext, bot: Bot, user_service: UserService, price_service: PriceService, ai_content_service: AIContentService):
    """
    Обрабатывает произвольный текстовый ввод:
    1. Пытается распознать тикер монеты.
    2. Если не получилось и это ЛС/ответ боту/упоминание, отвечает с помощью AI.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_text = message.text.strip()

    # Уровень 1: Поиск цены
    price_info = await price_service.get_crypto_price(user_text)
    if price_info:
        text = format_price_info(price_info)
        await message.answer(text)
        return

    # Уровень 2: AI-Консультант
    bot_info = await bot.get_me()
    is_mention = any(
        entity.type == 'mention' and message.text[entity.offset:entity.offset+entity.length] == f"@{bot_info.username}"
        for entity in message.entities or []
    )
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id

    if message.chat.type == ChatType.PRIVATE or is_mention or is_reply_to_bot:
        temp_msg = await message.reply("🤖 Думаю...")
        
        history = await user_service.get_conversation_history(user_id, chat_id)
        ai_answer = await ai_content_service.get_consultant_answer(user_text, history)
        await user_service.add_to_conversation_history(user_id, chat_id, user_text, ai_answer)
        
        response_text = (f"<b>Ваш вопрос:</b>\n<i>«{sanitize_html(user_text)}»</i>\n\n"
                         f"<b>Ответ AI-Консультанта:</b>\n{ai_answer}")
        
        await temp_msg.edit_text(response_text, disable_web_page_preview=True)
