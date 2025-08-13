# =================================================================================
# Файл: bot/handlers/public/common_handler.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ УМНАЯ)
# Описание: Обрабатывает общие команды и текстовый ввод, корректно
#           различая нажатия на текстовые кнопки и запросы к AI.
# ИСПРАВЛЕНИЕ: Исправлена ссылка на обработчик игры для устранения AttributeError.
#              Улучшены и конкретизированы импорты.
# =================================================================================
import logging
from typing import Dict, Any

from aiogram import F, Router, Bot, types
from aiogram.filters import CommandStart, Command, CommandObject, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatType

from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.keyboards.onboarding_keyboards import get_onboarding_start_keyboard, get_onboarding_step_keyboard
from bot.states.common_states import CommonStates
from bot.utils.dependencies import Deps
from bot.utils.text_utils import sanitize_html
from bot.texts.public_texts import HELP_TEXT, ONBOARDING_TEXTS

# --- Корректный импорт всех необходимых обработчиков ---
from bot.handlers.public import price_handler, asic_handler, news_handler, quiz_handler, market_info_handler, crypto_center_handler
from bot.handlers.tools import calculator_handler
from bot.handlers.game import mining_game_handler # ИСПРАВЛЕНО: Правильный импорт игрового хендлера

from bot.keyboards.callback_factories import MenuCallback

router = Router(name=__name__)
logger = logging.getLogger(__name__)

# --- Словарь для сопоставления текста кнопки с ее обработчиком ---
TEXT_COMMAND_MAP: Dict[str, Any] = {
    "💹 Курс": (price_handler.handle_price_menu_start, "price"),
    "⚙️ Топ ASIC": (asic_handler.top_asics_start, "asics"),
    "⛏️ Калькулятор": (calculator_handler.start_profit_calculator, "calculator"),
    "📰 Новости": (news_handler.handle_news_menu_start, "news"),
    "😱 Индекс Страха": (market_info_handler.handle_fear_greed_index, "fear_index"),
    "⏳ Халвинг": (market_info_handler.handle_halving_info, "halving"),
    "📡 Статус BTC": (market_info_handler.handle_btc_status, "btc_status"),
    "🧠 Викторина": (quiz_handler.handle_quiz_start, "quiz"),
    # ИСПРАВЛЕНО: Указана правильная функция (handle_mining_menu) и ее источник (mining_game_handler)
    "💎 Виртуальный Майнинг": (mining_game_handler.handle_mining_menu, "game"),
    "💎 Крипто-Центр": (crypto_center_handler.crypto_center_entry, "crypto_center")
}

class AITriggerFilter(BaseFilter):
    async def __call__(self, message: Message, bot: Bot) -> bool:
        if not message.text or message.text.startswith('/'):
            return False
        if message.text in TEXT_COMMAND_MAP:
            return False

        bot_info = await bot.get_me()
        if message.chat.type == ChatType.PRIVATE:
            return True
        if f"@{bot_info.username}" in message.text:
            return True
        if message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id:
            return True
        return False

# --- ОБРАБОТЧИКИ КОМАНД ---

@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, command: CommandObject, deps: Deps):
    await state.clear()
    user = message.from_user
    profile, is_new_user = await deps.user_service.get_or_create_user(user)

    if is_new_user and command.args:
        try:
            referrer_id = int(command.args)
            logger.info(f"Новый пользователь {user.id} пришел по реферальной ссылке от {referrer_id}")
        except (ValueError, TypeError):
            logger.warning(f"Некорректный deeplink-аргумент '{command.args}' от пользователя {user.id}")
    
    if is_new_user:
        text = (f"👋 <b>Привет, {user.full_name}!</b>\n\n"
                "Я ваш персональный ассистент в мире криптовалют и майнинга. "
                "Давайте я быстро покажу, что я умею!")
        await message.answer(text, reply_markup=get_onboarding_start_keyboard())
    else:
        await message.answer(
            "👋 С возвращением! Выберите одну из опций в меню ниже.",
            reply_markup=get_main_menu_keyboard()
        )
    await state.set_state(CommonStates.main_menu)

@router.message(Command("help"))
async def handle_help(message: Message):
    await message.answer(HELP_TEXT, disable_web_page_preview=True)

# --- УПРАВЛЕНИЕ ОНБОРДИНГОМ ---
@router.callback_query(F.data.startswith("onboarding:"))
async def handle_onboarding_navigation(call: CallbackQuery, state: FSMContext):
    await call.answer()
    action = call.data.split(":")[1]

    if action in ["skip", "finish"]:
        text = ("Отлично, теперь вы знаете все основы!\n\n"
                "Вот ваше главное меню. Если забудете, что я умею, просто вызовите команду /help.")
        await call.message.edit_text(text, reply_markup=get_main_menu_keyboard())
        await state.set_state(CommonStates.main_menu)
        return

    try:
        step = int(action.split("_")[1])
        await state.update_data(onboarding_step=step)
        
        text = ONBOARDING_TEXTS.get(step, "Неизвестный шаг.")
        keyboard = get_onboarding_step_keyboard(step)
        await call.message.edit_text(text, reply_markup=keyboard)
    except (ValueError, IndexError):
        logger.error(f"Invalid onboarding action: {action}")
        await call.answer("Произошла ошибка навигации.", show_alert=True)

# --- ОБРАБОТКА ПРОИЗВОЛЬНОГО ТЕКСТА ---

@router.message(F.text.in_(TEXT_COMMAND_MAP.keys()))
async def handle_text_as_button(message: Message, state: FSMContext, deps: Deps):
    """
    Если текст сообщения совпадает с кнопкой меню, эмулируем нажатие на callback-кнопку.
    """
    handler_func, action = TEXT_COMMAND_MAP[message.text]
    
    fake_callback_query = types.CallbackQuery(
        id=str(message.message_id),
        from_user=message.from_user,
        chat_instance="fake_chat_instance",
        message=message,
        data=MenuCallback(level=0, action=action).pack()
    )
    
    await handler_func(call=fake_callback_query, state=state, deps=deps)

@router.message(AITriggerFilter())
async def handle_text_for_ai(message: Message, state: FSMContext, deps: Deps):
    """
    Обрабатывает текстовые сообщения, которые не являются командами или кнопками,
    и передает их AI-консультанту.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_text = message.text.strip()
    
    temp_msg = await message.reply("🤖 Думаю...")
    
    history = await deps.user_service.get_conversation_history(user_id, chat_id)
    ai_answer = await deps.ai_content_service.get_consultant_answer(user_text, history)
    await deps.user_service.add_to_conversation_history(user_id, chat_id, user_text, ai_answer)
    
    response_text = (f"<b>Ваш вопрос:</b>\n<i>«{sanitize_html(user_text)}»</i>\n\n"
                     f"<b>Ответ AI-Консультанта:</b>\n{ai_answer}")
    
    await temp_msg.edit_text(response_text, disable_web_page_preview=True)