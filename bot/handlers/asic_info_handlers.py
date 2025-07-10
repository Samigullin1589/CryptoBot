import logging
import re
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.services.asic_service import AsicService
from bot.services.admin_service import AdminService

router = Router()
logger = logging.getLogger(__name__)

def format_asic_passport(data: dict) -> str:
    """Формирует красивый текстовый паспорт для ASIC."""
    
    # Преобразуем словарь характеристик в строки
    specs_text = "\n".join([f"  ▫️ <b>{key.replace('_', ' ').capitalize()}:</b> {value}" for key, value in data.items() if key != 'name'])
        
    text = (
        f"📋 <b>Паспорт устройства: {data['name']}</b>\n\n"
        f"<b><u>Технические характеристики:</u></b>\n{specs_text}\n"
    )
    return text

@router.message(Command("asic"))
async def asic_passport_handler(message: Message, asic_service: AsicService, admin_service: AdminService):
    """
    Обрабатывает команду /asic [модель] и выдает паспорт устройства из кэша Redis.
    """
    await admin_service.track_command_usage("/asic")
    
    try:
        # Убираем /asic и приводим к нижнему регистру, удаляя пробелы
        model_query = message.text.split(maxsplit=1)[1]
    except IndexError:
        await message.reply("Пожалуйста, укажите модель ASIC после команды.\n"
                            "Например: <code>/asic s19k pro</code>")
        return

    found_asic = await asic_service.find_asic_by_query(model_query)
            
    if found_asic:
        # Конвертируем Pydantic модель в словарь для форматирования
        response_text = format_asic_passport(found_asic.model_dump())
        await message.answer(response_text, disable_web_page_preview=True)
    else:
        await message.answer(f"😕 Модель, похожая на '{model_query}', не найдена в нашей базе. "
                             "База данных обновляется автоматически, попробуйте позже или проверьте название.")