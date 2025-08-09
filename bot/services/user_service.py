# =================================================================================
# Файл: bot/services/user_service.py (ФИНАЛЬНАЯ ВЕРСИЯ - АРХИТЕКТУРНО ИСПРАВЛЕННАЯ)
# Описание: Сервис управления пользователями с корректной сериализацией
# вложенных Pydantic моделей для Redis HASH.
# ИСПРАВЛЕНИЕ: Устранена ошибка redis.exceptions.DataError путем
# преобразования вложенных моделей в JSON-строки перед сохранением в Redis.
# =================================================================================
import json
import logging
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta

from aiogram.types import User as TelegramUser
from redis.asyncio import Redis

from bot.utils.models import User, UserRole, VerificationData
from bot.utils.keys import KeyFactory
# ИЗМЕНЕНО: Импортируем экземпляр настроек из нового файла
from bot.config.config import settings

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для управления данными пользователей в Redis."""
    
    def __init__(self, redis: Redis):
        self.redis = redis
        self.keys = KeyFactory
        self.history_max_size = settings.ai.history_max_size

    async def get_user(self, user_id: int) -> Optional[User]:
        """
        Получает данные пользователя из Redis HASH и корректно десериализует вложенные JSON.
        """
        user_key = self.keys.user_profile(user_id)
        user_data_dict = await self.redis.hgetall(user_key)
        
        if not user_data_dict:
            return None
        
        try:
            # ИСПРАВЛЕНО: Десериализуем вложенные JSON-объекты перед валидацией
            if 'verification_data' in user_data_dict:
                user_data_dict['verification_data'] = json.loads(user_data_dict['verification_data'])
            
            return User.model_validate(user_data_dict)
        except (json.JSONDecodeError, TypeError, Exception) as e:
            logger.error(f"Ошибка при десериализации HASH-данных для пользователя {user_id}: {e}")
            return None

    async def save_user(self, user: User) -> None:
        """
        Сохраняет модель пользователя в Redis HASH, корректно сериализуя вложенные модели.
        """
        user_key = self.keys.user_profile(user.id)
        
        # ИСПРАВЛЕНО: Преобразуем модель в словарь и вручную сериализуем вложенные объекты
        user_data_to_save = user.model_dump() 
        if isinstance(user_data_to_save.get('verification_data'), dict):
            user_data_to_save['verification_data'] = json.dumps(user_data_to_save['verification_data'])

        await self.redis.hset(user_key, mapping=user_data_to_save)

    async def get_or_create_user(self, tg_user: TelegramUser) -> Tuple[User, bool]:
        """
        Получает пользователя из базы данных. Если его нет, создает нового
        и сохраняет его, корректно сериализуя данные.
        """
        existing_user = await self.get_user(tg_user.id)
        if existing_user:
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
        
        await self.save_user(new_user)
        await self.redis.sadd(self.keys.all_users_set(), new_user.id)

        logger.info(f"Зарегистрирован новый пользователь {tg_user.id} (@{tg_user.username}).")
        return new_user, True

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