import asyncio
import logging
from typing import Union
from datetime import datetime

import redis.asyncio as redis
from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.enums import ContentType, ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config.settings import settings
from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.services.admin_service import AdminService
from bot.utils.helpers import get_message_and_chat_id, sanitize_html
# --- НОВЫЕ ИМПОРТЫ ДЛЯ AI-КОНСУЛЬТАНТА ---
from bot.services.ai_consultant_service import AIConsultantService
from bot.services.ai_conversation_service import AIConversationService
from bot.services.price_service import PriceService


router = Router()
logger = logging.getLogger(__name__)

# --- КЛАВИАТУРЫ ДЛЯ ОНБОРДИНГА ---

def get_onboarding_start_keyboard():
    """Создает клавиатуру для начала онбординга."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Начать знакомство", callback_data="onboarding_start")
    builder.button(text="Пропустить", callback_data="onboarding_skip")
    builder.adjust(1)
    return builder.as_markup()

def get_onboarding_step_keyboard(step: int):
    """Создает клавиатуру для шагов онбординга."""
    builder = InlineKeyboardBuilder()
    if step == 1:
        builder.button(text="💹 Узнать курс BTC", callback_data="menu_price")
        builder.button(text="Далее ➡️", callback_data="onboarding_step_2")
    elif step == 2:
        builder.button(text="⚙️ Показать Топ ASIC", callback_data="menu_asics")
        builder.button(text="Далее ➡️", callback_data="onboarding_step_3")
    elif step == 3:
        builder.button(text="💎 Войти в Крипто-Центр", callback_data="menu_crypto_center")
        builder.button(text="✅ Все понятно!", callback_data="onboarding_finish")
    builder.adjust(1)
    return builder.as_markup()


# --- СУЩЕСТВУЮЩИЙ КОД ---

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

📞 <b>Поддержка и обратная связь</b>
Есть вопросы, предложения или нашли ошибку?
Свяжитесь с администратором: <a href="https://t.me/mining_sale_admin">@mining_sale_admin</a>
"""

async def handle_referral(message: Message, command: CommandObject, redis_client: redis.Redis, bot: Bot):
    """Обрабатывает запуск по реферальной ссылке."""
    referrer_id = command.args
    new_user_id = message.from_user.id

    if not referrer_id or not referrer_id.isdigit() or int(referrer_id) == new_user_id:
        return

    referrer_id = int(referrer_id)
    
    already_referred = await redis_client.sismember("referred_users", new_user_id)
    if already_referred:
        logger.info(f"User {new_user_id} tried to use referral link from {referrer_id}, but is already a referred user.")
        return

    bonus = settings.REFERRAL_BONUS_AMOUNT
    
    async with redis_client.pipeline() as pipe:
        pipe.incrbyfloat(f"user:{referrer_id}:balance", bonus)
        pipe.incrbyfloat(f"user:{referrer_id}:total_earned", bonus)
        pipe.sadd("referred_users", new_user_id)
        pipe.sadd(f"user:{referrer_id}:referrals", new_user_id)
        await pipe.execute()
    
    logger.info(f"User {new_user_id} joined via referral from {referrer_id}. Referrer received {bonus} coins.")

    try:
        await bot.send_message(
            referrer_id,
            f"🤝 Поздравляем! Ваш друг @{message.from_user.username} присоединился по вашей ссылке.\n"
            f"💰 Ваш баланс пополнен на <b>{bonus} монет</b>!"
        )
    except Exception as e:
        logger.error(f"Failed to send referral notification to user {referrer_id}: {e}")


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, command: CommandObject, redis_client: redis.Redis, bot: Bot, admin_service: AdminService):
    """
    Обработчик команды /start с онбордингом для новых пользователей.
    """
    await admin_service.track_command_usage("/start")
    await state.clear()
    
    user_id = message.from_user.id
    
    is_new_user = await redis_client.sadd("users:known", user_id)
    
    if is_new_user:
        current_timestamp = int(datetime.now().timestamp())
        await redis_client.zadd("stats:user_first_seen", {str(user_id): current_timestamp})
        logger.info(f"New user {user_id} has been registered. Starting onboarding.")
        
        text = (
            f"👋 <b>Привет, {message.from_user.full_name}!</b>\n\n"
            "Я ваш персональный ассистент в мире криптовалют и майнинга. "
            "Давайте я быстро покажу, что я умею!"
        )
        await message.answer(text, reply_markup=get_onboarding_start_keyboard())

    else:
        logger.info(f"User {user_id} started the bot.")
        await message.answer(
            "👋 С возвращением! Выберите одну из опций в меню ниже.",
            reply_markup=get_main_menu_keyboard()
        )

    if command.args:
        await handle_referral(message, command, redis_client, bot)


@router.callback_query(F.data == "onboarding_start" or F.data == "onboarding_step_1")
async def onboarding_step_1(call: CallbackQuery):
    text = (
        "<b>Шаг 1: Курсы валют 💹</b>\n\n"
        "Первая и главная функция — актуальные курсы. Вы можете просто отправить мне тикер "
        "(например, <code>btc</code> или <code>эфир</code>) или воспользоваться кнопкой в меню."
    )
    await call.message.edit_text(text, reply_markup=get_onboarding_step_keyboard(1))
    await call.answer()


@router.callback_query(F.data == "onboarding_step_2")
async def onboarding_step_2(call: CallbackQuery):
    text = (
        "<b>Шаг 2: Все для майнеров ⚙️</b>\n\n"
        "В разделе 'Топ ASIC' вы всегда найдете свежий список самого доходного оборудования. "
        "А 'Калькулятор' поможет рассчитать чистую прибыль с учетом вашей розетки."
    )
    await call.message.edit_text(text, reply_markup=get_onboarding_step_keyboard(2))
    await call.answer()


@router.callback_query(F.data == "onboarding_step_3")
async def onboarding_step_3(call: CallbackQuery):
    text = (
        "<b>Шаг 3: Крипто-Центр 💎</b>\n\n"
        "Это наша главная фишка! Здесь наш AI-аналитик 24/7 ищет для вас самые горячие "
        "возможности для заработка: от Airdrop'ов до майнинг-сигналов."
    )
    await call.message.edit_text(text, reply_markup=get_onboarding_step_keyboard(3))
    await call.answer()


@router.callback_query(F.data == "onboarding_skip" or F.data == "onboarding_finish")
async def onboarding_finish(call: CallbackQuery):
    """Завершает онбординг и показывает главное меню."""
    text = (
        "Отлично, теперь вы знаете все основы!\n\n"
        "Вот ваше главное меню. Если забудете, что я умею, просто вызовите команду /help."
    )
    await call.message.delete()
    await call.message.answer(text, reply_markup=get_main_menu_keyboard())
    await call.answer()


@router.message(Command("help"))
async def handle_help(message: Message, admin_service: AdminService):
    """Отправляет информационное сообщение по команде /help."""
    await admin_service.track_command_usage("/help")
    await message.answer(HELP_TEXT, disable_web_page_preview=True)


@router.callback_query(F.data == "back_to_main_menu")
async def handle_back_to_main(call: CallbackQuery, state: FSMContext, admin_service: AdminService):
    """
    Обработчик кнопки 'Назад в главное меню'.
    Умеет обрабатывать колбэки из текстовых сообщений, медиа и опросов.
    """
    await admin_service.track_command_usage("⬅️ Назад в меню")
    await state.clear()
    
    try:
        if call.message.content_type == ContentType.TEXT:
            await call.message.edit_text("Главное меню:", reply_markup=get_main_menu_keyboard())
        else:
            await call.message.delete()
            await call.message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())
    except TelegramBadRequest as e:
        logger.error(f"Error returning to main menu: {e}. Sending new message.")
        await call.message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())
    finally:
        await call.answer()

# --- ОБНОВЛЕННЫЙ ОБРАБОТЧИК ДЛЯ AI-КОНСУЛЬТАНТА С ТРЕХУРОВНЕВЫМ ФИЛЬТРОМ ---
@router.message(
    F.content_type == ContentType.TEXT,
    lambda message: not message.text.startswith('/')
)
async def handle_arbitrary_text(
    message: Message, 
    state: FSMContext, 
    ai_consultant_service: AIConsultantService, 
    ai_conversation_service: AIConversationService,
    price_service: PriceService, 
    admin_service: AdminService
):
    """
    Обрабатывает произвольный текстовый ввод с использованием трехуровневого фильтра.
    """
    # Фильтр 1: Базовые проверки (без AI)
    if (message.forward_from or message.forward_from_chat or 
        len(message.text.split()) < 3):
        return

    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    user_text = message.text.strip()

    # Фильтр 2: Быстрая проверка на тикер (без AI)
    coin = await price_service.get_crypto_price(user_text)
    if coin:
        await admin_service.track_command_usage(f"Курс (текстом): {coin.symbol}")
        change = coin.price_change_24h or 0
        emoji = "📈" if change >= 0 else "📉"
        text = (f"<b>{coin.name} ({coin.symbol})</b>\n"
                f"💹 Курс: <b>${coin.price:,.4f}</b>\n"
                f"{emoji} 24ч: <b>{change:.2f}%</b>\n")
        if coin.algorithm:
            text += f"⚙️ Алгоритм: <code>{coin.algorithm}</code>"
        await message.answer(text)
        return

    # Фильтр 3: Глубокий AI-анализ намерения
    # В личных сообщениях отвечаем всегда, в группах - только на вопросы
    should_respond = False
    if message.chat.type == ChatType.PRIVATE:
        should_respond = True
    else:
        intent = await ai_consultant_service.get_user_intent(user_text)
        if intent == 'question':
            should_respond = True
    
    if not should_respond:
        return

    # Если все проверки пройдены, запускаем полноценного AI-Консультанта
    await admin_service.track_command_usage("AI-Консультант (вопрос)")
    
    temp_msg = await message.reply("🤖 Думаю...")
    await asyncio.sleep(1.5)
    await temp_msg.edit_text("🧠 Анализирую информацию...")
    
    history = await ai_conversation_service.get_history(user_id)
    ai_answer = await ai_consultant_service.get_ai_answer(user_text, history)
    await ai_conversation_service.add_to_history(user_id, user_text, ai_answer)
    
    response_text = (
        f"<b>Ваш вопрос:</b>\n<i>«{sanitize_html(user_text)}»</i>\n\n"
        f"<b>Ответ AI-Консультанта:</b>\n{ai_answer}"
    )
    
    await temp_msg.edit_text(response_text, disable_web_page_preview=True)
