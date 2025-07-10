import logging
import redis.asyncio as redis
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

# Импортируем наши настройки, где хранится ID админа
from bot.config.settings import settings

router = Router()
logger = logging.getLogger(__name__)

# Убираем AdminFilter из декоратора
@router.message(Command("force_clear_cache"))
async def force_clear_asic_cache(message: Message, redis_client: redis.Redis):
    """
    Принудительно очищает все ключи, связанные с ASIC, из кэша Redis.
    Теперь доступно только администратору, ID которого указан в настройках.
    """
    # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ---
    # Проверяем ID пользователя прямо внутри функции, а не через фильтр
    if message.from_user.id != settings.admin_chat_id:
        logger.warning(f"User {message.from_user.id} tried to use an admin command: /force_clear_cache")
        # Просто ничего не отвечаем не-админам
        return
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    logger.warning(f"Admin {message.from_user.id} initiated a forced cache clear.")
    
    try:
        # Находим все ключи, связанные с паспортами ASIC
        keys_to_delete = [key async for key in redis_client.scan_iter("asic_passport:*")]
        
        # Добавляем ключ времени последнего обновления
        last_update_key = "asics_last_update_utc"
        if await redis_client.exists(last_update_key):
            keys_to_delete.append(last_update_key)
        
        if keys_to_delete:
            # redis-py > 4.2.0 требует передавать ключи как отдельные аргументы
            deleted_count = await redis_client.delete(*keys_to_delete)
            await message.answer(f"✅ Успешно удалено <b>{deleted_count}</b> ключей из кэша Redis.\n\n"
                                 "При следующем запросе 'Топ ASIC' или 'Калькулятор' база данных будет загружена заново.")
        else:
            await message.answer("ℹ️ Кэш ASIC уже был пуст. Удалять нечего.")
            
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        await message.answer(f"❌ Произошла ошибка при очистке кэша: {e}")
