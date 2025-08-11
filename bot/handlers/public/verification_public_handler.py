# =================================================================================
# Файл: bot/handlers/public/verification_public_handler.py (ПРОМЫШЛЕННЫЙ СТАНДАРТ)
# Описание: Обработчики для публичных команд верификации с продуманной
# логикой и улучшенным пользовательским опытом.
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
    Обрабатывает команду /check для проверки статуса пользователя.
    Поддерживает 3 сценария: проверка себя, проверка по reply, проверка по mention/ID.
    """
    # Сначала пытаемся найти целевого пользователя по reply или mention
    target_user = await extract_target_user(message, deps.user_service)
    
    # Если цель не найдена (команда введена без аргументов), проверяем автора сообщения
    if not target_user:
        logger.info(f"Цель для /check не найдена, проверяем автора: {message.from_user.id}")
        target_user, _ = await deps.user_service.get_or_create_user(message.from_user)

    if not target_user:
        await message.answer("Не удалось определить пользователя для проверки. Попробуйте снова.")
        return
        
    response_text = deps.verification_service.format_check_message(target_user)
    await message.answer(response_text, disable_web_page_preview=True)

@router.message(Command("infoVerif"))
async def handle_info_verif_command(message: Message, deps: Deps):
    """
    Отправляет подробную информацию о том, как и зачем проходить верификацию,
    с кнопкой для связи с администратором.
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