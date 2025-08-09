# =================================================================================
# Файл: bot/services/user_service.py (ФИНАЛЬНАЯ ВЕРСИЯ - АРХИТЕКТУРНО ИСПРАВЛЕННАЯ)
# Описание: Сервис управления пользователями, переведенный на атомарную
# работу с HASH в Redis для устранения ошибок WRONGTYPE.
# =================================================================================
import json
import logging
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta

from aiogram.types import User as TelegramUser
from redis.asyncio import Redis

from bot.utils.models import User, UserRole
from bot.utils.keys import KeyFactory
from bot.config.settings import settings

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для управления данными пользователей в Redis."""
    
    def __init__(self, redis: Redis):
        self.redis = redis
        self.keys = KeyFactory
        self.history_max_size = settings.ai.history_max_size

    # ========================== КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ №1 ==========================
    async def get_user(self, user_id: int) -> Optional[User]:
        """
        Получает данные пользователя из Redis, используя HGETALL, так как
        профиль хранится в виде HASH для гибкости и производительности.
        """
        user_key = self.keys.user_profile(user_id)
        # Используем HGETALL для чтения хэша, а не GET для строки
        user_data_dict = await self.redis.hgetall(user_key)
        
        if not user_data_dict:
            return None
            
        try:
            # Pydantic v2 отлично работает со словарями напрямую
            return User.model_validate(user_data_dict)
        except Exception as e:
            logger.error(f"Ошибка при десериализации HASH-данных для пользователя {user_id}: {e}")
            return None

    async def save_user(self, user: User) -> None:
        """
        Сохраняет модель пользователя в Redis в виде HASH.
        Это позволяет атомарно обновлять отдельные поля в будущем.
        """
        user_key = self.keys.user_profile(user.id)
        # Преобразуем Pydantic модель в словарь строк для HMSET
        user_data_to_save = user.model_dump(mode='json')
        # Pydantic автоматически сериализует вложенные модели в JSON-строки
        
        await self.redis.hset(user_key, mapping=user_data_to_save)
    # =========================================================================

    async def get_or_create_user(self, tg_user: TelegramUser) -> Tuple[User, bool]:
        """
        Получает пользователя из базы данных. Если его нет, создает нового
        и сохраняет его в виде HASH.
        """
        existing_user = await self.get_user(tg_user.id)
        if existing_user:
            # Обновим данные, если они изменились (например, username)
            if (existing_user.username != tg_user.username or 
                existing_user.first_name != tg_user.full_name):
                existing_user.username = tg_user.username
                existing_user.first_name = tg_user.full_name
                await self.save_user(existing_user)
            return existing_user, False
        
        new_user = User(
            id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.full_name,
            language_code=tg_user.language_code,
            role=UserRole.USER
        )
        
        user_key = self.keys.user_profile(new_user.id)
        user_data_to_save = new_user.model_dump(mode='json')

        async with self.redis.pipeline(transaction=True) as pipe:
            # ================== КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ №2 ==================
            # Используем HSET вместо SET для сохранения профиля
            pipe.hset(user_key, mapping=user_data_to_save)
            # =============================================================
            pipe.sadd(self.keys.all_users_set(), new_user.id)
            await pipe.execute()

        logger.info(f"Зарегистрирован новый пользователь {tg_user.id} (@{tg_user.username}).")
        return new_user, True

    # --- Остальные методы остаются без изменений, так как они не затрагивают профиль напрямую ---
    async def get_all_user_ids(self) -> List[int]:
        user_ids_raw = await self.redis.smembers(self.keys.all_users_set())
        return [int(user_id) for user_id in user_ids_raw]

    async def update_user_activity(self, user_id: int, chat_id: int):
        now = datetime.utcnow()
        today_str, week_str = now.strftime('%Y-%m-%d'), now.strftime('%Y-%U')
        day_key, week_key = f"users:active:day:{today_str}", f"users:active:week:{week_str}"

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.sadd(day_key, user_id)
            pipe.sadd(week_key, user_id)
            pipe.expire(day_key, timedelta(days=2))
            pipe.expire(week_key, timedelta(weeks=2))
            await pipe.execute()

    async def get_conversation_history(self, user_id: int, chat_id: int) -> List[Dict]:
        history_key = self.keys.conversation_history(user_id, chat_id)
        raw_history = await self.redis.lrange(history_key, 0, self.history_max_size * 2 - 1)
        history = [json.loads(msg) for msg in reversed(raw_history)]
        return history

    async def add_to_conversation_history(self, user_id: int, chat_id: int, user_text: str, ai_answer: str):
        history_key = self.keys.conversation_history(user_id, chat_id)
        user_message = {"role": "user", "parts": [{"text": user_text}]}
        model_message = {"role": "model", "parts": [{"text": ai_answer}]}
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.lpush(history_key, json.dumps(model_message, ensure_ascii=False))
            pipe.lpush(history_key, json.dumps(user_message, ensure_ascii=False))
            pipe.ltrim(history_key, 0, self.history_max_size * 2 - 1)
            await pipe.execute()