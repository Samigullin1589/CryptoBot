import logging
import redis.asyncio as redis
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
# Убедитесь, что у вас есть такой фильтр, или временно уберите его для теста
from bot.filters.admin_filter import AdminFilter 

router = Router()
logger = logging.getLogger(__name__)

# Применяем фильтр, чтобы команда была доступна только админам
@router.message(Command("force_clear_cache"), AdminFilter())
async def force_clear_asic_cache(message: Message, redis_client: redis.Redis):
    """
    Принудительно очищает все ключи, связанные с ASIC, из кэша Redis.
    """
    logger.warning(f"Admin {message.from_user.id} initiated a forced cache clear.")
    
    try:
        # Находим все ключи, связанные с паспортами ASIC
        keys_to_delete = [key async for key in redis_client.scan_iter("asic_passport:*")]
        
        # Добавляем ключ времени последнего обновления
        last_update_key = "asics_last_update_utc"
        # Используем await, так как exists может быть асинхронным
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

