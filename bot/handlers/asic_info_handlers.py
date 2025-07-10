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
    
    # Конвертируем байты в строки, если это необходимо (данные из Redis)
    clean_data = {k.decode('utf-8') if isinstance(k, bytes) else k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in data.items()}
    
    name = clean_data.get('name', "Неизвестно")
    
    # Собираем только известные характеристики
    specs_map = {
        "algorithm": "Алгоритм",
        "hashrate": "Хешрейт",
        "power": "Потребление",
        "efficiency": "Эффективность"
    }
    
    specs_text = "\n".join([f"  ▫️ <b>{rus_name}:</b> {clean_data.get(key)}" for key, rus_name in specs_map.items() if clean_data.get(key) not in [None, "N/A"]])
        
    text = (
        f"📋 <b>Паспорт устройства: {name}</b>\n\n"
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
        model_query = message.text.split(maxsplit=1)[1]
    except IndexError:
        await message.reply("Пожалуйста, укажите модель ASIC после команды.\n"
                            "Например: <code>/asic s19k pro</code>")
        return

    found_asic_dict = await asic_service.find_asic_by_query(model_query)
            
    if found_asic_dict:
        # ИСПРАВЛЕНО: Убираем .model_dump(), так как found_asic_dict - это уже словарь
        response_text = format_asic_passport(found_asic_dict)
        await message.answer(response_text, disable_web_page_preview=True)
    else:
        await message.answer(f"😕 Модель, похожая на '{model_query}', не найдена в нашей базе. "
                             "База данных обновляется автоматически. Попробуйте выполнить /force_update_asics или проверьте название.")