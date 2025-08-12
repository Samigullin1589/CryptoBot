# =================================================================================
# Файл: bot/services/user_service.py (ФИНАЛЬНАЯ ВЕРСИЯ - С ПОИСКОМ ПО USERNAME)
# Описание: Сервис управления пользователями с поддержкой индекса username <-> user_id.
# ИСПРАВЛЕНИЕ: Добавлена логика для поиска пользователя по его имени.
# =================================================================================
import json
import logging
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta

from aiogram.types import User as TelegramUser
from redis.asyncio import Redis
from pydantic import BaseModel

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

    async def get_user(self, user_id: int) -> Optional[User]:
        user_key = self.keys.user_profile(user_id)
        user_data_dict = await self.redis.hgetall(user_key)
        
        if not user_data_dict:
            return None
        
        try:
            # Преобразуем строковые значения к их правильным типам
            if 'id' in user_data_dict: user_data_dict['id'] = int(user_data_dict['id'])
            if 'role' in user_data_dict: user_data_dict['role'] = int(user_data_dict['role'])
            if 'electricity_cost' in user_data_dict: user_data_dict['electricity_cost'] = float(user_data_dict['electricity_cost'])
            if 'verification_data' in user_data_dict and isinstance(user_data_dict['verification_data'], str):
                user_data_dict['verification_data'] = json.loads(user_data_dict['verification_data'])
            
            return User.model_validate(user_data_dict)
        except Exception as e:
            logger.error(f"Ошибка десериализации HASH для пользователя {user_id}: {e}")
            return None

    async def save_user(self, user: User, old_username: Optional[str] = None) -> None:
        """
        Сохраняет модель пользователя в Redis HASH и обновляет индекс username -> user_id.
        """
        user_key = self.keys.user_profile(user.id)
        user_data_to_save = user.model_dump()
        
        final_mapping = {}
        for key, value in user_data_to_save.items():
            if isinstance(value, (dict, list, BaseModel)):
                final_mapping[key] = json.dumps(value)
            elif value is not None:
                final_mapping[key] = str(value)

        # Атомарная операция для обновления профиля и индекса
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(user_key, mapping=final_mapping)
            
            # Логика обновления индекса username -> id
            current_username = user.username.lower() if user.username else None
            old_username_lower = old_username.lower() if old_username else None

            # Если юзернейм изменился или появился, а старый был
            if current_username != old_username_lower and old_username_lower:
                pipe.hdel(self.keys.username_to_id_map(), old_username_lower)
            
            # Если новый юзернейм есть, добавляем его в индекс
            if current_username:
                pipe.hset(self.keys.username_to_id_map(), current_username, user.id)
            
            await pipe.execute()

    async def get_or_create_user(self, tg_user: TelegramUser) -> Tuple[User, bool]:
        """
        Получает пользователя. Если нет - создает. Если данные изменились - обновляет.
        """
        existing_user = await self.get_user(tg_user.id)
        if existing_user:
            update_needed = False
            old_username = existing_user.username
            
            if existing_user.username != tg_user.username or existing_user.first_name != tg_user.full_name:
                existing_user.username = tg_user.username
                existing_user.first_name = tg_user.full_name
                update_needed = True
                
            if update_needed:
                logger.info(f"Обновлены данные для пользователя {tg_user.id} (@{tg_user.username}).")
                await self.save_user(existing_user, old_username=old_username)
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

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """[НОВЫЙ МЕТОД] Находит пользователя по его @username."""
        username_lower = username.lower().lstrip('@')
        user_id = await self.redis.hget(self.keys.username_to_id_map(), username_lower)
        if user_id:
            return await self.get_user(int(user_id))
        return None
    
    # ... (остальные методы без изменений) ...
    async def get_all_user_ids(self) -> List[int]:
        user_ids_raw = await self.redis.smembers(self.keys.all_users_set())
        return [int(user_id) for user_id in user_ids_raw]

    async def update_user_activity(self, user_id: int):
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
        return [json.loads(msg) for msg in reversed(raw_history)]

    async def add_to_conversation_history(self, user_id: int, chat_id: int, user_text: str, ai_answer: str):
        history_key = self.keys.conversation_history(user_id, chat_id)
        user_message = {"role": "user", "parts": [{"text": user_text}]}
        model_message = {"role": "model", "parts": [{"text": ai_answer}]}
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.lpush(history_key, json.dumps(model_message, ensure_ascii=False))
            pipe.lpush(history_key, json.dumps(user_message, ensure_ascii=False))
            pipe.ltrim(history_key, 0, self.history_max_size * 2 - 1)
            await pipe.execute()
            
    async def set_user_electricity_cost(self, user_id: int, cost: float) -> None:
        user, _ = await self.get_or_create_user(TelegramUser(id=user_id, is_bot=False, first_name="Unknown"))
        if user:
            user.electricity_cost = cost
            await self.save_user(user)