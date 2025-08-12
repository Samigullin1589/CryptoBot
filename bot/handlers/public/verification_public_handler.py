# =================================================================================
# Файл: bot/handlers/public/verification_public_handler.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ - УЛУЧШЕННЫЙ)
# Описание: Обработчики для публичных команд верификации.
# ИСПРАВЛЕНИЕ: Улучшена логика команды /check для корректной
#              обработки случаев, когда целевой пользователь не найден.
# =================================================================================
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from bot.utils.dependencies import Deps
from bot.utils.user_helpers import extract_target_user
from bot.keyboards.verification_keyboards import get_verification_info_keyboard

router = Router(name="verification_public_router")
logger = logging.getLogger(__name__)

@router.message(Command("check"))
async def handle_check_command(message: Message, deps: Deps):
    """
    Обрабатывает команду /check.
    - Если есть аргумент (@username/ID) или reply - ищет цель.
    - Если цель не найдена - сообщает об этом.
    - Если аргументов нет - проверяет автора команды.
    """
    args = message.text.split()
    target_user = await extract_target_user(message, deps.user_service)

    # Случай 1: Целевой пользователь успешно найден (по reply, ID или @username)
    if target_user:
        response_text = deps.verification_service.format_check_message(target_user)
        await message.answer(response_text, disable_web_page_preview=True)
        return

    # Случай 2: Был указан аргумент (ID/@username), но пользователь не найден
    if len(args) > 1:
        await message.reply(
            "❌ **Пользователь не найден.**\n\n"
            "Я не могу найти пользователя по указанному ID или @username. "
            "Вероятнее всего, этот человек еще ни разу не взаимодействовал со мной. "
            "Попросите его запустить бота командой /start."
        )
        return

    # Случай 3: Аргументы не указаны, проверяем автора команды
    logger.info(f"Цель для /check не указана, проверяем автора: {message.from_user.id}")
    author_user, _ = await deps.user_service.get_or_create_user(message.from_user)
    if author_user:
        response_text = deps.verification_service.format_check_message(author_user)
        await message.answer(response_text, disable_web_page_preview=True)
    else:
        # Этот случай практически невозможен, но является защитой
        await message.answer("Не удалось определить пользователя для проверки.")


@router.message(Command("infoverif"))
async def handle_info_verif_command(message: Message, deps: Deps):
    """
    Отправляет подробную информацию о том, как и зачем проходить верификацию.
    """
    admin_id = deps.settings.admin_ids[0] if deps.settings.admin_ids else None
    
    text = (
        "✅ <b>Что такое верификация и зачем она нужна?</b>\n\n"
        "Верификация — это процесс подтверждения вашей личности и надежности как поставщика. "
        "Получение статуса «ПРОВЕРЕННЫЙ ПОСТАВЩИК» значительно повышает доверие со стороны других участников "
        "и открывает доступ к дополнительным возможностям в сообществе.\n\n"
        "<b>Преимущества верифицированного статуса:</b>\n"
        "• <b>Доверие:</b> Ваш профиль будет отмечен специальным знаком, который видят все пользователи.\n"
        "• <b>Безопасность:</b> Наличие депозита страхует сделки и является гарантией вашей добросовестности.\n"
        "• <b>Приоритет:</b> Ваши предложения могут иметь больший вес и видимость.\n\n"
        "<b>Как пройти верификацию?</b>\n"
        "Для начала процесса, пожалуйста, свяжитесь с куратором. Он предоставит вам полный список требований и "
        "проведет по всем шагам."
    )
    
    await message.answer(text, reply_markup=get_verification_info_keyboard(admin_id))