# bot/handlers/admin/data_management_handlers.py

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.filters.admin_filter import IsAdmin
from bot.services.asic_service import AsicService

router = Router()
router.message.filter(IsAdmin()) # Все команды в этом файле только для админов
logger = logging.getLogger(__name__)

@router.message(Command("force_update_asics"))
async def force_update_asics_db(message: Message, asic_service: AsicService):
    """
    Принудительно запускает задачу обновления базы данных ASIC'ов.
    """
    await message.answer("✅ Принято. Запускаю процесс обновления базы данных ASIC'ов в фоновом режиме. "
                         "Это может занять до минуты. Вы получите уведомление о завершении.")
    
    try:
        asics = await asic_service.update_asics_db()
        logger.info("Manual ASIC DB update completed successfully.")
        await message.answer(f"✅ База данных ASIC успешно обновлена. Найдено и сохранено моделей: {len(asics)}.")
    except Exception as e:
        logger.error(f"Manual ASIC DB update failed: {e}", exc_info=True)
        await message.answer(f"❌ Произошла ошибка при обновлении базы данных: {e}")