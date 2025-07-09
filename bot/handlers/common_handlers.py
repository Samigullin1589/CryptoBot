import logging
from typing import Union

import redis.asyncio as redis
from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
# 👇 Добавляем нужные импорты
from aiogram.enums import ContentType
from aiogram.exceptions import TelegramBadRequest

from bot.config.settings import settings
from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.services.admin_service import AdminService
from bot.utils.helpers import get_message_and_chat_id

router = Router()
logger = logging.getLogger(__name__)

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

    if not referrer_id.isdigit() or int(referrer_id) == new_user_id:
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
    """Обработчик команды /start с поддержкой рефералов и удалением старой клавиатуры."""
    await admin_service.track_command_usage("/start")
    await state.clear()
    
    if command.args:
        await handle_referral(message, command, redis_client, bot)
    
    logger.info(f"User {message.from_user.id} started the bot.")

    await message.answer(
        "Загружаю меню...",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await message.answer(
        "👋 Добро пожаловать в CryptoBot! Выберите одну из опций в меню ниже, чтобы начать.",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("help"))
async def handle_help(message: Message, admin_service: AdminService):
    """Отправляет информационное сообщение по команде /help."""
    await admin_service.track_command_usage("/help")
    await message.answer(HELP_TEXT, disable_web_page_preview=True)


# --- ИЗМЕНЕНИЯ ЗДЕСЬ ---
@router.callback_query(F.data == "back_to_main_menu")
async def handle_back_to_main(call: CallbackQuery, state: FSMContext, admin_service: AdminService):
    """
    Обработчик кнопки 'Назад в главное меню'.
    Умеет обрабатывать колбэки из текстовых сообщений, медиа и опросов.
    """
    await admin_service.track_command_usage("⬅️ Назад в меню")
    await state.clear()
    
    try:
        # Проверяем, можно ли отредактировать сообщение (если это текст)
        if call.message.content_type == ContentType.TEXT:
            await call.message.edit_text("Главное меню:", reply_markup=get_main_menu_keyboard())
        else:
            # Если это опрос, фото или что-то еще, удаляем старое и присылаем новое
            await call.message.delete()
            await call.message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())
    except TelegramBadRequest as e:
        logger.error(f"Error returning to main menu: {e}. Sending new message.")
        # Если возникла любая другая ошибка (например, сообщение слишком старое),
        # просто отправляем новое сообщение.
        await call.message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())
    finally:
        # В любом случае отвечаем на колбэк, чтобы убрать "часики"
        await call.answer()