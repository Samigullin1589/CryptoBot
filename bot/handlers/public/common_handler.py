# ===============================================================
# Файл: bot/handlers/public/common_handler.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Полностью переработанный хэндлер для общих команд.
# Использует FSM для онбординга, делегирует логику в сервисы
# и применяет единый стиль для всех публичных функций.
# ===============================================================
import logging

from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest

from bot.config.settings import settings
from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.keyboards.onboarding_keyboards import get_onboarding_start_keyboard, get_onboarding_step_keyboard
from bot.utils.helpers import sanitize_html
from bot.services.user_service import UserService
from bot.services.ai_consultant_service import AIConsultantService
from bot.services.price_service import PriceService
from bot.services.admin_service import AdminService
from bot.states.common_states import CommonStates
from bot.utils.formatters import format_price_info
from bot.texts.public_texts import HELP_TEXT, ONBOARDING_TEXTS # Тексты вынесены

router = Router()
logger = logging.getLogger(__name__)

@router.message(CommandStart())
async def handle_start(
    message: Message, state: FSMContext, command: CommandObject, user_service: UserService, admin_service: AdminService
):
    """
    Обработчик команды /start.
    - Регистрирует пользователя через UserService (который также обрабатывает рефералов).
    - Запускает онбординг для новых пользователей.
    - Показывает главное меню для существующих.
    """
    await admin_service.track_command_usage("/start")
    await state.clear()
    
    # Регистрация и обработка реферала делегированы сервису
    is_new_user = await user_service.register_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        referrer_id_str=command.args
    )
    
    if is_new_user:
        logger.info(f"New user {message.from_user.id} registered. Starting onboarding.")
        await state.set_state(CommonStates.onboarding)
        await message.answer(
            ONBOARDING_TEXTS['start'].format(full_name=message.from_user.full_name),
            reply_markup=get_onboarding_start_keyboard()
        )
    else:
        logger.info(f"Existing user {message.from_user.id} started the bot.")
        await message.answer("👋 С возвращением!", reply_markup=get_main_menu_keyboard())

@router.callback_query(F.data.startswith("onboarding:"))
async def handle_onboarding_callbacks(call: CallbackQuery, state: FSMContext):
    """
    Единый обработчик для всех шагов онбординга.
    """
    action = call.data.split(":")[1]
    await call.answer()

    if action == "skip" or action == "finish":
        await state.clear()
        await call.message.delete()
        await call.message.answer(ONBOARDING_TEXTS['finish'], reply_markup=get_main_menu_keyboard())
        return

    try:
        step = int(action.split("_")[1])
        text = ONBOARDING_TEXTS[f'step_{step}']
        keyboard = get_onboarding_step_keyboard(step)
        await call.message.edit_text(text, reply_markup=keyboard)
    except (ValueError, KeyError, IndexError):
        logger.warning(f"Invalid onboarding callback data: {call.data}")
        await call.message.edit_text("Произошла ошибка. Пожалуйста, начните заново /start")
        await state.clear()

@router.message(Command("help"))
async def handle_help(message: Message, admin_service: AdminService):
    """Отправляет справочное сообщение по команде /help."""
    await admin_service.track_command_usage("/help")
    await message.answer(HELP_TEXT, disable_web_page_preview=True)

@router.callback_query(F.data == "back_to_main_menu")
async def handle_back_to_main(call: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад в главное меню'."""
    await state.clear()
    try:
        await call.message.edit_text("Главное меню:", reply_markup=get_main_menu_keyboard())
    except TelegramBadRequest:
        await call.message.delete()
        await call.message.answer("Главное меню:", reply_markup=get_main_menu_keyboard())
    finally:
        await call.answer()

@router.message(F.text, lambda msg: not msg.text.startswith('/'))
async def handle_arbitrary_text(
    message: Message, state: FSMContext, bot: Bot, user_service: UserService,
    ai_consultant_service: AIConsultantService, price_service: PriceService, admin_service: AdminService
):
    """
    Обрабатывает произвольный текстовый ввод.
    - Сначала проверяет, не является ли текст тикером монеты.
    - Если нет, и это ЛС/ответ/упоминание, отвечает с помощью AI.
    """
    if await state.get_state() is not None:
        return # Игнорируем, если пользователь в каком-либо сценарии FSM

    # 1. Проверка на тикер
    coin = await price_service.get_crypto_price(message.text.strip())
    if coin:
        await admin_service.track_command_usage(f"Курс (текстом): {coin.symbol}")
        await message.answer(format_price_info(coin))
        return

    # 2. Проверка на необходимость ответа AI
    bot_info = await bot.get_me()
    is_private = message.chat.type == ChatType.PRIVATE
    is_mention = f"@{bot_info.username}" in message.text
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id

    if is_private or is_mention or is_reply_to_bot:
        await admin_service.track_command_usage("AI-Консультант")
        temp_msg = await message.reply("🤖 Думаю...")
        
        history = await user_service.get_conversation_history(message.from_user.id, message.chat.id)
        ai_answer = await ai_consultant_service.get_ai_answer(message.text, history)
        await user_service.add_to_conversation_history(message.from_user.id, message.chat.id, message.text, ai_answer)
        
        await temp_msg.edit_text(ai_answer, disable_web_page_preview=True)
