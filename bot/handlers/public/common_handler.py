# =================================================================================
# Файл: bot/handlers/public/common_handler.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛЬНАЯ)
# Описание: Обрабатывает общие команды и текстовый ввод.
# =================================================================================
import logging
from typing import Union, Dict, Any

from aiogram import F, Router, Bot, types
from aiogram.filters import CommandStart, Command, CommandObject, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, User
from aiogram.enums import ChatType

from bot.keyboards.keyboards import get_main_menu_keyboard
from bot.keyboards.onboarding_keyboards import get_onboarding_start_keyboard, get_onboarding_step_keyboard
from bot.states.common_states import CommonStates
from bot.utils.dependencies import Deps
from bot.utils.formatters import format_price_info
from bot.utils.text_utils import sanitize_html
from bot.texts.public_texts import HELP_TEXT, ONBOARDING_TEXTS, get_referral_success_text

router = Router(name=__name__)
logger = logging.getLogger(__name__)

# Кастомный фильтр для определения, когда нужно вызывать AI
class AITriggerFilter(BaseFilter):
    async def __call__(self, message: Message, bot: Bot) -> bool:
        bot_info = await bot.get_me()
        if message.chat.type == ChatType.PRIVATE:
            return True
        if message.text and f"@{bot_info.username}" in message.text:
            return True
        if message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id:
            return True
        return False

# --- ОБРАБОТЧИКИ КОМАНД ---

@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, command: CommandObject, deps: Deps):
    """
    Обработчик /start. Регистрирует пользователя и запускает онбординг.
    """
    await state.clear()
    user = message.from_user
    
    profile, is_new_user = await deps.user_service.get_or_create_user(user)

    if is_new_user and command.args:
        try:
            referrer_id = int(command.args)
            # ВРЕМЕННО ОТКЛЮЧЕНО, так как метод process_referral не реализован в UserService
            # bonus_credited = await deps.user_service.process_referral(
            #     new_user_id=user.id,
            #     referrer_id=referrer_id
            # )
            # if bonus_credited:
            #     bonus_amount = 50.0 # Пример
            #     await deps.bot.send_message(
            #         referrer_id,
            #         get_referral_success_text(float(bonus_amount))
            #     )
            logger.info(f"Новый пользователь {user.id} пришел по реферальной ссылке от {referrer_id}")
        except (ValueError, TypeError):
            logger.warning(f"Некорректный deeplink-аргумент '{command.args}' от пользователя {user.id}")
        except Exception as e:
            logger.error(f"Ошибка обработки реферала для {user.id} от '{command.args}': {e}")
    
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
    """Отправляет справочное сообщение по команде /help."""
    await message.answer(HELP_TEXT, disable_web_page_preview=True)

# --- УПРАВЛЕНИЕ ОНБОРДИНГОМ ЧЕРЕЗ FSM ---
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

@router.message(F.text, ~F.text.startswith('/'))
async def handle_text_message(message: Message, state: FSMContext, deps: Deps):
    """
    Многоуровневый обработчик текста: сначала ищет цену, если не находит - передает AI.
    """
    # Уровень 2: AI-Консультант
    ai_filter = AITriggerFilter()
    if await ai_filter(message, deps.bot):
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